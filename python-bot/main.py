import os
import threading

from fastapi import FastAPI, Request

from dotenv import load_dotenv
load_dotenv()

from run_auditoria_integracao import iniciar_loop_auditoria

PORT = int(os.getenv("PORTA_PYTHON", "9090"))

app = FastAPI()


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Recebe as mensagens capturadas pelo Node.js, mas apenas as ignora:
    este bot não reage a mensagens, só envia os relatórios de auditoria
    de integração (via NotificacaoService, disparado pelo loop em background)."""
    await request.json()
    return {"status": "ok"}


@app.on_event("startup")
def iniciar_auditoria_em_background():
    threading.Thread(target=iniciar_loop_auditoria, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
