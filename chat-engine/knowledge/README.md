# knowledge: kunskapsmaterial för RAG (PLAN-118)

Det här är **specen** för hur materialet ska se ut, så att det går att dela upp automatiskt och söka i (PLAN-113, ChromaDB). Alla regler är mätta mot de nio riktiga modulerna. Själva modulerna ligger **inte** i git, se längre ned.

## Flödet

```
Word-modulerna  →  convert_docx.py  →  data/*.md  →  chunker.py  →  (PLAN-113) embeddings  →  ChromaDB
 (utanför git)      rensar och        (ignoreras     delar i            gör sifferrepresen-      retrieve_context()
                    konverterar        av git)       sökbara bitar      tationer och lagrar      i backend
```

Rörlig del som är klar och testad: `convert_docx.py` och `chunker.py` (`tests/test_knowledge.py`). Det som återstår är PLAN-113.

## Regler för markdown-filerna

**Metadata överst**, mellan `---`:

```markdown
---
id: modul-03-tankefallor-och-ifragasattande-av-tankar
titel: "Modul 3: Tankefällor och ifrågasättande av tankar"
modul: 3
källa: "CHAI-behandlingsmoduler"
licens: "internt studentprojekt, ej publicerat"
språk: sv
version: 1
granskad_av:
---
```

**Rubriker styr uppdelningen:**

| Rubrik | Betydelse |
|---|---|
| `#` | filens titel (en per fil) |
| `##` | ett avsnitt (ett begrepp, en teknik eller en övning) |
| `###`, `####` | delavsnitt. Varje rubrik med egen text blir en egen sökbar bit. |

**Bitarna** (`chunker.py`):

- Rubrikvägen sätts först i varje bit (`Modul 3: ... > Tankefällor > Tankeläsning`), så att en kort bit får sitt sammanhang när den hittas.
- Avsnitt under **40 ord** slås ihop med nästa. Avsnitt över **450 ord** delas vid styckegränser (ca 350 ord per del).
- Typ härleds ur rubriken: `övning` (börjar med "Övning"), `exempel`, `arbetsblad`, annars `begrepp`.
- **`arbetsblad` indexeras aldrig.** Det är blanketter.
- Bitens ID blir `<fil-id>#<rubrik>`. Byt därför inte namn på rubriker utan att höja `version`.

**Skrivregler för text som läggs till för hand:**

1. Vardagsspråk, fackord förklaras (samma regel som `GRUNDREGLER`).
2. Varje avsnitt ska gå att läsa fristående. Skriv aldrig "som vi sa ovan".
3. Listor i stället för tabeller. Bilder ersätts av en mening.
4. **Aldrig med i materialet:** diagnoser, medicinråd, doser, telefonnummer och krisinstruktioner. De ligger i `safety_config.py` och hämtas aldrig ur en databas.

## Vad konverteringen tar bort (och varför)

Modulerna är kopierade från en webbplattform och innehåller sådant som aldrig ska bli kunskap för boten. `convert_docx.py` tar bort det och redovisar vad i `data/_rapport.txt`:

| Borttaget | Varför |
|---|---|
| Menytext, "Logga ut", **deltagar-ID** | Plattformsrester. ID:t är en personuppgift. |
| Svarsfält ("Redigera ditt svar") och avsnitten "Kontakt med behandlare" och "Berätta om följande" | Formulär. De kan innehålla en persons egna svar och meddelanden. |
| **Tabeller** (100 st, utom 6) | Många är **ifyllda blanketter** med personers egna svar (datum, rädslor, mål, ångestnivåer). Bara 6 tabeller med programmets egen kunskap släpps igenom, omskrivna som listor: se `KEEP_TABLES_UNDER` i `convert_docx.py` (varje rad granskad för hand). Vill du lägga till en tabell, lägg dess rubrik där. |
| Bilder (70 st) | Går inte att söka i. |
| Sidfötter ("Kom ihåg!", "Bra jobbat med modulen!") och plattformsinstruktioner ("klicka på spara") | Inte kunskap. |

Resultat på de nio modulerna: **275 bitar**, median **199 ord**, minst 40 och störst 491. Fördelning: 251 begrepp, 22 övningar, 2 exempel.

## Materialet: krypterat paket i stället för text i repot

Modulernas text ska inte ligga som läsbar text i det publika repot. Därför:

- `data/` (de konverterade markdown-filerna) är avstängd i `.gitignore` och finns bara hos den som har Word-filerna.
- Det som följer med koden är **`material.enc`**: bitarna och deras vektorer, krypterade (Fernet/AES). Utan nyckeln är filen oläslig.
- Nyckeln heter `KNOWLEDGE_KEY`. Den ligger i `chat-engine/.env` (git ignorerar den) och som variabel i Railway. **Lägg den aldrig i git, Discord eller en skärmdump.**
- Saknas filen eller nyckeln är kunskapen avstängd och chatten svarar som förut. Det kraschar aldrig.

Vad det skyddar mot: att någon läser eller kopierar texten ur repot. Vad det **inte** skyddar mot: den som har nyckeln (alla med tillgång till Railway kan läsa variabeln). Håll därför nyckeln begränsad, och bestäm i teamet att appen och materialet inte säljs eller sprids vidare utan att alla är överens.

Modellen svarar dessutom med instruktionen att inte citera långa stycken ordagrant (se `build_system_prompt`).

## Köra

```bash
python chat-engine/knowledge/convert_docx.py "C:/sökväg/till/mappen/med/modulerna"   # Word -> markdown (data/)
python chat-engine/knowledge/chunker.py chat-engine/knowledge/data                    # statistik över bitarna
python chat-engine/knowledge/ingest.py --new-key        # en gång: skapar nyckeln (lägg i chat-engine/.env)
python chat-engine/knowledge/ingest.py --dry-run        # antal bitar, inga anrop
python chat-engine/knowledge/ingest.py                  # bäddar in (ett Gemini-anrop per bit) och skriver material.enc
python chat-engine/knowledge/evaluate.py                # mäter sökningen och föreslår MIN_SCORE
python chat-engine/tests/test_knowledge.py              # tester (påhittad text, utan nyckel)
python chat-engine/tests/test_retrieval.py              # tester av sökningen (fejkade vektorer)
```

## Så fungerar sökningen

1. Användaren skriver en KBT-fråga. Routern ser att det inte är kris och anropar `retrieve_fn`.
2. `knowledge_retriever.retrieve()` gör frågan till en vektor (`llm.embed`, ett Gemini-anrop) och jämför med alla bitar i paketet.
3. De upp till 4 bitar som liknar mest, och minst `MIN_SCORE`, skickas med som "KUNSKAPSUNDERLAG". Källan (modul och rubrik) följer med i svaret.
4. Är ingen bit tillräckligt lik skickas inget med, och boten svarar utan underlag.

Gamla motorn (`engine=legacy`) använder aldrig kunskapen, så jämförelsen i demon blir tydlig.

## Beslut och avvikelse från kortet

Kortet säger ChromaDB. Vi använder i stället en enkel sökning i minnet över det krypterade paketet, eftersom 275 bitar inte kräver en vektordatabas, Railway slipper en volym, inget tungt paket behövs, och paketet kan krypteras. Behöver materialet växa kraftigt går det att byta till ChromaDB eller pgvector bakom samma funktion (`retrieve()`).

## Kvar

1. Köra `ingest.py` lokalt och lägga `KNOWLEDGE_KEY` i Railway (den som har materialet).
2. Köra `evaluate.py` och sätta `MIN_SCORE` efter resultatet.
3. Visa källorna i Streamlit-teknikraden (valfritt).
