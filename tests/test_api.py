"""
Testes do servidor web (app.py) contra o mesmo pipeline do main.py.

Rodar:  python -m pytest -q
"""
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app  # noqa: E402
from lexer import (  # noqa: E402
    imprimir_erros,
    imprimir_tabela,
    imprimir_tokens,
    tokenizar,
)
from semantico import Semantico, imprimir_semantica  # noqa: E402
from sintatico import (  # noqa: E402
    Parser,
    desenhar_arvore,
    imprimir_arvores,
    imprimir_erros_sintaticos,
)

BASE = Path(__file__).resolve().parents[1]
client = TestClient(app)


def codigo(nome):
    return (BASE / nome).read_text(encoding="utf-8")


def analisar(texto):
    return client.post("/api/analisar", json={"codigo": texto}).json()


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
    assert dados["resumo"]["semanticos"] == 1
    assert dados["ok"] is False

    assert dados["tokens"][0]["tipo"] == "DIRETIVA"
    assert dados["simbolos"][0]["lexema"] == "int"
    assert dados["arvores"][0]["comando"] == 1
    assert "Declaracao" in dados["arvores"][0]["linhas"][0]


def test_analisar_erros_lexicos():
    dados = analisar(codigo("teste_erros.c"))
    assert dados["resumo"]["lexicos"] == 3
    assert dados["resumo"]["sintaticos"] == 2
    assert dados["resumo"]["comandos"] == 0
    assert dados["erros"]["lexicos"][0].startswith("[ERRO LÉXICO]")


def test_analisar_erros_semanticos():
    dados = analisar(codigo("teste_semantico.c"))
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


def test_nome_do_arquivo_e_devolvido():
    dados = client.post(
        "/api/analisar", json={"codigo": "int a = 1;", "nome_arquivo": "aluno.c"}
    ).json()
    assert dados["nome_arquivo"] == "aluno.c"


def test_lexer_nao_acusa_operadores_validos_de_c():
    operadores = ["&", "|", "^", "~", "?", ":", "<<", ">>", "->", "&&", "||",
                  "!", "++", "--", "+=", "-=", "*=", "/=", "%="]
    for operador in operadores:
        tokens, _tabela, erros = tokenizar(f"x {operador} y;")
        assert erros == [], f"operador {operador} gerou erro léxico"
        assert len(tokens) == 4


def test_lexer_aceita_continuacao_de_linha():
    tokens, _tabela, erros = tokenizar("int x = 1 + \\\n    2;")
    assert erros == []
    assert tokens[-2].linha == 2


def test_lexer_ainda_acusa_caractere_invalido():
    _tokens, _tabela, erros = tokenizar("int x = 1 @ 2;")
    assert len(erros) == 1
    assert "Caractere inválido" in erros[0]


def test_tabela_de_simbolos_registra_tipo_de_ponteiro():
    dados = analisar('char *s = "Ana";\nint *a, b;\nint *c, *d;')
    tipos = {s["lexema"]: s["tipo"] for s in dados["simbolos"]}
    assert tipos["s"] == "char*"
    assert tipos["a"] == "int*"
    assert tipos["b"] == "int"
    assert tipos["c"] == "int*"
    assert tipos["d"] == "int*"


def test_ast_barema_de_x_mais_a_mais_5():
    tokens, _tabela, _erros = tokenizar("x = a + 5;")
    arvores, _erros_sintaticos = Parser(tokens).analisar()
    esperado = (
        "Atribuicao\n"
        "├── ID (x)\n"
        "├── OP_ATRIB (=)\n"
        "└── Expressao (+)\n"
        "    ├── ID (a)\n"
        "    └── NUM (5)"
    )
    assert desenhar_arvore(arvores[0]) == esperado.split("\n")


def test_mensagens_semanticas_barema():
    tokens, tabela, _erros = tokenizar('int resultado = "texto";')
    arvores, _erros_sintaticos = Parser(tokens).analisar()
    erros, _avisos = Semantico(tabela).analisar(arvores)
    assert erros == [
        "[ERRO SEMÂNTICO] Incompatibilidade de tipos na linha 1: "
        "Não é possível atribuir String a um tipo int."
    ]

    tokens, tabela, _erros = tokenizar("total = 10;")
    arvores, _erros_sintaticos = Parser(tokens).analisar()
    erros, _avisos = Semantico(tabela).analisar(arvores)
    assert erros == [
        "[ERRO SEMÂNTICO] Variável 'total' utilizada na linha 1 "
        "não foi declarada previamente."
    ]


def _relatorio_cli(texto):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        tokens, tabela, erros_lexicos = tokenizar(texto)
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


def test_main_do_terminal_continua_funcionando():
    processo = subprocess.run(
        [sys.executable, "main.py", "teste.c"],
        cwd=str(BASE),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert processo.returncode == 0
    assert "LISTA DE TOKENS" in processo.stdout
    assert "TABELA DE SÍMBOLOS" in processo.stdout
    assert "RESUMO:" in processo.stdout
