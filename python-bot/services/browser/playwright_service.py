from playwright.sync_api import sync_playwright


class PlaywrightService:
    """Gerencia o ciclo de vida do browser Playwright.

    `__enter__` limpa qualquer recurso parcialmente criado se uma etapa do
    lançamento falhar (ex: browser não instalado, sem memória), e `__exit__`
    tenta fechar cada recurso (context/browser/playwright) independentemente
    — uma falha ao fechar um deles não deve impedir a limpeza dos outros."""

    def __init__(self, headless=True):
        self.headless = headless
        self.pw = None
        self.browser = None
        self.context = None

    def __enter__(self):
        try:
            print(f"🌐 Iniciando browser (headless={self.headless})...")
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context()
            return self.context
        except Exception as e:
            print(f"❌ Falha ao iniciar o browser: {e}")
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb):
        if self.context is not None:
            try:
                self.context.close()
            except Exception as e:
                print(f"⚠️ Falha ao fechar o context do browser: {e}")

        if self.browser is not None:
            try:
                self.browser.close()
            except Exception as e:
                print(f"⚠️ Falha ao fechar o browser: {e}")

        if self.pw is not None:
            try:
                self.pw.stop()
            except Exception as e:
                print(f"⚠️ Falha ao encerrar o Playwright: {e}")