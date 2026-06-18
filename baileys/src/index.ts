import path from 'path';
import dotenv from 'dotenv';

dotenv.config({
  path: path.resolve(__dirname, '../../.env')
});

process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

import express from 'express';
import cors from 'cors';
import path from 'path';
import QRCode from 'qrcode';
import axios from 'axios';
import makeWASocket, { useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

const PORT = process.env.PORTA_BAILEYS || 9000;
const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL || 'http://localhost:9090/webhook';

let sock: any = null;
let currentQR: string | null = null;
let isConnected = false;

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');
    
    // Busca automaticamente a versão estável mais recente do protocolo do WhatsApp
    const { version, isLatest } = await fetchLatestBaileysVersion();// Corrija esta linha:
    console.log(`🔄 Usando a versão do WhatsApp Web: ${version.join('.')} (Mais recente: ${isLatest})`);

    sock = makeWASocket({
        auth: state,
        version, // <--- Adicionado aqui
        logger: pino({ level: 'error' }) as any,
        browser: ['Windows', 'Chrome', '110.0.0.0'] // <--- Simula um navegador real para evitar bloqueios
    });

    sock.ev.on('connection.update', async (update: any) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            currentQR = await QRCode.toDataURL(qr);
        }

        if (connection === 'close') {
            isConnected = false;
            currentQR = null;
            
            const error = lastDisconnect?.error as Boom;
            const statusCode = error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            
            console.log(`⚠️ Conexão fechada. Motivo (Status Code): ${statusCode}`);
            if (error) {
                console.log(`📝 Detalhes do erro: ${error.message || error}`);
            }

            if (shouldReconnect) {
                // Adicionado um delay de 5 segundos antes de tentar reconectar
                console.log('🔄 Tentando reconectar em 5 segundos...');
                setTimeout(() => {
                    connectToWhatsApp();
                }, 5000);
            } else {
                console.log('❌ Você foi desconectado do WhatsApp. Apague a pasta "auth_info_baileys" e escaneie novamente.');
            }
        } else if (connection === 'open') {
            isConnected = true;
            currentQR = null;
            console.log('✅ WhatsApp Conectado com sucesso!');
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async (m: any) => {
        if (m.type === 'notify') {
            try {
                await axios.post(PYTHON_WEBHOOK_URL, m);
            } catch (error: any) {
                console.error('❌ Erro ao enviar para o Webhook Python:', error.message);
            }
        }
    });
}

app.get('/status', (req, res) => {
    res.json({
        connected: isConnected,
        qr: currentQR
    });
});

app.post('/send', async (req, res) => {
    try {
        const { number, text } = req.body;
        if (!sock || !isConnected) {
            return res.status(400).json({ error: 'WhatsApp não está conectado' });
        }
        
        const jid = `${number}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text });
        res.json({ success: true, message: 'Mensagem enviada!' });
    } catch (error: any) {
        res.status(500).json({ error: error.message });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Servidor rodando na porta ${PORT}`);
    console.log(`📊 Dashboard disponível em: http://localhost:${PORT}`);
    connectToWhatsApp();
});