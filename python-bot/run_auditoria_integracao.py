import os
import time
from datetime import datetime

from dotenv import load_dotenv

from services.browser.playwright_service import PlaywrightService
from services.web.login_service import LoginService
from services.web.integracao_service import IntegracaoService

load_dotenv()

EMAIL = os.getenv("APISUL_EMAIL", "")
SENHA = os.getenv("APISUL_SENHA", "")
INTERVALO_SEGUNDOS = int(os.getenv("AUDITORIA_INTERVALO_SEGUNDOS", "60"))


def iniciar_loop_auditoria():
    """Roda o ciclo de auditoria de integração indefinidamente, a cada
    INTERVALO_SEGUNDOS — abrindo um browser novo e fazendo login a cada
    ciclo, para não acumular estado/memória de uma sessão que nunca fecha.

    Se um ciclo falhar (browser é o ponto mais frágil: pode travar, crashar
    ou perder conexão), `ultima_data_fim` NÃO avança — o próximo ciclo
    tenta de novo a partir da mesma janela, então nenhum registro é
    perdido por causa de uma falha pontual."""
    ultima_data_fim = None
    cache_placas = {}
    ciclo = 0

    while True:
        ciclo += 1
        agora = datetime.now()
        inicio = time.monotonic()
        print(f"\n===== Ciclo {ciclo} — {agora.strftime('%d/%m/%Y %H:%M:%S')} =====")

        try:
            with PlaywrightService(headless=True) as context:
                page = LoginService().executar(context, EMAIL, SENHA)
                _, ultima_data_fim = IntegracaoService(cache_placas=cache_placas).executar(
                    page,
                    metodo_valor="1",
                    metodo_texto="InsereSMP",
                    page_size="50",
                    apenas_erros=True,
                    data_inicio=ultima_data_fim,
                    data_fim=agora,
                )
            print(f"⏱️ Ciclo {ciclo} concluído em {time.monotonic() - inicio:.1f}s")
        except Exception as e:
            print(
                f"⚠️ Erro no ciclo {ciclo} de auditoria de integração "
                f"({type(e).__name__}): {e}"
            )
            print("↩️ Período não avançado — será retentado no próximo ciclo.")

        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    iniciar_loop_auditoria()
