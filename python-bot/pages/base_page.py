class BasePage:
    def __init__(self, page):
        self.page = page

    def remover_popup_nps(self):
        """Remove o popup de pesquisa de satisfação (NPS) que o site injeta
        às vezes após uma pesquisa e que fica sobrepondo a página, bloqueando
        cliques em outros elementos."""
        self.page.evaluate("() => { document.getElementById('novoNPS')?.remove(); }")