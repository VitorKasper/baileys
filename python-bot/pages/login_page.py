from pages.base_page import BasePage

class LoginPage(BasePage):

    def acessar(self):
        self.page.goto("https://novoapisullog.apisul.com.br/Login")

    def preencher_email(self, email):
        self.page.fill("input[name='txtUsuario']", email)

    def preencher_senha(self, senha):
        self.page.fill("input[name='txtSenha']", senha)

    def submit(self):
        self.page.click("input[name='btnLogin']")