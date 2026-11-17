"""
Compilador/analisador simplificado de C

Executa, em sequência:
  I.   Análise Léxica      (lexer.py)     -> tokens + tabela de símbolos
  II.  Análise Sintática   (sintatico.py) -> AST
  III. Análise Semântica   (semantico.py) -> erros de tipo / variável não declarada

Uso: python main.py arquivo.c
"""
import sys

from lexer import imprimir_erros, imprimir_tabela, imprimir_tokens, tokenizar
from semantico import Semantico, imprimir_semantica
from sintatico import Parser, imprimir_arvores, imprimir_erros_sintaticos


def main():
    if len(sys.argv) != 2:
        print("Uso: python main.py arquivo.c")
        sys.exit(1)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    # I. Léxica
    tokens, tabela, erros_lexicos = tokenizar(codigo)
    imprimir_tokens(tokens)
    imprimir_tabela(tabela)
    imprimir_erros(erros_lexicos)

    # II. Sintática
    print()
    arvores, erros_sintaticos = Parser(tokens).analisar()
    imprimir_arvores(arvores)
    imprimir_erros_sintaticos(erros_sintaticos)

    # III. Semântica
    erros_semanticos, avisos = Semantico(tabela).analisar(arvores)
    imprimir_semantica(erros_semanticos, avisos)

    # Resumo
    print()
    print("=" * 62)
    print(f"RESUMO: {len(erros_lexicos)} erro(s) léxico(s), "
          f"{len(erros_sintaticos)} sintático(s), "
          f"{len(erros_semanticos)} semântico(s), {len(avisos)} aviso(s)")
    print("=" * 62)


if __name__ == "__main__":
    main()
