"""
Testes do servidor web (app.py) contra o mesmo pipeline do main.py.

Rodar:  python -m pytest -q
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: E402
from lexer import tokenizar  # noqa: E402
from semantico import Semantico  # noqa: E402
from sintatico import Parser  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
client = TestClient(app)


def codigo(nome):
    return (BASE / nome).read_text(encoding="utf-8")


# ----------------------------------------------------------------- API

def test_pagina_inicial_serve_o_front():
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    assert "static/app.js" in resposta.text


def test_saude():
    assert client.get("/api/saude").json()["status"] == "ok"


def test_exemplos_disponiveis():
    dados = client.get("/api/exemplos").json()
    assert "teste.c" in dados["exemplos"]


def test_analisar_codigo_valido():
    resposta = client.post("/api/analisar", json={"codigo": codigo("teste.c")})
    assert resposta.status_code == 200
    dados = resposta.json()

    assert dados["resumo"]["tokens"] == 55
    assert dados["resumo"]["simbolos"] == 11
    assert dados["resumo"]["comandos"] == 6
    assert dados["resumo"]["lexicos"] == 0
    assert dados["resumo"]["sintaticos"] == 0
    assert dados["resumo"]["semanticos"] == 1      # 'total' não declarado
    assert dados["ok"] is False

    assert dados["tokens"][0]["tipo"] == "DIRETIVA"
    assert dados["simbolos"][0]["lexema"] == "int"
    assert dados["arvores"][0]["comando"] == 1
    assert "Declaracao" in dados["arvores"][0]["linhas"][0]


def test_analisar_erros_lexicos():
    dados = client.post("/api/analisar", json={"codigo": codigo("teste_erros.c")}).json()
    assert dados["resumo"]["lexicos"] == 3
    assert dados["resumo"]["sintaticos"] == 2
    assert dados["resumo"]["comandos"] == 0
    assert dados["erros"]["lexicos"][0].startswith("[ERRO LÉXICO]")


def test_analisar_erros_semanticos():
    dados = client.post("/api/analisar", json={"codigo": codigo("teste_semantico.c")}).json()
    assert dados["resumo"]["semanticos"] == 6
    assert dados["resumo"]["avisos"] == 1
    assert dados["erros"]["avisos"][0].startswith("[AVISO SEMÂNTICO]")


def test_codigo_vazio_nao_quebra():
    resposta = client.post("/api/analisar", json={"codigo": ""})
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["resumo"]["total_erros"] == 0
    assert dados["ok"] is True
    assert dados["tokens"] == []


def test_codigo_ausente_usa_string_vazia():
    dados = client.post("/api/analisar", json={}).json()
    assert dados["resumo"]["total_erros"] == 0


def test_relatorio_em_texto_puro():
    resposta = client.post("/api/relatorio", json={"codigo": codigo("teste.c")})
    assert resposta.status_code == 200
    assert "text/plain" in resposta.headers["content-type"]
    assert resposta.text.startswith("=" * 62)
    assert "LISTA DE TOKENS" in resposta.text
    assert "RESUMO:" in resposta.text


# -------------------------------------------- relatório = saída do CLI

def _relatorio_cli(texto):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        tokens, tabela, erros_lexicos = tokenizar(texto)
        from lexer import imprimir_erros, imprimir_tabela, imprimir_tokens
        from semantico import imprimir_semantica
        from sintatico import imprimir_arvores, imprimir_erros_sintaticos
        imprimir_tokens(tokens)
        imprimir_tabela(tabela)
        imprimir_erros(erros_lexicos)
        print()
        arvores, erros_sintaticos = Parser(tokens).analisar()
        imprimir_arvores(arvores)
        imprimir_erros_sintaticos(erros_sintaticos)
        erros_semanticos, avisos = Semantico(tabela).analisar(arvores)
        imprimir_semantica(erros_semanticos, avisos)
        print()
        print("=" * 62)
        print(f"RESUMO: {len(erros_lexicos)} erro(s) léxico(s), "
              f"{len(erros_sintaticos)} sintático(s), "
              f"{len(erros_semanticos)} semântico(s), {len(avisos)} aviso(s)")
        print("=" * 62)
    return buffer.getvalue()


@pytest.mark.parametrize("arquivo", ["teste.c", "teste_erros.c", "teste_semantico.c"])
def test_relatorio_da_api_e_identico_ao_console(arquivo):
    texto = codigo(arquivo)
    esperado = _relatorio_cli(texto)
    obtido = client.post("/api/relatorio", json={"codigo": texto}).text
    assert obtido == esperado
