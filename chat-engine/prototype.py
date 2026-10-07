"""Terminalprototyp med routing. Kör: python chat-engine/prototype.py"""
import logging

import llm
from router import SessionState, route


def main():
    logging.basicConfig(level=logging.WARNING, format="[varning] %(message)s")
    logging.getLogger("google_genai").setLevel(logging.ERROR)  # tysta ofarliga SDK-varningar
    state = SessionState()
    historik = []
    print("Fickologen-prototyp v2 (med routing). Skriv 'exit' för att avsluta.\n")
    while True:
        meddelande = input("Du: ").strip()
        if meddelande.lower() == "exit":
            break
        if not meddelande:
            meddelande = "."
        svar = route(meddelande, historik, state,
                     classify_fn=llm.classify, generate_fn=llm.generate)
        print(f"\n[debug: {svar.category} via {svar.source}, llm={svar.llm_used}]")
        print(f"Bot: {svar.text}\n")
        historik.append({"role": "user", "text": meddelande})
        historik.append({"role": "bot", "text": svar.text})


if __name__ == "__main__":
    main()
