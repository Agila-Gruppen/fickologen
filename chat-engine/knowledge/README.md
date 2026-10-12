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

## Materialet ligger utanför git

`data/` är avstängd i `.gitignore`. Det betyder:

- Word-filerna och de konverterade filerna **finns bara på din dator**. Ingen annan i teamet har dem.
- **Railway hämtar koden från GitHub**, så servern har inte materialet. För att RAG ska fungera live måste det finnas ett sätt att få dit det (se PLAN-113). Det går också att checka in de färdiga markdown-filerna när ni har bestämt att det är okej.
- Den som kör `convert_docx.py` lokalt får samma resultat, men behöver Word-filerna.

## Köra

```bash
python chat-engine/knowledge/convert_docx.py "C:/sökväg/till/mappen/med/modulerna"
python chat-engine/knowledge/chunker.py chat-engine/knowledge/data
python chat-engine/tests/test_knowledge.py
```

## Kvar för PLAN-113

1. Embedding-modell (Gemini eller lokal) och test på svenska.
2. Var indexet ska bo på Railway (volym, bygga om vid start, eller förberäknat).
3. `retrieve_context()` i `backend/src/services/retrieval.py`: sök, och returnera inget vid svag träff.
4. En testmängd med 15–20 frågor och förväntat avsnitt.
5. (klart) Tabellerna är granskade, se `KEEP_TABLES_UNDER`.
