import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

with open("chat-engine/prompt_v1.txt", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

print("Fickologen-prototyp. Skriv 'exit' för att avsluta.\n")
history = []
while True:
    user_msg = input("Du: ")
    if user_msg.lower() == "exit":
        break
    history.append({"role": "user", "parts": [{"text": user_msg}]})
    resp = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=history,
        config={"system_instruction": SYSTEM_PROMPT},
    )
    print(f"\nBot: {resp.text}\n")
    history.append({"role": "model", "parts": [{"text": resp.text}]})