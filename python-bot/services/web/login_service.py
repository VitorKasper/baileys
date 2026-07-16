from pages.login_page import LoginPage


class LoginService:

    def executar(self, context, email, senha):
        if not email or not senha:
            raise ValueError(
                "APISUL_EMAIL/APISUL_SENHA não configurados (verifique o .env)."
            )

        page = context.new_page()
        login = LoginPage(page)

        try:
            print("🔐 Acessando página de login...")
            login.acessar()
            login.preencher_email(email)
            login.preencher_senha(senha)

            print("👉 Pronto para submeter login...")
            login.submit()

            page.wait_for_url("**/Inicio", timeout=30_000)
            print("✅ Login realizado com sucesso.")
        except Exception as e:
            print(f"❌ Falha ao fazer login na Apisul: {e}")
            page.close()
            raise

        return page
