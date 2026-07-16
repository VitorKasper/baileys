import json
from urllib.parse import parse_qs

from pages.base_page import BasePage


class IntegracaoPage(BasePage):

    URL = "https://novoapisullog.apisul.com.br/AuditoriaIntegracao"
    GRID = "ctl00$MainContent$grdAuditoriaIntegracao"

    def acessar(self):
        self.page.goto(self.URL)

    def preencher_metodo(self, valor="1", texto="InsereSMP"):
        """Seleciona o método injetando o valor no ClientState do RadComboBox."""
        client_state = json.dumps(
            {
                "logEntries": [],
                "value": valor,
                "text": texto,
                "enabled": True,
                "checkedIndices": [],
                "checkedItemsTextOverflows": False,
            }
        )
        self.page.evaluate(
            """([texto, clientState]) => {
                const input = document.querySelector("input[name='ctl00$MainContent$rcbMetodo']");
                if (input) input.value = texto;
                const hidden = document.getElementById('ctl00_MainContent_rcbMetodo_ClientState');
                hidden.value = clientState;
            }""",
            [texto, client_state],
        )

    def selecionar_tipo_retorno(self, texto="Não Ok"):
        """Abre o dropdown (checkbox list) de Tipo Retorno e marca a opção desejada."""
        self.remover_popup_nps()
        self.page.click("a[id='ctl00_MainContent_rcbTipoRetornoIntegracao_Arrow']")

        dropdown = self.page.locator("#ctl00_MainContent_rcbTipoRetornoIntegracao_DropDown")
        dropdown.wait_for(state="visible")

        dropdown.locator("li", has_text=texto).locator("input[type=checkbox]").check()

        self.page.keyboard.press("Escape")

    def preencher_periodo(self, data_inicio, data_fim):
        """Preenche Data Inicial e Data Final do filtro de pesquisa."""
        self._preencher_data_hora(
            "ctl00_MainContent_periodoFiltro_txtDataInicial_dateInput", data_inicio
        )
        self._preencher_data_hora(
            "ctl00_MainContent_periodoFiltro_txtDataFinal_dateInput", data_fim
        )

    def _preencher_data_hora(self, input_id, valor):
        """Digita os dígitos direto na máscara do RadDateInput (dd/MM/yyyy HH:mm).

        Ex.: 10/10/2005 15:54 -> digita "101020051554". Digitar via a máscara
        (em vez de setar `.value`/ClientState via JS) faz o próprio widget
        Telerik sincronizar seu estado interno — inclusive o hidden "mestre"
        que o servidor usa no postback, que não era atualizado só com JS."""
        digitos = valor.strftime("%d%m%Y%H%M")

        campo = self.page.locator(f"#{input_id}")
        campo.click()
        self.page.keyboard.press("Control+A")
        campo.press_sequentially(digitos, delay=50)
        campo.press("Tab")

    def submit(self):
        self.remover_popup_nps()
        with self.page.expect_response(self._resposta_grid, timeout=120_000) as resposta_info:
            self.page.click("span[id='ctl00_MainContent_btnPesquisar']")
        self._logar_filtro_enviado(resposta_info.value)
        self.page.wait_for_timeout(1_500)
        print(f"🔢 Linhas na grid após pesquisar: {self._contar_linhas()}")

    def _contar_linhas(self):
        return self.page.evaluate(
            """() => document.querySelectorAll(
                '#ctl00_MainContent_grdAuditoriaIntegracao_ctl00 > tbody > tr.rgRow,' +
                '#ctl00_MainContent_grdAuditoriaIntegracao_ctl00 > tbody > tr.rgAltRow'
            ).length"""
        )

    @staticmethod
    def _logar_filtro_enviado(resposta):
        """Loga os filtros de fato recebidos pelo servidor (período, método e
        tipo de retorno), para conferência — os valores no ClientState nem
        sempre batem com o que é efetivamente submetido no postback."""
        campos = parse_qs(resposta.request.post_data or "")
        palavras_chave = ("DataInicial", "DataFinal", "rcbMetodo", "rcbTipoRetorno")
        filtro = {
            chave: valores[0]
            for chave, valores in campos.items()
            if any(p in chave for p in palavras_chave)
        }
        if filtro:
            print(f"🗓️ Filtros confirmados pelo servidor: {filtro}")

    def alterar_page_size(self, tamanho="50"):
        """Abre o dropdown do PageSize e clica na opção desejada (10/20/50).
        Quando a pesquisa não retorna nenhum registro, a grid não renderiza
        esse controle — nesse caso não há nada a fazer."""
        arrow = self.page.locator(
            "#ctl00_MainContent_grdAuditoriaIntegracao_ctl00_ctl03_ctl01_PageSizeComboBox_Arrow"
        )
        if not arrow.is_visible():
            print("ℹ️ Combo de page size não visível — pulando (grid provavelmente vazia).")
            return

        self.remover_popup_nps()
        arrow.click()

        dropdown = self.page.locator(
            "#ctl00_MainContent_grdAuditoriaIntegracao_ctl00_ctl03_ctl01_PageSizeComboBox_DropDown"
        )
        dropdown.wait_for(state="visible")

        with self.page.expect_response(self._resposta_grid, timeout=120_000):
            dropdown.locator("li", has_text=str(tamanho)).click()
        self.page.wait_for_timeout(2_000)
        print(f"🔢 Linhas na grid após alterar page size: {self._contar_linhas()}")

    def extrair_registros(self):
        """Lê todas as linhas do grid. Os botões 'Ver dados' (Enviados/Recebidos)
        são RadButtons cujo commandArgument é 'tipoAuditoriaIntegracao;idAuditoriaIntegracao'."""
        return self.page.evaluate(
            """() => {
                const linhas = document.querySelectorAll(
                    '#ctl00_MainContent_grdAuditoriaIntegracao_ctl00 > tbody > tr.rgRow,' +
                    '#ctl00_MainContent_grdAuditoriaIntegracao_ctl00 > tbody > tr.rgAltRow'
                );

                const texto = (td) => td ? td.innerText.replace(/\\u00a0/g, ' ').trim() : '';

                const argumento = (td) => {
                    if (!td) return null;
                    const span = td.querySelector('span[id]');
                    if (!span) return null;
                    try {
                        const ctl = window.$find ? $find(span.id) : null;
                        if (ctl && ctl.get_commandArgument) {
                            return ctl.get_commandArgument() || null;
                        }
                    } catch (e) {}
                    const hidden = td.querySelector('input[type=hidden]');
                    if (hidden && hidden.value) {
                        try {
                            return JSON.parse(hidden.value).commandArgument || null;
                        } catch (e) {}
                    }
                    return null;
                };

                return Array.from(linhas).map((tr) => {
                    const tds = tr.querySelectorAll(':scope > td');
                    return {
                        metodo: texto(tds[1]),
                        ip: texto(tds[2]),
                        data_hora: texto(tds[3]),
                        data_hora_reprocessamento: texto(tds[4]),
                        tipo_retorno: texto(tds[5]),
                        mensagem_erro: texto(tds[6]),
                        numero_smp: texto(tds[7]),
                        documento_controle: texto(tds[8]),
                        placa_cavalo: texto(tds[9]),
                        transportadora: texto(tds[10]),
                        observacao: texto(tds[11]),
                        argumento_enviado: argumento(tds[12]),
                        argumento_recebido: argumento(tds[13]),
                    };
                });
            }"""
        )

    @staticmethod
    def _resposta_grid(response):
        return (
            "AuditoriaIntegracao" in response.url
            and response.request.method == "POST"
        )
