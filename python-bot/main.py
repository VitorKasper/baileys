from fastapi import FastAPI, Request
import requests
import os

from dotenv import load_dotenv
load_dotenv()

PORTA_BAILEYS = os.getenv("PORTA_BAILEYS", "9000")
NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:9000/send")
PORT = os.getenv("PORTA_PYTHON", "9090")

app = FastAPI()

# URL da API Node.js (Baileys)

@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Este endpoint recebe todas as mensagens capturadas pelo Node.js.
    A regra de negócio do seu bot entra aqui!
    """
    data = await request.json()
    
    # O Baileys envia um array de mensagens dentro de 'messages'
    messages = data.get("messages", [])
    
    for msg in messages:
        # Verifica se não é uma mensagem enviada por você mesmo (evita loop infinito)
        if msg.get("key", {}).get("fromMe"):
            continue
            
        # Extrai o número de quem enviou e o texto da mensagem
        sender = msg.get("key", {}).get("remoteJidAlt", "").split("@")[0]
        
        # Tenta pegar o texto de mensagens simples ou de mensagens com botões/listas
        text = ""
        message_content = msg.get("message", {})
        if "conversation" in message_content:
            text = message_content["conversation"]
        elif "extendedTextMessage" in message_content:
            text = message_content["extendedTextMessage"].get("text", "")
            
        if sender and text:
            print(f"📩 Nova mensagem de {sender}: {text}")
            
            # --- SUA REGRA DE NEGÓCIO AQUI ---
            # Exemplo de Auto-Resposta simples:
            if text.lower() == "oi":
                enviar_mensagem(sender, "Olá! Sou um bot de demonstração em Python 🐍")
            elif text.lower() == "ping":
                enviar_mensagem(sender, "Pong! 🏓")
            # ---------------------------------

    return {"status": "ok"}

def enviar_mensagem(numero: str, texto: str):
    """
    Função auxiliar para enviar comandos para o nosso Node.js
    """
    payload = {
        "number": numero,
        "text": texto
    }
    try:
        response = requests.post(NODE_API_URL, json=payload)
        if response.status_code == 200:
            print(f"✅ Mensagem enviada para {numero}")
        else:
            print(f"❌ Erro ao enviar: {response.text}")
    except Exception as e:
        print(f"❌ Erro de conexão com a API Node: {e}")

if __name__ == "__main__":
    import uvicorn
    # Roda o servidor na porta 8000
    uvicorn.run(app, host="0.0.0.0", port=PORT)