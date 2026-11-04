<p align="center">
  <img src="frontend/src/assets/logo-mark.png" alt="Fickologen" width="120">
</p>

<h1 align="center">Fickologen</h1>

<p align="center">
  En varm och trygg KBT-inspirerad stödapp: chatta, skriv dagbok och gå ett tolvveckorsprogram i din egen takt.
</p>

---

> **Studentprojekt, inte vård.** Fickologen ersätter inte kontakt med vården. Kristexter, telefonnummer och programtexter är **utkast som inte är kliniskt granskade**. Vid akut fara: ring 112. Vid frågor om din hälsa: 1177.

## Innehåll

- [Vad appen gör](#vad-appen-gör)
- [Arkitektur](#arkitektur)
- [Kom igång lokalt](#kom-igång-lokalt)
- [Miljövariabler](#miljövariabler)
- [Tester](#tester)
- [Säkerhet och integritet](#säkerhet-och-integritet)
- [Projektstruktur](#projektstruktur)
- [Mer dokumentation](#mer-dokumentation)

## Vad appen gör

| Del | Beskrivning |
|---|---|
| **Chatt** | Samtal med en AI-assistent som bygger på KBT-principer. En router avgör först vad slags meddelande det är. Kris och känsliga ämnen får fasta, granskningsbara texter med hjälplinjer, och AI:n svarar bara på vanliga KBT-frågor och samtal. |
| **Sparade chattar** | Tidigare samtal går att öppna igen, byta namn på och ta bort. |
| **Dagbok** | Anteckningar med humör för dagen. |
| **12 veckor KBT** | Ett övningsprogram med teori, övningar och reflektion vecka för vecka. Framstegen sparas per konto, och chatten kan få veckans innehåll som sammanhang. Valfria påminnelser via e-post på söndagar. |
| **Trygghet & integritet** | Hjälplinjer, vad appen kan och inte kan, och hur data hanteras. |
| **Konto** | Profil, återställningskod, export av egen data och radering av data eller hela kontot. |
| **Hantera konton** | Endast för administratörer. |

Chatten är i stängd beta. Besökare utan konto ser startsidan och sidan om trygghet och integritet. Chatt, dagbok, sparade chattar och programmet kräver inloggning.

## Arkitektur

```
 Webbläsare
     │
     ▼
 frontend/  Streamlit (gränssnittet)
     │  HTTP (BACKEND_URL)
     ▼
 backend/   FastAPI + SQLAlchemy ──► PostgreSQL (Alembic-migreringar)
     │
     ▼
 chat-engine/  router, prompter, krisregler, kunskapssökning (RAG) ──► Google Gemini
```

- **Frontend:** Streamlit med egen design i `frontend/src/assets/style.css`. Temat är låst till ljust i `frontend/src/.streamlit/config.toml`, oavsett webbläsarens inställning.
- **Backend:** FastAPI med JWT-inloggning. API-dokumentationen finns på `/docs` när servern kör.
- **Chattmotor:** routern i tre lager (regler, klassificering, hanterare). Principen är att ju allvarligare ämnet är, desto mindre får AI:n improvisera. Se [chat-engine/README.md](chat-engine/README.md).
- **Språkmodell:** Google Gemini via `google-genai`. All kod som pratar med modellen ligger i `chat-engine/llm.py`.

## Kom igång lokalt

**Krav:** Python 3.11 eller senare och en PostgreSQL-databas. För snabba lokala tester går det också att använda SQLite, till exempel `DATABASE_URL=sqlite:///fickologen.db`.

```bash
# 1. Klona och installera
git clone https://github.com/Agila-Gruppen/fickologen.git
cd fickologen
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Konfigurera
cp .env.example .env             # fyll i värdena, se nedan

# 3. Skapa tabellerna i databasen
cd backend
alembic upgrade head
cd ..

# 4. Starta backend (från repots rot)
uvicorn backend.src.main:app --reload --port 8000

# 5. Starta frontend (i en ny terminal, från repots rot)
streamlit run frontend/src/app.py
```

Appen öppnas på <http://localhost:8501>. Utan `GEMINI_API_KEY` startar appen, men chatten kan inte svara med AI.

Repot har också en devcontainer (`.devcontainer/`) för GitHub Codespaces som installerar beroendena och startar frontend automatiskt.

### Administratörer

Användarnamn som listas i `ADMIN_USERNAMES` (kommaseparerade) får administratörsroll varje gång backend startar. Tas ett namn bort från listan förlorar kontot rollen.

## Miljövariabler

Alla variabler finns i [.env.example](.env.example). Lägg dem i `.env` i repots rot. Filen ignoreras av git.

| Variabel | Krävs | Beskrivning |
|---|---|---|
| `DATABASE_URL` | Ja | Anslutning till databasen. |
| `SECRET_KEY` | Ja | Signerar inloggningstoken (JWT). |
| `DATA_ENCRYPTION_KEY` | Ja | Fernet-nyckel som krypterar dagbok och chattmeddelanden. **Tappas nyckeln går den datan inte att läsa.** Se `.env.example` för hur nyckeln skapas och byts. |
| `GEMINI_API_KEY` | För chatten | Nyckel till Google Gemini. |
| `BACKEND_URL` | Nej | Var frontend når backend. Standard är `http://localhost:8000`. |
| `ADMIN_USERNAMES` | Nej | Kommaseparerade användarnamn med administratörsroll. |
| `KNOWLEDGE_KEY` | Nej | Låser upp det krypterade kunskapsmaterialet för RAG. Utan nyckeln är kunskapssökningen avstängd och chatten svarar ändå. |
| `SMTP_*`, `APP_URL`, `REMINDER_*` | Nej | Påminnelser via e-post. Lämna `SMTP_HOST` tomt för att stänga av dem. |

Skapa en krypteringsnyckel med:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Tester

Testerna ligger i `chat-engine/tests/` och körs som vanliga Python-skript från repots rot. De använder fejkad Gemini och en tillfällig SQLite-databas, så ingen nyckel eller server behövs.

```bash
python chat-engine/tests/test_router.py
python chat-engine/tests/test_program_ui.py
```

Kör alla:

```bash
for f in chat-engine/tests/test_*.py; do python "$f" || echo "FEL i $f"; done
```

Använd bara **påhittad data** när ni provar mot den riktiga Gemini-nyckeln.

## Säkerhet och integritet

- **Kryptering i databasen:** dagboksanteckningar och chattmeddelanden krypteras med `DATA_ENCRYPTION_KEY` innan de sparas.
- **Lösenord** lagras som bcrypt-hashar.
- **Krishantering utan AI:** fraser som alltid betyder allvar fångas av regler och får en fast kristext direkt. Efter en kris svarar chatten försiktigt i tre turer. Listorna finns i `chat-engine/safety_config.py`.
- **Kunskapsmaterialet** (behandlingsmodulerna) ligger inte som läsbar text i repot, bara krypterat i `chat-engine/knowledge/material.enc`.
- **Hemligheter** (`.env`, nycklar) ska aldrig in i git, i chattar eller i skärmdumpar.

## Projektstruktur

```
fickologen/
├── frontend/src/
│   ├── app.py                 # startpunkt för Streamlit
│   ├── components.py          # meny, sidhuvuden och delade komponenter
│   ├── views/                 # en fil per sida
│   ├── assets/                # stilmall och logotyp
│   └── .streamlit/config.toml # tema (alltid ljust)
├── backend/
│   ├── src/
│   │   ├── main.py            # FastAPI-appen
│   │   ├── routes/            # API-endpoints
│   │   ├── models/, schemas/  # databasmodeller och API-scheman
│   │   ├── services/          # chatt, export, påminnelser, sökning
│   │   └── content/program/   # programmets tolv veckor (markdown)
│   └── alembic/               # databasmigreringar
├── chat-engine/
│   ├── router.py, prompts.py, safety_config.py, llm.py
│   ├── knowledge/             # RAG: konvertering, uppdelning, krypterat paket
│   └── tests/
├── requirements.txt
└── .env.example
```

## Mer dokumentation

- [chat-engine/README.md](chat-engine/README.md): routern, kategorierna och promptmodulerna.
- [chat-engine/knowledge/README.md](chat-engine/knowledge/README.md): kunskapsmaterialet och sökningen.
- [backend/src/content/program/README.md](backend/src/content/program/README.md): formatet för programveckorna.
- [chat-engine/prompt-iteration-log.md](chat-engine/prompt-iteration-log.md): hur prompterna har utvecklats.
