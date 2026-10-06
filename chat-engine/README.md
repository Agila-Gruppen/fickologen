# chat-engine: Fickologens chattmotor

> Status: routern är klar och testad (PLAN-62, PR #6). Den är **inte inkopplad i backenden än**, det sker i en separat PR. Texter och telefonnummer är **utkast** som behöver klinisk granskning.

## Kort version

Förut svarade boten på alla meddelanden med samma 9-stegsmall, även på "." och "tack". Nu avgör en **router** först *vad slags meddelande* det är och hur det ska hanteras:

1. **Regler** fångar kris, "tack", "." och frågor om boten, utan AI.
2. **Gemini klassificerar** övriga meddelanden i en kategori.
3. **En hanterare per kategori** svarar. Kris och känsliga ämnen får **fasta, granskade texter**. Gemini skriver bara svar på vanliga KBT-frågor, korta svar och övrigt.

Principen: ju allvarligare ämne, desto mindre får AI:n improvisera.

## Så fungerar det

```
meddelande
   │
   ▼
Lager 0  Regler (ingen AI)
   ├─ hård krislista träffar  → kristext direkt + försiktigt läge i 3 turer
   ├─ "tack", "hej", "."      → kort fast svar
   └─ "är du en människa?"    → fast ärligt svar (META)
   │ ingen träff
   ▼
Lager 1  Gemini klassificerar (ett ordsvar: kategorin)
   │      (klassificeraren nere eller osäker → reservregler, hellre försiktig än slarvig)
   ▼
Lager 2  Hanterare
   ├─ kris- och känsliga kategorier → fast text med hjälplinjer
   └─ KBT_DELNING / KORT_SVAR / OVRIGT → Gemini med rätt promptmodul
```

### Kategorier

| Typ | Kategorier | Svar |
|---|---|---|
| Kris | SJALVSKADA, VALD_MOT_ANDRA, VALD_MOT_MIG, OROAD_FOR_ANNAN | Fast text med 112 och hjälplinjer. Sätter försiktigt läge i 3 turer. |
| Känsliga | OVERGREPP_TIDIGARE (sätter också försiktigt läge), BEGATT_BROTT, SEXUELLA_TANKAR_BARN, MISSBRUK, UTANFOR_OMRADE, META | Fast text som hänvisar rätt |
| LLM | KBT_DELNING, KORT_SVAR, OVRIGT | Gemini svarar med modul kbt, latt eller ovrigt |
| Interna | TOMT, HEJ, TACK, HEJ_DA, RISK_UPPFOLJNING, OSAKER, FALLBACK | Kort fast text |

### Hård och mjuk lista

- **Hård lista** (`HARDA_MONSTER`): fraser som alltid betyder allvar, till exempel "ta livet av mig". Träff ger kristext direkt, utan AI.
- **Mjuk lista** (`MJUKA_MONSTER`): enstaka ord som *kan* betyda allvar men ofta inte gör det ("dö", "alkohol", "brott", "orkar inte mer"). En träff är bara en **ledtråd till klassificeraren**. Om klassificeraren inte svarar används den försiktiga reservtexten.

Exempel: "jag vill dö" larmar direkt. "Jag ville dö av skam" larmar inte, utan klassificeraren avgör.

### Promptmoduler (`prompts.py`)

`GRUNDREGLER` gäller alltid ("du är en AI", "anta aldrig något om användaren", ...). Därefter läggs en modul till: `kbt` (mallen), `latt` (kort svar), `ovrigt`, eller `forsiktig` (de tre turerna efter en kris).

### Backend utan minne

Backenden får hela samtalet vid varje anrop. `state_from_history()` återskapar därför det försiktiga läget ur historiken (har boten nyligen skickat en kristext?).

### Om något går fel

Gemini nere, blockerat eller tomt svar ger en vänlig reservtext med 112/1177. Boten kraschar aldrig tyst.

## Filer

| Fil | Innehåll |
|---|---|
| `safety_config.py` | **Krisordlistan**: kategorier, mönster, hjälplinjer, alla fasta texter |
| `router.py` | `route()`: själva routingen |
| `prompts.py` | Promptmodulerna |
| `llm.py` | All kod som pratar med Gemini (byter vi leverantör ändras bara denna) |
| `prototype.py` | Terminalchatt med debugrad |
| `tests/test_router.py` | 26 tester med fejkad Gemini |

## Köra och testa

```bash
python chat-engine/tests/test_router.py   # ingen nyckel behövs
python chat-engine/prototype.py           # kräver GEMINI_API_KEY i chat-engine/.env
```

Använd bara **påhittad data** när ni provar mot Gemini (gratisnivån kan använda indata).

## RAG: vad som är kvar

Routern är förberedd. `route()` tar en `retrieve_fn` som anropas **bara** i KBT-hanteraren (aldrig vid kris), och `build_system_prompt(modul, kontext)` lägger in underlaget med regeln "hitta inte på". Kvar (PLAN-113):

1. Få fram texten ur de 9 modulerna och kontrollera att vi får använda den.
2. Dela upp texten i bitar med metadata (modul, kapitel).
3. Välja embedding-modell (Gemini eller lokal) och testa svenska.
4. Bygga ChromaDB-index, och se till att det överlever omstart på Railway.
5. Fylla i `retrieve_context()` i `backend/src/services/retrieval.py`. Returnera inget vid låg likhet.
6. Skriva en utvärderingsmängd (frågor med förväntat avsnitt).

Inget i routern behöver ändras för det.

## Kända begränsningar

- Hårda listan är en startpunkt, inte en garanti. Utöka den med fall från teamet (varje fall blir ett test).
- Varje icke-trivialt meddelande kostar ett extra Gemini-anrop (klassificeringen).
- Alla texter och nummer är utkast (`VERIFIERAD = None` i `safety_config.py`).
