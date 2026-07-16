# WhatsApp Bot Boilerplate (Node.js + Python)

Template para criar chatbots no WhatsApp sem precisar reconfigurar o Baileys a cada projeto. A conexão com o WhatsApp fica no serviço Node.js; toda a regra de negócio fica no Python.

## Como funciona

```
WhatsApp → Node.js (Baileys) → POST /webhook → Python (FastAPI)
                 ↑                                      |
                 └──────── POST /send ←─────────────────┘
```

1. O Node.js conecta ao WhatsApp e encaminha cada mensagem recebida ao Python via webhook.
2. O Python processa a mensagem e chama `/send` no Node.js para responder.
3. Um dashboard web em `http://localhost:9000` exibe o QR Code para autenticação.

## Pré-requisitos

- Node.js 20+
- Python 3.11+

## Configuração

Copie o arquivo de exemplo e ajuste as variáveis:

```bash
cp .env.example .env
```

| Variável           | Padrão                          | Descrição                                      |
|--------------------|---------------------------------|------------------------------------------------|
| `PORTA_BAILEYS`    | `9000`                          | Porta do serviço Node.js                       |
| `PORTA_PYTHON`     | `9090`                          | Porta do serviço Python                        |
| `NODE_API_URL`     | `http://localhost:9000/send`    | URL que o Python usa para enviar mensagens     |
| `PYTHON_WEBHOOK_URL` | `http://localhost:9090/webhook` | URL que o Node.js usa para entregar mensagens |
| `API_KEY`          | _(vazio)_                       | Chave de autenticação do endpoint `/send` (recomendado) |

> Para gerar uma `API_KEY` segura: `openssl rand -hex 32`

## Rodando localmente

**Terminal 1 — serviço Node.js:**
```bash
cd baileys
npm install
npm run dev
```

Acesse `http://localhost:9000`, escaneie o QR Code com o WhatsApp e aguarde "Conectado".

**Terminal 2 — bot Python:**
```bash
cd python-bot
pip install -r requirements.txt
python main.py
```

`python main.py` sobe o webhook (que apenas recebe e ignora mensagens — o bot
não reage a nada) e, em background, o loop de auditoria de integração
(`run_auditoria_integracao.py`), que pesquisa erros a cada
`AUDITORIA_INTERVALO_SEGUNDOS` (padrão 60s) e envia o relatório via WhatsApp
aos destinatários configurados em `config/auditoria_integracao.json`.

## Rodando com Docker

```bash
docker compose up --build
```

A sessão do WhatsApp é persistida em `baileys/auth_info_baileys/` via volume — você não precisa escanear o QR a cada restart.

## Auditoria de integração

A lógica de scraping/relatório de erros fica em
`python-bot/services/web/integracao_service.py` e
`python-bot/run_auditoria_integracao.py`. A cada ciclo, a `data_inicio` da
pesquisa é sempre igual à `data_fim` do ciclo anterior, para não deixar
lacunas nem duplicar registros.

## API do serviço Node.js

| Método | Endpoint  | Descrição                                           |
|--------|-----------|-----------------------------------------------------|
| GET    | `/status` | Retorna `{ connected, qr }` com o estado da conexão |
| POST   | `/send`   | Envia mensagem. Body: `{ number, text }`. Requer `x-api-key` se `API_KEY` estiver configurada |
| POST   | `/webhook`| _(interno)_ Recebido pelo Python, não exposto externamente |

## Estrutura

```
.
├── baileys/          # Serviço Node.js + Baileys
│   ├── src/index.ts  # Lógica de conexão e endpoints
│   └── public/       # Dashboard web (QR Code)
├── python-bot/       # Lógica do bot
│   └── main.py       # Webhook + regra de negócio
├── docker-compose.yml
└── .env.example
```
