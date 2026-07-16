import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from pages.integracao_page import IntegracaoPage
from services.notificacao_service import NotificacaoService

BUSCA_XML_URL = (
    "https://novoapisullog.apisul.com.br/Servicos/AuditoriaIntegracao.svc/BuscaXML"
)

CONFIG_PADRAO = Path(__file__).resolve().parents[2] / "config" / "auditoria_integracao.json"

JANELA_DEDUP_PLACA = timedelta(minutes=5)


class IntegracaoService:

    def __init__(
        self,
        output_dir="output/auditoria_integracao",
        config_path=CONFIG_PADRAO,
        notificacao=None,
        cache_placas=None,
    ):
        self.output_dir = Path(output_dir)
        self.notificacao = notificacao or NotificacaoService()

        config = self._carregar_config(config_path)
        self.destinatarios = config.get("destinatarios", ["555184748220"])
        self._cargas_norm = [
            self._normalizar(c) for c in config.get("cargas_ignoradas", []) if c
        ]

        # placa -> datetime da última notificação enviada para ela.
        # Passe o mesmo dict entre execuções (ex.: entre ciclos do loop) para
        # que a deduplicação funcione também entre chamadas diferentes.
        self._cache_placas = cache_placas if cache_placas is not None else {}

    def executar(
        self,
        page,
        metodo_valor="1",
        metodo_texto="InsereSMP",
        tipo_retorno="Não Ok",
        data_inicio=None,
        data_fim=None,
        minutos_atras=10,
        page_size="50",
        apenas_erros=True,
    ):
        """Pesquisa a auditoria de integração no período [data_inicio, data_fim].

        Se `data_inicio`/`data_fim` não forem informados, usa como fallback
        `agora - minutos_atras` até `agora` (útil apenas na primeira execução
        de um loop; nas execuções seguintes o chamador deve informar
        `data_inicio` igual ao `data_fim` da requisição anterior, para não
        deixar lacunas)."""
        data_fim = data_fim or datetime.now()
        data_inicio = data_inicio or (data_fim - timedelta(minutes=minutos_atras))

        integracao = IntegracaoPage(page)

        try:
            print("🌐 Acessando página de Auditoria de Integração...")
            integracao.acessar()
            page.wait_for_url("**/AuditoriaIntegracao", timeout=30_000)

            print(f"⚙️ Aplicando filtros (método={metodo_texto}, tipo_retorno={tipo_retorno})...")
            integracao.preencher_metodo(metodo_valor, metodo_texto)
            integracao.selecionar_tipo_retorno(tipo_retorno)
            integracao.preencher_periodo(data_inicio, data_fim)

            print("🔎 Pesquisando auditoria de integração...")
            integracao.submit()

            print(f"📄 Alterando page size para {page_size}...")
            integracao.alterar_page_size(page_size)

            registros = integracao.extrair_registros()
        except Exception as e:
            print(f"❌ Falha ao pesquisar/extrair a grid de auditoria: {e}")
            raise

        print(f"📋 {len(registros)} registros encontrados no grid")

        if apenas_erros:
            registros = [r for r in registros if self._tem_erro(r)]
            print(f"❌ {len(registros)} registros com erro")

        salvos = []
        ignorados = 0
        falhas = 0
        for indice, registro in enumerate(registros, start=1):
            try:
                tipo, id_auditoria = self._split_argumento(registro["argumento_enviado"])
                registro["id_auditoria_integracao"] = id_auditoria

                registro["xml_enviado"] = self._busca_xml(
                    page, registro["argumento_enviado"]
                )
                registro["xml_recebido"] = self._busca_xml(
                    page, registro["argumento_recebido"]
                )
                registro["campos_xml_enviado"] = self._xml_para_dict(
                    registro["xml_enviado"]
                )
                registro["cargas_detectadas"] = self._cargas_detectadas(
                    registro["xml_enviado"]
                )

                # Se a carga do XML estiver na lista de ignorados, pula (não salva/notifica)
                if self._carga_ignorada(registro["xml_enviado"]):
                    ignorados += 1
                    print(
                        f"⏭️  [{indice}/{len(registros)}] Ignorado (carga na lista): "
                        f"{registro['cargas_detectadas'] or '—'}"
                    )
                    continue

                caminho = self._salvar_json(registro)
                salvos.append(str(caminho))
                print(f"💾 [{indice}/{len(registros)}] {caminho.name}")

                if self._placa_repetida(registro):
                    print(
                        f"🔁 [{indice}/{len(registros)}] Placa "
                        f"{registro.get('placa_cavalo') or '—'} já notificada nos "
                        f"últimos {int(JANELA_DEDUP_PLACA.total_seconds() // 60)} min — notificação ignorada"
                    )
                    continue

                self._notificar(registro)
            except Exception as e:
                falhas += 1
                print(f"⚠️  [{indice}/{len(registros)}] Falha ao processar registro: {e}")
                continue

        print(
            f"✅ {len(salvos)} salvos, {ignorados} ignorados, {falhas} com falha. "
            f"Saída em {self.output_dir.resolve()}"
        )
        return salvos, data_fim

    # =========================
    # BUSCA XML (via sessão autenticada do browser, sem UI)
    # =========================
    def _busca_xml(self, page, argumento):
        if not argumento:
            return None

        tipo, id_auditoria = self._split_argumento(argumento)
        if not id_auditoria:
            return None

        response = page.request.post(
            BUSCA_XML_URL,
            data=json.dumps(
                {
                    "tipoAuditoriaIntegracao": tipo,
                    "idAuditoriaIntegracao": id_auditoria,
                }
            ),
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": IntegracaoPage.URL,
            },
        )

        if not response.ok:
            print(f"⚠️ Erro {response.status} ao buscar XML ({argumento})")
            return None

        try:
            return response.json().get("d")
        except Exception as e:
            print(f"⚠️ Resposta inválida do BuscaXML ({argumento}): {e}")
            return None

    # =========================
    # CARGA / NOTIFICAÇÃO
    # =========================
    def _carga_ignorada(self, xml_string):
        """True se QUALQUER valor de texto do XML corresponder (palavra inteira,
        sem acento, maiúsculas) a alguma carga da lista de ignorados."""
        if not xml_string or not self._cargas_norm:
            return False

        texto = "\n".join(
            self._normalizar(v) for v in self._valores_xml(xml_string)
        )
        for carga in self._cargas_norm:
            if re.search(r"\b" + re.escape(carga) + r"\b", texto):
                return True
        return False

    def _cargas_detectadas(self, xml_string):
        """Best-effort: valores de tags cujo nome sugere carga/produto/mercadoria,
        apenas para exibir na notificação/log."""
        if not xml_string:
            return []
        try:
            raiz = ET.fromstring(xml_string)
        except (ET.ParseError, TypeError):
            return []

        chaves = ("CARGA", "PRODUTO", "MERCADORIA")
        achados = []
        for elemento in raiz.iter():
            nome = self._normalizar(elemento.tag)
            if any(k in nome for k in chaves) and (elemento.text or "").strip():
                achados.append(elemento.text.strip())
        return achados

    def _placa_repetida(self, registro):
        """True se essa placa já foi notificada há menos de JANELA_DEDUP_PLACA
        (considerando também notificações de ciclos/execuções anteriores, se o
        mesmo `cache_placas` for reaproveitado entre chamadas). Atualiza o
        cache com o horário desta ocorrência quando não é repetição."""
        placa = self._normalizar(registro.get("placa_cavalo"))
        if not placa:
            return False

        agora = self._data_hora_registro(registro)

        # Descarta entradas antigas para o cache não crescer indefinidamente.
        self._cache_placas = {
            p: quando
            for p, quando in self._cache_placas.items()
            if abs(agora - quando) < JANELA_DEDUP_PLACA
        }

        ultima_notificacao = self._cache_placas.get(placa)
        if ultima_notificacao is not None and abs(agora - ultima_notificacao) < JANELA_DEDUP_PLACA:
            return True

        self._cache_placas[placa] = agora
        return False

    @staticmethod
    def _data_hora_registro(registro):
        try:
            return datetime.strptime(registro["data_hora"], "%d/%m/%Y %H:%M")
        except (ValueError, KeyError, TypeError):
            return datetime.now()

    def _notificar(self, registro):
        if not self.destinatarios:
            return
        texto = self._montar_mensagem(registro)
        self.notificacao.enviar_para_todos(self.destinatarios, texto)

    @staticmethod
    def _montar_mensagem(registro):
        return (
            "🚨 *Erro de Integração (SMP)*\n"
            f"*Placa:* {registro.get('placa_cavalo') or '—'}\n"
            f"*Data/Hora:* {registro.get('data_hora') or '—'}\n"
            f"*Erro:* \n{registro.get('mensagem_erro') or '—'}"
        )

    @staticmethod
    def _valores_xml(xml_string):
        try:
            raiz = ET.fromstring(xml_string)
        except (ET.ParseError, TypeError):
            return []
        return [
            elemento.text.strip()
            for elemento in raiz.iter()
            if (elemento.text or "").strip()
        ]

    @staticmethod
    def _normalizar(texto):
        if not texto:
            return ""
        decomposto = unicodedata.normalize("NFKD", str(texto))
        sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", sem_acento.upper()).strip()

    @staticmethod
    def _carregar_config(config_path):
        try:
            return json.loads(Path(config_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️ Não foi possível ler a config ({config_path}): {e}")
            return {}

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _tem_erro(registro):
        tipo_retorno = (registro.get("tipo_retorno") or "").strip().lower()
        return bool(registro.get("mensagem_erro")) or tipo_retorno == "não ok"

    @staticmethod
    def _split_argumento(argumento):
        """commandArgument do RadButton: 'tipoAuditoriaIntegracao;idAuditoriaIntegracao'."""
        if not argumento or ";" not in argumento:
            return None, None
        tipo, id_auditoria = argumento.split(";", 1)
        return tipo.strip(), id_auditoria.strip()

    @staticmethod
    def _xml_para_dict(xml_string):
        if not xml_string:
            return None
        try:
            raiz = ET.fromstring(xml_string)
        except ET.ParseError:
            return None

        def converte(elemento):
            filhos = list(elemento)
            if not filhos:
                return (elemento.text or "").strip()
            resultado = {}
            for filho in filhos:
                valor = converte(filho)
                if filho.tag in resultado:
                    if not isinstance(resultado[filho.tag], list):
                        resultado[filho.tag] = [resultado[filho.tag]]
                    resultado[filho.tag].append(valor)
                else:
                    resultado[filho.tag] = valor
            return resultado

        return {raiz.tag: converte(raiz)}

    def _salvar_json(self, registro):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            data = datetime.strptime(registro["data_hora"], "%d/%m/%Y %H:%M")
            carimbo = data.strftime("%Y-%m-%d_%H-%M")
        except (ValueError, KeyError):
            carimbo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        identificador = registro.get("id_auditoria_integracao") or "sem-id"
        identificador = re.sub(r"[^\w-]", "_", identificador)

        caminho = self.output_dir / f"{carimbo}_{identificador}.json"
        caminho.write_text(
            json.dumps(registro, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return caminho
