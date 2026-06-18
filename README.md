# 🤖 WhatsApp Bot Boilerplate (Node.js + Python)

Este projeto é um template pronto para você criar chatbots para WhatsApp! Ele separa a complexidade da conexão do WhatsApp Web (usando [Baileys](https://github.com/WhiskeySockets/Baileys) em Node.js) da lógica do seu bot, permitindo que você escreva **toda a sua regra de negócio em Python**.

## 🚀 Como Funciona?
1. O serviço **Node.js** se conecta ao WhatsApp e escuta as mensagens.
2. Toda mensagem nova é enviada via **Webhook** para o serviço **Python**.
3. O script **Python** processa a mensagem e envia uma requisição de volta para o Node.js para responder ao usuário.
4. Inclui um **Dashboard web** para escaneamento fácil do QR Code!

## ⚙️ Como rodar?

Você precisará de 2 terminais abertos.

### Passo 1: Iniciar a API Baileys (Terminal 1)
```bash
cd baileys
npm install
npm start

Acesse http://localhost:3000 no seu navegador. Um QR Code aparecerá. Escaneie-o com o seu WhatsApp para conectar.

Passo 2: Iniciar a Lógica do Bot em Python (Terminal 2)
Bash
cd python-bot
pip install -r requirements.txt
python main.py
Pronto! Agora envie um "Oi" ou "Ping" para o WhatsApp conectado e veja a mágica acontecer. Edite o arquivo python-bot/main.py para criar suas próprias regras de negócios!


Com essa base sólida, a comunidade vai conseguir fazer o `git clone`, abrir a API do Baileys para ler o QR code em `localhost:3000`, e codar os bots livremente escrevendo apenas no arquivo Python!

Qualquer dúvida sobre a implementação ou se quiser adicionar mais algum recurso (como en