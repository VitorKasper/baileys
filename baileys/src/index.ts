import path from 'path';
import dotenv from 'dotenv';

dotenv.config({
  path: path.resolve(__dirname, '../../.env')
});

import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import QRCode from 'qrcode';
import axios from 'axios';
import makeWASocket, {
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    WASocket,
    proto,
    ConnectionState,
    MessageUpsertType
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

const PORT = process.env.PORTA_BAILEYS || 9000;
const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL || 'http://localhost:9090/webhook';
const API_KEY = process.env.API_KEY;

let sock: WASocket | null = null;
let currentQR: string | null = null;
let isConnected = false;

function requireApiKey(req: Request, res: Response, next: NextFunction) {
    if (!API_KEY) return next();
    const key = req.headers['x-api-key'];
    if (key !== API_KEY) {
        res.status(401).json({ error: 'Não autorizado' });
        return;
    }
    next();
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(`🔄 Usando a versão do WhatsApp Web: ${version.join('.')} (Mais recente: ${isLatest})`);

    sock = makeWASocket({
        auth: state,
        version,
        logger: pino({ level: 'error' }) as ReturnType<typeof pino>,
        browser: ['Windows', 'Chrome', '110.0.0.0']
    });

    sock.ev.on('connection.update', async (update: Partial<ConnectionState>) => {
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
                console.log(`📝 Detalhes do erro: ${error.message || String(error)}`);
            }

            if (shouldReconnect) {
                console.log('🔄 Tentando reconectar em 5 segundos...');
                setTimeout(() => connectToWhatsApp(), 5000);
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

    sock.ev.on('messages.upsert', async ({ messages, type }: { messages: proto.IWebMessageInfo[]; type: MessageUpsertType }) => {
        if (type === 'notify') {
            try {
                await axios.post(PYTHON_WEBHOOK_URL, { messages, type });
            } catch (error: unknown) {
                const msg = error instanceof Error ? error.message : String(error);
                console.error('❌ Erro ao enviar para o Webhook Python:', msg);
            }
        }
    });
}

app.get('/status', (_req: Request, res: Response) => {
    res.json({ connected: isConnected, qr: currentQR });
});

app.post('/send', requireApiKey, async (req: Request, res: Response) => {
    try {
        const { number, text } = req.body as { number: string; text: string };
        if (!sock || !isConnected) {
            res.status(400).json({ error: 'WhatsApp não está conectado' });
            return;
        }

        const jid = `${number}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text });
        res.json({ success: true, message: 'Mensagem enviada!' });
    } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : String(error);
        res.status(500).json({ error: msg });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Servidor rodando na porta ${PORT}`);
    console.log(`📊 Dashboard disponível em: http://localhost:${PORT}`);
    if (!API_KEY) {
        console.log('⚠️  API_KEY não configurada — endpoint /send sem autenticação');
    }
    connectToWhatsApp();
});
