import json
import os
from datetime import datetime

class Fluxo:
    def __init__(self):
        # Controle de sessões ativas na memória
        self.sessions = {}
        # Caminho do arquivo onde o histórico permanente será salvo
        self.arquivo_historico = "historico_atendimentos.json"

        # Mensagens fixas centralizadas (Agora aceitam String OU Lista de Strings)
        self.mensagens = {
            "boas_vindas": [
                "Olá! 👋 Seja bem-vindo ao assistente do Multicadastro.",
                "Para iniciar o atendimento, por favor informe o seu *usuário do Apisullog*:"
            ],

            "usuario_invalido": (
                "❌ Não foi possível validar o usuário informado.\n"
                "Por motivos de segurança, o atendimento foi encerrado."
            ),

            "menu_principal": (
                "Usuário validado com sucesso, Vitor! ✅\n\n"
                "Como podemos ajudá-lo hoje? Selecione uma das opções abaixo digitando o número correspondente:\n\n"
                "1️⃣ - Solicitar alteração de rastreador\n"
                "2️⃣ - Solicitar alteração de placa"
            ),

            "submenu_rastreador": (
                "Deseja realizar a alteração do *emitente* do rastreador?\n\n"
                "1️⃣ - Sim\n"
                "2️⃣ - Não"
            ),

            "submenu_placa": (
                "Informe o tipo de alteração de placa que deseja realizar:\n\n"
                "1️⃣ - Alteração no campo emitente\n"
                "2️⃣ - Alteração de sensores/atuadores ou troca de rastreador"
            ),

            "solicitar_placa": (
                "Por favor, informe a **placa do veículo** para darmos continuidade ao atendimento:"
            ),

            "sucesso_final": (
                "✅ Solicitação concluída com sucesso!\n\n"
                "A alteração foi registrada e o atendimento foi finalizado.\n"
                "Caso precise de algo mais, estamos à disposição."
            ),

            "atendimento_encerrado": (
                "ℹ️ Atendimento encerrado sem a realização de alterações.\n"
                "Se desejar, você pode iniciar um novo atendimento a qualquer momento."
            ),

            "erro_opcao": (
                "⚠️ Opção inválida.\n"
                "Por favor, selecione uma das opções disponíveis digitando o número correspondente."
            )
        }

    def _obter_mensagem(self, chave: str, **kwargs) -> list:
        """Busca a mensagem e garante que o retorno seja SEMPRE uma lista de strings,

        mesmo que tenha sido configurada como uma string única. Também aplica formatação se necessário.
        """
        msg = self.mensagens[chave]
        if isinstance(msg, list):
            return [m.format(**kwargs) for m in msg]
        return [msg.format(**kwargs)]

    def _salvar_historico(self, sender: str, session: dict, motivo_encerramento: str):
        """Método interno para persistir os dados coletados e a conversa em um arquivo JSON."""
        dados_atendimento = {
            "data_hora_fim": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "whatsapp_numero": sender,
            "motivo_encerramento": motivo_encerramento,
            "dados_coletados": session["dados"],
            "transcricao_conversa": session["historico_conversa"]
        }

        if os.path.exists(self.arquivo_historico):
            try:
                with open(self.arquivo_historico, "r", encoding="utf-8") as f:
                    historico = json.load(f)
                    if not isinstance(historico, list):
                        historico = []
            except Exception:
                historico = []
        else:
            historico = []

        historico.append(dados_atendimento)
        with open(self.arquivo_historico, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)

    def _registrar_mensagem(self, session: dict, autor: str, texto_ou_lista):
        """Registra cada interação no histórico interno, aceitando strings ou listas."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if isinstance(texto_ou_lista, list):
            for t in texto_ou_lista:
                session["historico_conversa"].append({
                    "timestamp": timestamp,
                    "autor": autor,
                    "texto": t
                })
        else:
            session["historico_conversa"].append({
                "timestamp": timestamp,
                "autor": autor,
                "texto": texto_ou_lista
            })

    def run(self, sender: str, text: str):
        texto_limpo = text.strip()

        # ---------------------------------------------------------
        # NOVA SESSÃO (ETAPA 0)
        # ---------------------------------------------------------
        if sender not in self.sessions:
            self.sessions[sender] = {
                "etapa": 1,
                "dados": {},
                "historico_conversa": []
            }
            msgs = self._obter_mensagem("boas_vindas")
            self._registrar_mensagem(self.sessions[sender], "usuario", texto_limpo)
            self._registrar_mensagem(self.sessions[sender], "bot", msgs)
            
            return {"numero": sender, "mensagem": msgs}

        # Recupera sessão ativa
        session = self.sessions[sender]
        etapa_atual = session["etapa"]
        self._registrar_mensagem(session, "usuario", texto_limpo)

        # ---------------------------------------------------------
        # ETAPA 1: Validação do Usuário Apisullog
        # ---------------------------------------------------------
        if etapa_atual == 1:
            if texto_limpo.lower() == "vitor.borba":
                session["dados"]["usuario_apisullog"] = texto_limpo
                session["etapa"] = 2
                
                msgs = self._obter_mensagem("menu_principal")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}
            else:
                msgs = self._obter_mensagem("usuario_invalido")
                self._registrar_mensagem(session, "bot", msgs)
                self._salvar_historico(sender, session, "Usuário Inválido")
                del self.sessions[sender]
                return {"numero": sender, "mensagem": msgs}

        # ---------------------------------------------------------
        # ETAPA 2: Menu Principal (Rastreador vs Placa)
        # ---------------------------------------------------------
        elif etapa_atual == 2:
            if texto_limpo == "1":
                session["dados"]["fluxo_escolhido"] = "Rastreador"
                session["etapa"] = 3
                
                msgs = self._obter_mensagem("submenu_rastreador")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}
            
            elif texto_limpo == "2":
                session["dados"]["fluxo_escolhido"] = "Placa"
                session["etapa"] = 4
                
                msgs = self._obter_mensagem("submenu_placa")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}
            
            else:
                msgs = self._obter_mensagem("erro_opcao")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}

        # ---------------------------------------------------------
        # ETAPA 3: Submenu Rastreador (Alterar Emitente?)
        # ---------------------------------------------------------
        elif etapa_atual == 3:
            if texto_limpo == "1":
                session["dados"]["alterar_emitente"] = "Sim"
                session["etapa"] = 5
                
                msgs = self._obter_mensagem("solicitar_placa")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}
            
            elif texto_limpo == "2":
                msgs = self._obter_mensagem("atendimento_encerrado")
                self._registrar_mensagem(session, "bot", msgs)
                self._salvar_historico(sender, session, "Cancelado no Submenu Rastreador")
                del self.sessions[sender]
                return {"numero": sender, "mensagem": msgs}
            
            else:
                msgs = self._obter_mensagem("erro_opcao")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}

        # ---------------------------------------------------------
        # ETAPA 4: Submenu Placa (Tipo de alteração)
        # ---------------------------------------------------------
        elif etapa_atual == 4:
            if texto_limpo == "1":
                session["dados"]["tipo_alteracao_placa"] = "Alteração no campo emitente"
                session["etapa"] = 5
                
                msgs = self._obter_mensagem("solicitar_placa")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}
            
            elif texto_limpo == "2":
                session["dados"]["tipo_alteracao_placa"] = "Alteração nos sensores/atuadores ou troca de rastreador"
                session["etapa"] = 5
                
                msgs = self._obter_mensagem("solicitar_placa")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}
            
            else:
                msgs = self._obter_mensagem("erro_opcao")
                self._registrar_mensagem(session, "bot", msgs)
                return {"numero": sender, "mensagem": msgs}

        # ---------------------------------------------------------
        # ETAPA 5: Coleta de Placa e Finalização com Sucesso
        # ---------------------------------------------------------
        elif etapa_atual == 5:
            session["dados"]["placa_veiculo"] = texto_limpo.upper()
            
            msgs = self._obter_mensagem("sucesso_final")
            self._registrar_mensagem(session, "bot", msgs)
            
            self._salvar_historico(sender, session, "Concluído com Sucesso")
            del self.sessions[sender]
            
            return {"numero": sender, "mensagem": msgs}

        return False
    

