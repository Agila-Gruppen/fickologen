"""Säkerhets- och routingkonfiguration för Fickologens chattmotor.

VIKTIGT: Allt här är ett UTKAST. Innan riktiga användare får tillgång ska
  1. texterna granskas av någon med klinisk kompetens (lärare/handledare)
  2. varje telefonnummer verifieras och datum fyllas i nedan
Håll all text och alla nummer HÄR, aldrig inbakat i en prompt.
"""

VERIFIERAD = None  # fyll i t.ex. "2026-10-06" när numren kontrollerats

HJALPLINJER = {
    "akut": "112",
    "vard": "1177",
    "sjalvmordslinjen": "90101",
    "kvinnofrid": "020-50 50 50",
    "bris": "116 111",
    "polisen": "114 14",
    "brottsofferjouren": "0200-21 20 19",
    "preventell": "020-66 77 88",
    "alkohollinjen": "020-84 44 48",
    "droglinjen": "020-91 91 91",
}
H = HJALPLINJER

# ---------------------------------------------------------------- kategorier
# Kategorier som klassificeraren (Lager 1) får välja mellan.
KRIS_KATEGORIER = ("SJALVSKADA", "VALD_MOT_ANDRA", "VALD_MOT_MIG", "OROAD_FOR_ANNAN")
KANSLIGA_KATEGORIER = ("OVERGREPP_TIDIGARE", "BEGATT_BROTT", "SEXUELLA_TANKAR_BARN",
                       "MISSBRUK", "UTANFOR_OMRADE", "META")
LLM_KATEGORIER = ("KBT_DELNING", "KORT_SVAR", "OVRIGT")
KATEGORIER = KRIS_KATEGORIER + KANSLIGA_KATEGORIER + LLM_KATEGORIER

# Efter dessa går boten in i "försiktigt läge" i några turer.
FORSIKTIGA_KATEGORIER = KRIS_KATEGORIER + ("OVERGREPP_TIDIGARE",)
RISK_TURNS = 3

# Vilken promptmodul varje LLM-kategori använder (se prompts.py).
MODUL_FOR = {"KBT_DELNING": "kbt", "KORT_SVAR": "latt", "OVRIGT": "ovrigt"}

KATEGORIBESKRIVNING = """\
SJALVSKADA: personen uttrycker självmordstankar, självskada eller att inte vilja leva
VALD_MOT_ANDRA: personen har tankar på eller avsikt att skada andra
VALD_MOT_MIG: personen utsätts just nu för våld, hot eller övergrepp, eller är rädd för någon
OROAD_FOR_ANNAN: personen är orolig för att någon annan mår mycket dåligt eller är i fara
OVERGREPP_TIDIGARE: personen har tidigare utsatts för övergrepp eller sexuellt våld
BEGATT_BROTT: personen berättar att den har begått ett brott
SEXUELLA_TANKAR_BARN: sexuella tankar om barn
MISSBRUK: alkohol, droger, spel eller läkemedel som ett problem
UTANFOR_OMRADE: medicin, dosering, diagnos, psykos, ätstörning och liknande
META: frågor om boten, att den är en AI, eller om hur data sparas
KORT_SVAR: mycket kort svar (ja, nej, ok, vet inte) som hör ihop med botens förra fråga
KBT_DELNING: personen delar en tanke, händelse eller fråga om sitt mående eller sin ångest
OVRIGT: allt annat (småprat, off-topic, kritik av boten, vill prata med en människa)"""

# ------------------------------------------------- Lager 0: regler (utkast!)
# HÅRD lista: träff => krishandler direkt, utan LLM. Hellre falsklarm än missad
# kris. OBS: personer med social ångest säger ofta "jag vill dö av skam", så
# "vill dö av ..." är undantaget (avgörs av klassificeraren). Ett fristående
# "jag vill dö" larmar dock. Diskutera den avvägningen med klinisk granskare.
HARD_PRIORITET = ["SJALVSKADA", "VALD_MOT_ANDRA", "VALD_MOT_MIG",
                  "OVERGREPP_TIDIGARE", "SEXUELLA_TANKAR_BARN", "OROAD_FOR_ANNAN"]

_PERSONER = (r"(honom|henne|dem|någon( annan)?|folk|alla|andra|"
             r"min (chef|man|fru|sambo|partner|pojkvän|flickvän|syster|bror|mamma|pappa|kollega|granne|lärare)|"
             r"mitt barn|mina barn)")
_NARSTAENDE = (r"(vän|väninna|kompis|syster|bror|mamma|pappa|partner|sambo|"
               r"flickvän|pojkvän|man|fru|dotter|son|kollega|klasskompis|kurskamrat)")

HARDA_MONSTER = {
    "SJALVSKADA": [
        r"\bta livet av mig\b",
        r"\bta mitt (eget )?liv\b",
        r"\b(vill|vilja|orkar) inte (leva|finnas)\b",
        r"\bvill (bara )?dö\b(?! av\b)",  # "vill dö av skam" avgörs av klassificeraren
        r"\bförsvinna för alltid\b",
        r"\bbättre (om jag inte fanns|utan mig)\b",
        r"\b(skada|skära|döda) mig( själv)?\b",
        r"\bskär mig\b",
        r"\b(har|får) (självmords|självskade)tankar\b",
        r"\btagit för många (tabletter|piller)\b",
        r"\b(tog|tagit|ta) en överdos\b",
    ],
    "VALD_MOT_ANDRA": [
        r"\b(skada|döda|slå ihjäl|mörda|knivhugga|skjuta ihjäl) " + _PERSONER + r"\b",
    ],
    "VALD_MOT_MIG": [
        r"\b(slår|misshandlar|våldtar|hotar) mig\b",
        r"\bjag (är|känner mig) inte säker hemma\b",
    ],
    "OVERGREPP_TIDIGARE": [
        r"\b(våldtog|misshandlade|förgrep sig på|antastade|tafsade på) mig\b",
        r"\b(blev|har blivit|är) (våldtagen|sexuellt utnyttjad)\b",
        r"\butsatt för (ett |sexuella |sexuellt )?(övergrepp|våldtäkt|våld)\b",
    ],
    "SEXUELLA_TANKAR_BARN": [
        r"\bjag är pedofil\b",
        r"\bsexuellt attraherad (av|till) barn\b",
        r"\bsexuella (tankar|fantasier) (om|kring|mot|på) barn\b",
    ],
    "OROAD_FOR_ANNAN": [
        r"\b(min|mitt) " + _NARSTAENDE +
        r"\b.{0,50}\b(ta livet av sig|självmord|skada sig|vill dö|inte leva)\b",
    ],
}

# MJUK lista: träff => bara en hint till klassificeraren, och försiktig
# reservhantering om klassificeraren inte kan svara.
MJUKA_MONSTER = [
    r"\bdö\b", r"\bdöd(a|ar|en)?\b", r"\bsjälvmord\w*", r"\bsjälvskad\w*",
    r"\bta livet\b", r"\btabletter\b", r"\böverdos\b", r"\bvåld\w*",
    r"\b(slår|slog|slå ihjäl)\b", r"\bhot(ar|ade|ad|et)\b", r"\bövergrepp\b",
    r"\bvåldtäkt\b", r"\bvåldtog\b", r"\bvåldtagen\b", r"\bbrott\b",
    r"\bpolis\w*", r"\bdroger?\b", r"\bknark\w*", r"\balkohol\b", r"\bdricker\b",
    r"\borkar inte mer\b", r"\bge upp\b", r"\bmeningslös\w*", r"\bförsvinna\b",
    r"\bpedofil\w*",
]

# Frågor om boten/appen. Svaret är fast, så att LLM:en inte gissar om datahantering.
META_MONSTER = [
    r"\bär du (en )?(människa|robot|ai|riktig person|psykolog|terapeut)\b",
    r"\b(sparas|sparar du|lagras|lagrar du)\b",
    r"\bvem (ser|läser) (det här|detta|mina (svar|samtal|meddelanden))\b",
]

# Triviala meddelanden: fast kort svar, ingen LLM, ingen KBT-mall.
TRIVIALA_MONSTER = {
    "HEJ_DA": r"^(hej då|adjö|vi hörs|ha det bra|hörs senare|vi ses)$",
    "TACK": r"^(tusen )?tack( så mycket| för hjälpen| för idag| för det| igen)?$",
    "HEJ": r"^(hej|hejsan|hallå|tjena|hej igen|god morgon|god kväll|god dag)$",
}

# --------------------------------------------------- Fasta svar (UTKAST!)
FASTA_SVAR = {
    "SJALVSKADA": (
        "Tack för att du berättar det här. Det krävs mod.\n\n"
        "Jag är en AI och kan inte ge dig det stöd du behöver just nu, men du "
        "förtjänar att få prata med en människa direkt.\n\n"
        f"Är du i akut fara, eller har du gjort något du är orolig för? Ring {H['akut']} nu.\n"
        f"Vill du prata med någon: Självmordslinjen {H['sjalvmordslinjen']}, "
        f"eller {H['vard']} för råd och stöd.\n\n"
        "Om det går, berätta för någon som finns nära dig hur du mår, och försök "
        "att inte vara ensam just nu. Jag finns kvar här om du vill skriva."
    ),
    "VALD_MOT_ANDRA": (
        "Det du skriver låter allvarligt, och det är bra att du sätter ord på det. "
        "Jag är en AI och kan inte hjälpa dig med det här på rätt sätt, men en människa kan det.\n\n"
        f"Riskerar du att skada någon, eller är någon i fara just nu: ring {H['akut']}.\n"
        "Känner du att du håller på att tappa kontrollen: ta avstånd från situationen "
        f"eller personen om du kan, och kontakta {H['vard']} för att få prata med någon redan idag.\n\n"
        "Om det är tankar som kommer av sig själva och som du inte vill ha, är det "
        "vanligare än många tror, och det går att få hjälp med. Berätta gärna mer om "
        "hur det är för dig."
    ),
    "VALD_MOT_MIG": (
        "Tack för att du berättar. Ingen ska behöva vara rädd, och det du beskriver är allvarligt.\n\n"
        f"Är du i fara just nu: ring {H['akut']}.\n"
        "För stöd och rådgivning:\n"
        f"- Kvinnofridslinjen {H['kvinnofrid']} (stöd vid våld och hot)\n"
        f"- Polisen {H['polisen']} (när det inte är akut)\n"
        f"- Är du under 18: BRIS {H['bris']}\n\n"
        "Handlar det om ett barn som far illa: kontakta socialtjänsten eller polisen, "
        f"och ring {H['akut']} vid akut fara."
    ),
    "OROAD_FOR_ANNAN": (
        "Det är tungt att vara orolig för någon man bryr sig om, och fint att du vill hjälpa. "
        "Några saker som brukar hjälpa: fråga rakt ut hur personen mår, lyssna utan att "
        "försöka fixa, och stanna kvar hos personen om det går.\n\n"
        f"Är personen i akut fara: ring {H['akut']}. Självmordslinjen {H['sjalvmordslinjen']} "
        "finns också för dig som är orolig för någon annan. Du behöver inte bära det här ensam."
    ),
    "OVERGREPP_TIDIGARE": (
        "Tack för att du litar på mig med det här. Det som hände var inte ditt fel, och det "
        "du känner är begripligt. Du behöver inte berätta mer än du vill.\n\n"
        "Jag är en AI och inte rätt plats för att bearbeta något så tungt, men det finns "
        "människor som kan:\n"
        f"- Brottsofferjouren {H['brottsofferjouren']}\n"
        f"- Kvinnofridslinjen {H['kvinnofrid']}\n"
        f"- {H['vard']} eller din vårdcentral (studenthälsan om du studerar)\n\n"
        f"Är du i fara just nu, eller har det precis hänt: ring {H['akut']}.\n"
        "Du bestämmer takten. Jag finns kvar här om du vill skriva om hur du mår just nu."
    ),
    "BEGATT_BROTT": (
        "Tack för att du är ärlig. Jag dömer dig inte, men jag är en AI och kan varken ge "
        "juridisk rådgivning eller lova att det här stannar hos mig.\n\n"
        "Det kan hjälpa att prata med en jurist, eller med någon professionell som kan "
        f"hantera situationen på riktigt. Är någon i fara just nu, eller riskerar du att skada någon: ring {H['akut']}. "
        f"Mår du dåligt över det som hänt kan du kontakta {H['vard']}."
    ),
    "SEXUELLA_TANKAR_BARN": (
        "Tack för att du vågar säga det. Det här är något jag inte kan prata om i detalj, "
        "och jag är en AI och inte rätt stöd för det. Men det finns hjälp för dig som vill "
        f"få stöd att aldrig agera på sådana tankar: Preventell {H['preventell']} är en stödlinje.\n\n"
        f"Om ett barn far illa just nu: kontakta polisen, och ring {H['akut']} vid akut fara."
    ),
    "MISSBRUK": (
        "Tack för att du berättar, det är inte lätt att prata om. Jag dömer inte, och jag är "
        "glad att du tar upp det.\n\n"
        "Det ligger utanför vad jag kan hjälpa till med som AI, men det finns stöd:\n"
        f"- Alkohollinjen {H['alkohollinjen']}\n"
        f"- Droglinjen {H['droglinjen']}\n"
        f"- {H['vard']} eller din vårdcentral\n\n"
        f"Vid akut fara, till exempel en överdos: ring {H['akut']}."
    ),
    "UTANFOR_OMRADE": (
        "Det där är en viktig fråga, men jag är en AI och kan inte ge medicinsk rådgivning "
        "eller ställa diagnoser, och jag vill inte gissa. Prata med din läkare eller "
        f"vårdcentral, eller ring {H['vard']} för råd. Vill du berätta hur det känns för dig "
        "just nu, så finns jag här."
    ),
    "META": (
        "Jag är en AI, inte en människa eller psykolog. Hur dina samtal sparas och vem som "
        "kan se dem avgörs av appen och inte av mig, så jag vill inte gissa. Fråga teamet "
        "bakom Fickologen, så kan de berätta exakt."
    ),
    # Interna kategorier (väljs av regler/reservlogik, inte av klassificeraren):
    "TOMT": "Jag finns här. Vill du skriva något, eller bara vara en stund?",
    "HEJ": "Hej! Fint att du är här. Hur är det med dig just nu?",
    "TACK": "Varsågod. Det var fint att få vara med. Du är välkommen tillbaka när du vill.",
    "HEJ_DA": "Ta hand om dig. Jag finns här när du vill prata igen.",
    "RISK_UPPFOLJNING": (
        "Tack för att du skrev. Jag undrar fortfarande hur du har det just nu. "
        f"Har du någon nära dig som du kan vara med? Är du i akut fara: ring {H['akut']}, "
        f"eller Självmordslinjen {H['sjalvmordslinjen']}."
    ),
    "OSAKER": (
        "Tack för att du skriver. Jag vill förstå dig rätt: mår du så dåligt att du är i fara, "
        f"eller kan någon annan vara i fara? Ring då {H['akut']} direkt. "
        "Annars: berätta gärna mer med egna ord, så följer jag med."
    ),
    "FALLBACK": (
        "Tack för att du skriver. Jag har svårt att svara på det just nu. Vill du försöka "
        f"formulera det på ett annat sätt? Är du i akut fara, ring {H['akut']}, "
        f"eller kontakta {H['vard']}."
    ),
}
