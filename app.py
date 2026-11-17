import io
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lexer import imprimir_erros, imprimir_tabela, imprimir_tokens, tokenizar
from semantico import Semantico, imprimir_semantica
from sintatico import (
    Parser,
    desenhar_arvore,
    imprimir_arvores,
    imprimir_erros_sintaticos,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.setrecursionlimit(10000)

app = FastAPI(
    title="Compilador C — Analisador",
    description=(
        "Análise léxica, sintática e semântica de código C. "
        "Mesma lógica do compilador executado no terminal, com front web embutido."
    ),
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False), name="static")

_LOCK = threading.Lock()

LIMITE_CODIGO = 200_000


class RequisicaoAnalise(BaseModel):
    codigo: str = Field(
        default="",
        max_length=LIMITE_CODIGO,
        description="Código-fonte C a analisar.",
    )
    nome_arquivo: str = Field(
        default="",
        max_length=260,
        description="Nome do arquivo de origem exibido na interface.",
    )


def _tokens_json(tokens) -> List[Dict[str, Any]]:
    return [
        {
            "i": i,
            "tipo": t.tipo,
            "lexema": t.lexema,
            "linha": t.linha,
            "coluna": t.coluna,
        }
        for i, t in enumerate(tokens, 1)
    ]


def _simbolos_json(tabela) -> List[Dict[str, Any]]:
    return [
        {
            "ordem": s.ordem,
            "lexema": s.lexema,
            "categoria": s.categoria,
            "tipo": s.tipo,
            "linha": s.linha,
        }
        for s in tabela
    ]


def _erros_sintaticos_json(erros) -> List[Dict[str, Any]]:
    return [
        {
            "texto": str(e),
            "mensagem": e.mensagem,
            "linha": e.linha,
            "coluna": e.coluna,
            "falta_ponto_virgula": e.falta_ponto_virgula,
        }
        for e in erros
    ]


def _arvores_json(arvores) -> List[Dict[str, Any]]:
    return [
        {
            "comando": i,
            "linha": no.linha,
            "linhas": desenhar_arvore(no),
            "ast": no.para_dict(),
        }
        for i, no in enumerate(arvores, 1)
    ]


def analisar_codigo(codigo: str, nome_arquivo: str = "") -> Dict[str, Any]:
    """Roda as 3 fases e devolve (dados estruturados + relatório em texto)."""
    buffer = io.StringIO()
    dados: Dict[str, Any] = {}

    with _LOCK:
        with redirect_stdout(buffer):
            tokens, tabela, erros_lexicos = tokenizar(codigo)
            imprimir_tokens(tokens)
            imprimir_tabela(tabela)
            imprimir_erros(erros_lexicos)
            dados["simbolos"] = _simbolos_json(tabela)

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

    relatorio = buffer.getvalue()

    total_erros = len(erros_lexicos) + len(erros_sintaticos) + len(erros_semanticos)

    return {
        "relatorio": relatorio,
        "nome_arquivo": nome_arquivo,
        "tokens": _tokens_json(tokens),
        "simbolos": dados["simbolos"],
        "arvores": _arvores_json(arvores),
        "erros": {
            "lexicos": erros_lexicos,
            "sintaticos": _erros_sintaticos_json(erros_sintaticos),
            "semanticos": erros_semanticos,
            "avisos": avisos,
        },
        "resumo": {
            "tokens": len(tokens),
            "simbolos": len(dados["simbolos"]),
            "comandos": len(arvores),
            "lexicos": len(erros_lexicos),
            "sintaticos": len(erros_sintaticos),
            "semanticos": len(erros_semanticos),
            "avisos": len(avisos),
            "total_erros": total_erros,
        },
        "ok": total_erros == 0,
    }


@app.get("/", include_in_schema=False)
def pagina_inicial():
    """Front embutido no backend."""
    arquivo = STATIC_DIR / "index.html"
    if not arquivo.exists():
        raise HTTPException(status_code=404, detail="Interface não encontrada.")
    return FileResponse(str(arquivo))


@app.get("/api/saude", tags=["servidor"])
def saude():
    return {"status": "ok", "servidor": "compilador-c"}


@app.post("/api/analisar", tags=["compilador"])
def api_analisar(requisicao: RequisicaoAnalise):
    """Executa as 3 fases e devolve o relatório (texto) + os dados estruturados."""
    try:
        return analisar_codigo(requisicao.codigo, requisicao.nome_arquivo)
    except RecursionError:
        raise HTTPException(
            status_code=400,
            detail="Código muito profundamente aninhado para o parser.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha na análise: {exc}")


@app.post("/api/relatorio", tags=["compilador"], response_class=PlainTextResponse)
def api_relatorio(requisicao: RequisicaoAnalise):
    """Mesmo conteúdo do console, em texto puro (para salvar/inspecionar)."""
    try:
        return analisar_codigo(requisicao.codigo, requisicao.nome_arquivo)["relatorio"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha na análise: {exc}")


@app.get("/api/exemplos", tags=["compilador"])
def api_exemplos():
    """Arquivos de exemplo do próprio projeto, para carregar na interface."""
    exemplos = {}
    for nome in ("teste.c", "teste_erros.c", "teste_semantico.c"):
        caminho = BASE_DIR / nome
        if caminho.exists():
            try:
                exemplos[nome] = caminho.read_text(encoding="utf-8")
            except OSError:
                continue
    return {"exemplos": exemplos}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
