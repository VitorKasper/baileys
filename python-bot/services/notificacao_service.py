import os
import time
import requests


class NotificacaoService:
    """Envia mensagens via API Node/Baileys (endpoint /send).

    O campo `number` aceita tanto um número puro (que o Node completa com
    @s.whatsapp.net) quanto um JID completo de grupo (@g.us) ou contato."""

    def __init__(self, api_url=None, api_key=None):
        self.api_url = api_url or os.getenv("NODE_API_URL", "http://localhost:9000/send")
        self.api_key = api_key or os.getenv("API_KEY", "")

    def enviar(self, jid, texto, tentativas=2):
        if not jid:
            return False

        payload = {"number": jid, "text": texto}
        headers = {"x-api-key": self.api_key} if self.api_key else {}

        for tentativa in range(1, tentativas + 1):
            try:
                resposta = requests.post(
                    self.api_url, json=payload, headers=headers, timeout=30
                )
                if resposta.status_code == 200:
                    print(f"✅ Notificação enviada para {jid}")
                    return True
                print(
                    f"❌ Erro ao enviar para {jid} (tentativa {tentativa}/{tentativas}): "
                    f"{resposta.status_code} {resposta.text}"
                )
            except Exception as e:
                print(
                    f"❌ Erro de conexão com a API Node ({jid}, tentativa "
                    f"{tentativa}/{tentativas}): {e}"
                )

            if tentativa < tentativas:
                time.sleep(2)

        return False

    def enviar_para_todos(self, destinatarios, texto):
        """destinatarios: lista de dicts {"nome": ..., "jid": ...}.
        Um pequeno intervalo entre envios evita que o WhatsApp trate rajadas
        de mensagens automáticas para números diferentes como spam."""
        enviados = 0
        for destino in destinatarios:
            jid = (destino or {}).get("jid", "").strip()
            if not jid:
                continue
            if self.enviar(jid, texto):
                enviados += 1
            time.sleep(1)
        return enviados
