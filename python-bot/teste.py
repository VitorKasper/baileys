"""
Scraper de Agendamentos - Onnolog (OpenGTM)
=============================================

Faz login no portal https://agendamento.onnolog.com.br, consulta o
relatório de agendamentos (reportScheduling) para um intervalo de datas
e salva os resultados em JSON e XLSX.

Uso:
    python scraper_agendamentos.py --start 05/07/2026 --end 06/07/2026

Credenciais e URL podem ser sobrescritas por variáveis de ambiente:
    ONNOLOG_LOGIN, ONNOLOG_PASSWORD, ONNOLOG_WAREHOUSE_ID
"""

import argparse
import json
import os
import re
import sys
import urllib3

import requests
from bs4 import BeautifulSoup
import pandas as pd

# Evita warnings de SSL (o site usa -k / --insecure nos exemplos de curl)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://agendamento.onnolog.com.br"

# --- Credenciais -------------------------------------------------------
# Recomendado: definir via variáveis de ambiente em vez de hardcode.
#   export ONNOLOG_LOGIN="pedro.torres3@ldc.com"
#   export ONNOLOG_PASSWORD="Onnolog@2026"
LOGIN = os.environ.get("ONNOLOG_LOGIN", "pedro.torres3@ldc.com")
PASSWORD = os.environ.get("ONNOLOG_PASSWORD", "Onnolog@2026")
WAREHOUSE_ID = os.environ.get("ONNOLOG_WAREHOUSE_ID", "2")

HEADERS_COMUNS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def criar_sessao() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS_COMUNS)
    return session


def login(session: requests.Session) -> None:
    """Executa o fluxo de login (GET da página + POST das credenciais)."""
    login_page_url = f"{BASE_URL}/opengtm/login/index"
    resp = session.get(login_page_url, verify=False, timeout=30)
    resp.raise_for_status()

    login_url = f"{BASE_URL}/opengtm/login/login"
    payload = {
        "login": LOGIN,
        "password": PASSWORD,
        "_action_login": "Entrar",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE_URL,
        "Referer": login_page_url,
    }
    resp = session.post(login_url, data=payload, headers=headers, verify=False, timeout=30)
    resp.raise_for_status()

    if "login" in resp.url and "index" in resp.url:
        raise RuntimeError("Login falhou - verifique usuário/senha.")


def buscar_relatorio(session: requests.Session, data_inicio: str, data_fim: str,
                      warehouse_id: str = WAREHOUSE_ID) -> str:
    """POST no reportScheduling/index e retorna o HTML da resposta."""
    referer = (
        f"{BASE_URL}/opengtm/reportScheduling/list"
        f"?format=&startDate={data_inicio}&endDate={data_fim}"
    )
    url = f"{BASE_URL}/opengtm/reportScheduling/index"

    payload = {
        "_action_list": "Pesquisa - F7",
        "warehouse.id": warehouse_id,
        "truckCode": "",
        "startDate": data_inicio,
        "endDate": data_fim,
        "owner": "",
        "roadOperationType": "",
        "code": "",
        "additionalServiceId": "",
        "serviceType": "",
        "_closeOperationStock": "",
        "schedulingProductDescription": "",
        "schedulingProductId": "",
        "schedulingProductCode": "",
        "schedulingLot": "",
        "schedulingQuotaManagement": "",
        "optionSeach": "S",
        "productResultFields": "",
        "code_arg": "",
        "inea_arg": "",
        "description_arg": "",
        "ownerResultFields": "",
        "nextSchedulingResultFields": "",
        "exceptId": "",
        "finishOperation": "",
        "refusedSchedulingJustificationId": "",
        "refusedNextSchedulingJustificationObs": "",
        "schedulingIdDelayed": "",
        "schedulingIdDocumentNotReceived": "",
        "justificationDelayed": "",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE_URL,
        "Referer": referer,
    }
    resp = session.post(url, data=payload, headers=headers, verify=False, timeout=30)
    resp.raise_for_status()
    return resp.text


def _texto_apos_label(partes: list, label: str) -> str:
    """Retorna o texto que vem logo após uma parte contendo `label`,
    ou o restante da própria parte se o valor estiver na mesma linha."""
    for i, parte in enumerate(partes):
        if label in parte:
            resto = parte.split(label, 1)[1].strip()
            if resto:
                return resto
            if i + 1 < len(partes):
                return partes[i + 1]
    return ""


def parse_relatorio(html: str) -> list:
    """Extrai cada linha da tabela 'scheduling-report' em um dicionário."""
    soup = BeautifulSoup(html, "html.parser")
    tabela = soup.find("table", class_="scheduling-report")
    if not tabela:
        return []

    corpo = tabela.find("tbody")
    linhas = corpo.find_all("tr", recursive=False)

    registros = []
    for linha in linhas:
        celulas = linha.find_all("td", recursive=False)
        if len(celulas) < 11:
            continue

        # 0: número da linha (ignorado)

        # 1: Placa + Transportadora
        partes_placa = [p for p in celulas[1].get_text(separator="|", strip=True).split("|") if p]
        placa = partes_placa[0] if partes_placa else ""
        transportadora = _texto_apos_label(partes_placa, "Transportadora:")

        # 2: Data/Hora
        data_hora = celulas[2].get_text(strip=True)

        # 3: Agendamento -> título tem SchedulingID e DocID
        titulo = celulas[3].get("title", "")
        m_sched = re.search(r"SchedulingID:\s*(\d+)", titulo)
        m_doc = re.search(r"DocID:\s*(\d+)", titulo)
        scheduling_id = m_sched.group(1) if m_sched else ""
        doc_id = m_doc.group(1) if m_doc else ""

        partes_agend = [p for p in celulas[3].get_text(separator="|", strip=True).split("|") if p]
        codigo_sc = partes_agend[0] if partes_agend else ""
        programacao = _texto_apos_label(partes_agend, "Programação:")

        # 4: Proprietário + Destinatário
        partes_prop = [p for p in celulas[4].get_text(separator="|", strip=True).split("|") if p]
        proprietario = partes_prop[0] if partes_prop else ""
        destinatario = _texto_apos_label(partes_prop, "Destinatário:")

        # 5: Produto (código + descrição)
        partes_produto = [p for p in celulas[5].get_text(separator="|", strip=True).split("|") if p]
        produto_codigo = partes_produto[0] if partes_produto else ""
        produto_descricao = partes_produto[1] if len(partes_produto) > 1 else ""

        # 6: Solicitado (KG)
        solicitado_kg = celulas[6].get_text(strip=True)

        # 7: Lote
        lote = celulas[7].get_text(strip=True)

        # 8: Motorista (nome, celular, CPF)
        partes_motorista = [p for p in celulas[8].get_text(separator="|", strip=True).split("|") if p]
        motorista_nome = partes_motorista[0] if partes_motorista else ""
        celular = _texto_apos_label(partes_motorista, "Cel:")
        cpf = _texto_apos_label(partes_motorista, "CPF:")

        # 9: Checklist
        checklist = celulas[9].get_text(strip=True)

        # 10: Status + link "Visualizar"
        celula_status = celulas[10]
        link_tag = celula_status.find("a", string=re.compile("Visualizar"))
        link_visualizar = f"{BASE_URL}{link_tag['href']}" if link_tag and link_tag.get("href") else ""
        div_status = celula_status.find("div", class_="alert")
        status = div_status.get_text(strip=True) if div_status else ""

        registros.append({
            "placa_veiculo": placa,
            "transportadora": transportadora,
            "data_hora": data_hora,
            "scheduling_id": scheduling_id,
            "doc_id": doc_id,
            "codigo_sc": codigo_sc,
            "programacao": programacao,
            "proprietario": proprietario,
            "destinatario": destinatario,
            "produto_codigo": produto_codigo,
            "produto_descricao": produto_descricao,
            "solicitado_kg": solicitado_kg,
            "lote": lote,
            "motorista_nome": motorista_nome,
            "motorista_celular": celular,
            "motorista_cpf": cpf,
            "checklist": checklist,
            "status": status,
            "link_visualizar": link_visualizar,
        })

    return registros


def salvar_json(registros: list, caminho: str) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)


def salvar_xlsx(registros: list, caminho: str) -> None:
    colunas = [
        "placa_veiculo", "transportadora", "data_hora", "scheduling_id", "doc_id",
        "codigo_sc", "programacao", "proprietario", "destinatario",
        "produto_codigo", "produto_descricao", "solicitado_kg", "lote",
        "motorista_nome", "motorista_celular", "motorista_cpf",
        "checklist", "status", "link_visualizar",
    ]
    df = pd.DataFrame(registros, columns=colunas)
    df.to_excel(caminho, index=False, sheet_name="Agendamentos")


def main():
    parser = argparse.ArgumentParser(description="Scraper de agendamentos Onnolog/OpenGTM")
    parser.add_argument("--start", default="05/07/2026", help="Data inicial (DD/MM/AAAA)")
    parser.add_argument("--end", default="06/07/2026", help="Data final (DD/MM/AAAA)")
    parser.add_argument("--warehouse", default=WAREHOUSE_ID, help="ID do armazém (warehouse.id)")
    parser.add_argument("--json-out", default="agendamentos.json")
    parser.add_argument("--xlsx-out", default="agendamentos.xlsx")
    args = parser.parse_args()

    session = criar_sessao()

    print("Fazendo login...", file=sys.stderr)
    login(session)

    print(f"Buscando agendamentos de {args.start} até {args.end}...", file=sys.stderr)
    html = buscar_relatorio(session, args.start, args.end, args.warehouse)

    registros = parse_relatorio(html)
    print(f"{len(registros)} agendamento(s) encontrado(s).", file=sys.stderr)

    salvar_json(registros, args.json_out)
    salvar_xlsx(registros, args.xlsx_out)
    print(f"Salvos em '{args.json_out}' e '{args.xlsx_out}'.", file=sys.stderr)


if __name__ == "__main__":
    main()