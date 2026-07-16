import json
import time
from datetime import datetime, timedelta
from pages.smp_consulta_page import SmpPageConsulta
from pages.smp_page import SmpPage


class SmpService:

    def executar_get_pontos(self, page, numero_smp):
        smp_consulta = SmpPageConsulta(page)
        smp = SmpPage(page)

        smp_consulta.acessar()
        page.wait_for_url("**/SMPConsulta")

        smp.acessar(numero_smp=numero_smp)
        smp.gerar_mapa()

        time.sleep(0.5)

        with page.expect_response(
            lambda response: "GerarRota" in response.url
        ) as response_info:
            smp.gerar_mapa()

        response = response_info.value

        print("\n🔥 RESPONSE GERAR ROTA CAPTURADA 🔥")
        print("URL:", response.url)
        print("STATUS:", response.status)

        try:
            dados_json = response.json()
            return dados_json
        except Exception as e:
            print(f"Não foi possível converter para JSON. Erro: {e}")
            return None

    def executar_get_pontos_dinamico(self, page, pontos_simplificados):
        smp_consulta = SmpPageConsulta(page)
        smp_consulta.acessar()

        smp = SmpPage(page)

        smp_consulta.criar_smp()
        smp.clicar_ponto_dinamico()

        # ==========================================
        # PARSER: CONVERTE COORDENADAS PARA PAYLOAD API
        # ==========================================
        list_pontos_formatados = []
        # Definimos o dia inicial baseado no seu exemplo (01/07/2026)
        data_base = datetime(2026, 7, 1, 0, 0)

        for indice, coordenada in enumerate(pontos_simplificados):
            lat, lng = coordenada[0], coordenada[1]

            # Soma 1 dia a cada iteração/ponto que avança
            data_atual = data_base + timedelta(days=indice)
            previsao_formatada = data_atual.strftime("%d/%m/%Y %H:%M")

            # Monta o objeto exatamente como o cURL espera
            ponto_payload = {
                "IdPontoGeografico": "0",
                "IdTipoPontoEspacial": "1",
                "Raio": 90,
                "Apelido": "",
                "Nome": f"PONTO_DINAMICO_{indice + 1}",
                "Endereco": f"Rota Automatizada Ponto {indice + 1}",
                "CNPJ": "",
                "CEP": "",
                "Telefone": "",
                "IdPontoPai": 0,
                "JanelaInicial": None,
                "JanelaFinal": None,
                "TempoPermanencia": 60,
                "PrevisaoChegada": previsao_formatada,
                "Lats": [lat],
                "Lngs": [lng],
                "InserirComoPontoGeo": False,
                "IdTipoPontoSMP": 3,
                "IdSMPPonto": 0,
                "IdTipoGeorreferenciamento": 0,
                "IdTipoStatusGeocodificacao": 2,
            }
            list_pontos_formatados.append(ponto_payload)

        # ==========================================
        # INTERCEPTADOR DA REQUISIÇÃO
        # ==========================================
        def mapear_e_alterar_pontos(route):
            payload_modificado = {"listPontos": list_pontos_formatados}

            print(
                f"\n✈️ INTERCEPTADO: Injetando {len(list_pontos_formatados)} pontos dinâmicos mapeados..."
            )
            # Exemplo do primeiro e último ponto no console para conferência de datas
            print(f"-> Primeiro Ponto: {list_pontos_formatados[0]['PrevisaoChegada']}")
            print(f"-> Último Ponto: {list_pontos_formatados[-1]['PrevisaoChegada']}")

            route.continue_(post_data=json.dumps(payload_modificado))

        # Ativa a interceptação antes do clique de salvar
        page.route("**/AdicionarPontoDinamico", mapear_e_alterar_pontos)
        # ==========================================

        # Dispara a requisição que será interceptada
        smp.salva_ponto_dinamico()

        # Remove o interceptador para limpar o escopo do Playwright
        page.unroute("**/AdicionarPontoDinamico")

        input("Aguarde finalização")

        smp.radio_rota_dinamica()

        smp.gerar_mapa()
        smp.gerar_mapa()
        time.sleep(0.5)

        with page.expect_response(
            lambda response: "GerarRota" in response.url
        ) as response_info:
            smp.gerar_rota_dinamica()

        response = response_info.value

        print("\n🔥 RESPONSE GERAR ROTA CAPTURADA 🔥")
        try:
            dados_json = response.json()
            return dados_json
        except Exception as e:
            print(f"Não foi possível converter para JSON. Erro: {e}")
            return None


    # =========================
    # REQUEST
    # =========================
    def _interceptar_request(self, request):
        if request.method != "POST":
            return

        if "GerarRota" not in request.url:
            return

        print("\n🔥 REQUEST GERAR ROTA 🔥")
        print("URL:", request.url)
        print("BODY:", request.post_data)

    # =========================
    # RESPONSE
    # =========================
    def _capturar_response(self, response):
        if "GerarRota" not in response.url:
            return

        print("\n🔥 RESPONSE GERAR ROTA 🔥")
        print("URL:", response.url)
        print("STATUS:", response.status)

        try:
            data = response.json()
            print("\nBODY (JSON):")
            print(data)
        except Exception:
            try:
                print("\nBODY (TEXT):")
                print(response.text())
            except:
                print("Não foi possível ler response body")


