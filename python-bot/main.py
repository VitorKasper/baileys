from fastapi import FastAPI, Request
import requests
import os

from dotenv import load_dotenv
load_dotenv()

NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:9000/send")
PORT = int(os.getenv("PORTA_PYTHON", "9090"))
API_KEY = os.getenv("API_KEY", "")

app = FastAPI()


@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Este endpoint recebe todas as mensagens capturadas pelo Node.js.
    A regra de negócio do seu bot entra aqui!
    """
    data = await request.json()

    messages = data.get("messages", [])

    for msg in messages:
        if msg.get("key", {}).get("fromMe"):
            continue

        sender = msg.get("key", {}).get("remoteJidAlt", "").split("@")[0]

        text = ""
        message_content = msg.get("message", {})
        if "conversation" in message_content:
            text = message_content["conversation"]
        elif "extendedTextMessage" in message_content:
            text = message_content["extendedTextMessage"].get("text", "")

        if sender and text:
            print(f"📩 Nova mensagem de {sender}: {text}")

            # --- SUA REGRA DE NEGÓCIO AQUI ---
            if text.lower() == "oi":
                enviar_mensagem(sender, "Olá! Sou um bot de demonstração em Python 🐍")
            elif text.lower() == "ping":
                enviar_mensagem(sender, "Pong! 🏓")
            # ---------------------------------

    return {"status": "ok"}


def enviar_mensagem(numero: str, texto: str):
    """Envia uma mensagem de texto via API Node.js."""
    payload = {"number": numero, "text": texto}
    headers = {"x-api-key": API_KEY} if API_KEY else {}
    try:
        response = requests.post(NODE_API_URL, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ Mensagem enviada para {numero}")
        else:
            print(f"❌ Erro ao enviar: {response.text}")
    except Exception as e:
        print(f"❌ Erro de conexão com a API Node: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
