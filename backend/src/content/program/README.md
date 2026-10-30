# Övningsprogrammet: innehåll (PLAN-92)

Tolv filer, `week-01.md` till `week-12.md`. Varje fil är en vecka: YAML mellan två `---`-rader (rubrik, övningar, reflektionsfråga, förslag på chattfrågor) och därefter veckans teori som vanlig markdown.

> **Status: utkast.** Texterna är skrivna med egna ord utifrån KBT-principerna i CHAI-modulerna, och är **inte klinisk granskade**. Programmet syns för alla inloggade (`USER_NAV_ITEMS` i `frontend/src/components.py`) men inte för besökare utan konto, och intro-sidan säger att texterna är ett utkast. CHAI-modulernas egen text ska aldrig kopieras hit; den ligger krypterad i `chat-engine/knowledge/`.

## Format

```yaml
week: 3                      # måste matcha filnamnet
title: "Tankefällor"
summary: "En mening som visas på översikten."
minutes: 25                  # ungefär hur lång veckan är
safety_note: "Valfri säkerhetsruta överst."
exercises:
  - id: w03-namnge           # w + veckonummer + "-" + namn, unikt i hela programmet
    title: "Namnge tankefällorna"
    kind: ovning             # reflektion | tankedagbok | ovning | experiment | exponering
    required: true           # obligatoriska övningar måste vara gjorda för att veckan ska kunna avslutas
    minutes: 15
    why: "Varför övningen är bra."
    task: "En tydlig mening om vad man ska göra och skriva ner."   # visas först i övningen
    write_label: "Vad anteckningsrutan ber om"                       # valfri
    steps: ["Steg 1", "Steg 2"]
    measure_label: "Valfri fråga som ger Före/Efter-skattning 0–100"
reflection_prompt: "Frågan som avslutar veckan."
chat_tips: ["Förslag på frågor man kan ställa i chatten"]
```

## Riktmärken (testas i `chat-engine/tests/test_program.py`)

Högst 250 ord teori, 3 övningar och 45 minuter per vecka, så att ingen blir överväldigad. Alla tolv veckor måste finnas, och övnings-id:n får inte återanvändas (sparade svar pekar på dem, så byt aldrig id på en övning som någon kan ha gjort).
