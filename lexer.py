"""
PARTE I - ANÁLISE LÉXICA
Lê um arquivo .c e produz:
  1. Lista de tokens (tipo, lexema, linha, coluna)
  2. Tabela de Símbolos (identificadores e palavras reservadas, com tipo e ordem de inserção)
  3. Lista de erros léxicos

Uso: python lexer.py arquivo.c
"""
import re
import sys
from dataclasses import dataclass
from typing import Optional

PALAVRAS_RESERVADAS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if", "int",
    "long", "register", "return", "short", "signed", "sizeof", "static",
    "struct", "switch", "typedef", "union", "unsigned", "void", "volatile",
    "while",
}

TIPOS = {"int", "float", "char", "double", "void", "long", "short"}

ESPECIFICACAO_TOKENS = [
    ("COMENTARIO_LINHA",  r"//[^\n]*"),
    ("COMENTARIO_BLOCO",  r"/\*.*?\*/"),
    ("COMENTARIO_ABERTO", r"/\*.*"),
    ("CONTINUACAO_LINHA", r"\\\r?\n"),
    ("DIRETIVA",          r"\#[^\n]*"),
    ("STRING",            r'"(?:\\.|[^"\\\n])*"'),
    ("ERRO_STRING",       r'"[^"\n]*'),
    ("CHAR",              r"'(?:\\.|[^'\\\n])'"),
    ("ERRO_CHAR",         r"'[^'\n]*'?"),
    ("ERRO_NUMERO",       r"\d+(?:\.\d+)?[A-Za-z_]\w*"),
    ("NUM_REAL",          r"\d+\.\d+"),
    ("NUM_INT",           r"\d+"),
    ("ID",                r"[A-Za-z_]\w*"),
    ("OP_SHIFT",          r"<<|>>"),
    ("OP_REL",            r"==|!=|<=|>=|<|>"),
    ("OP_ATRIB_COMP",     r"\+=|-=|\*=|/=|%="),
    ("OP_INCDEC",         r"\+\+|--"),
    ("OP_LOGICO",         r"&&|\|\||!"),
    ("OP_BIT_AND",        r"&"),
    ("OP_BIT_OR",         r"\|"),
    ("OP_BIT_XOR",        r"\^"),
    ("OP_BIT_NOT",        r"~"),
    ("OP_TERNO",          r"\?"),
    ("OP_DOIS_PONTOS",    r":"),
    ("OP_SETA",           r"->"),
    ("OP_ATRIB",          r"="),
    ("OP_ARIT",           r"[+\-*/%]"),
    ("PONTO_VIRGULA",     r";"),
    ("VIRGULA",           r","),
    ("ABRE_PAR",          r"\("),
    ("FECHA_PAR",         r"\)"),
    ("ABRE_CHAVE",        r"\{"),
    ("FECHA_CHAVE",       r"\}"),
    ("ABRE_COLCH",        r"\["),
    ("FECHA_COLCH",       r"\]"),
    ("NOVA_LINHA",        r"\n"),
    ("ESPACO",            r"[ \t\r]+"),
    ("ERRO_CARACTERE",    r"."),
]

REGEX_MESTRE = re.compile(
    "|".join(f"(?P<{nome}>{padrao})" for nome, padrao in ESPECIFICACAO_TOKENS),
    re.DOTALL,
)

IGNORADOS = {
    "COMENTARIO_LINHA", "COMENTARIO_BLOCO", "ESPACO", "NOVA_LINHA",
    "CONTINUACAO_LINHA",
}

MENSAGENS_ERRO = {
    "COMENTARIO_ABERTO": "Comentário de bloco não foi fechado",
    "ERRO_STRING": "String não foi fechada",
    "ERRO_CHAR": "Constante de caractere mal formada",
    "ERRO_NUMERO": "Número mal formado (identificador começando com dígito)",
    "ERRO_CARACTERE": "Caractere inválido",
}


@dataclass
class Token:
    tipo: str
    lexema: str
    linha: int
    coluna: int


@dataclass
class Simbolo:
    ordem: int
    lexema: str
    categoria: str
    tipo: Optional[str]
    linha: int


class TabelaSimbolos:
    def __init__(self):
        self._simbolos = {}

    def inserir(self, lexema, categoria, linha, tipo=None):
        simbolo = self._simbolos.get(lexema)
        if simbolo is None:
            simbolo = Simbolo(len(self._simbolos) + 1, lexema, categoria, tipo, linha)
            self._simbolos[lexema] = simbolo
        elif tipo is not None and simbolo.tipo is None:
            simbolo.tipo = tipo
        return simbolo

    def buscar(self, lexema):
        return self._simbolos.get(lexema)

    def __iter__(self):
        return iter(self._simbolos.values())

    def __len__(self):
        return len(self._simbolos)


def tokenizar(codigo):
    """Retorna (tokens, tabela_de_simbolos, erros)."""
    tokens = []
    erros = []
    tabela = TabelaSimbolos()

    linha = 1
    inicio_linha = 0
    tipo_pendente = None
    ponteiro_pendente = False
    anterior = None

    for m in REGEX_MESTRE.finditer(codigo):
        tipo = m.lastgroup
        lexema = m.group()
        coluna = m.start() - inicio_linha + 1

        quebras = lexema.count("\n")

        if tipo in MENSAGENS_ERRO:
            erros.append(f"[ERRO LÉXICO] {MENSAGENS_ERRO[tipo]} na linha {linha}, "
                         f"coluna {coluna}: {lexema.splitlines()[0]!r}")
        elif tipo not in IGNORADOS:
            if tipo == "ID" and lexema in PALAVRAS_RESERVADAS:
                tipo = "PALAVRA_RESERVADA"

            token = Token(tipo, lexema, linha, coluna)
            tokens.append(token)

            if tipo == "PALAVRA_RESERVADA":
                tabela.inserir(lexema, "PALAVRA_RESERVADA", linha)
                if lexema in TIPOS:
                    tipo_pendente = lexema
                    ponteiro_pendente = False
            elif tipo == "ID":
                eh_declaracao = (
                    tipo_pendente is not None and anterior is not None and (
                        anterior.lexema in TIPOS
                        or anterior.tipo == "VIRGULA"
                        or anterior.lexema == "*"
                    )
                )
                tipo_declarado = None
                if eh_declaracao:
                    tipo_declarado = tipo_pendente + ("*" if ponteiro_pendente else "")
                tabela.inserir(lexema, "IDENTIFICADOR", linha, tipo_declarado)
                ponteiro_pendente = False
            elif tipo == "OP_ARIT" and lexema == "*":
                ponteiro_pendente = True
            elif tipo in ("PONTO_VIRGULA", "ABRE_PAR", "FECHA_PAR",
                          "ABRE_CHAVE", "FECHA_CHAVE"):
                tipo_pendente = None
                ponteiro_pendente = False

            anterior = token

        if quebras:
            linha += quebras
            inicio_linha = m.start() + lexema.rfind("\n") + 1

    return tokens, tabela, erros


def imprimir_tokens(tokens):
    print("=" * 62)
    print("LISTA DE TOKENS")
    print("=" * 62)
    print(f"{'#':<4}{'TIPO':<20}{'LEXEMA':<24}{'LINHA':<7}{'COL'}")
    print("-" * 62)
    for i, t in enumerate(tokens, 1):
        print(f"{i:<4}{t.tipo:<20}{t.lexema:<24}{t.linha:<7}{t.coluna}")


def imprimir_tabela(tabela):
    print()
    print("=" * 62)
    print("TABELA DE SÍMBOLOS (ordem de inserção)")
    print("=" * 62)
    print(f"{'ORD':<5}{'LEXEMA':<20}{'CATEGORIA':<20}{'TIPO':<10}{'LINHA'}")
    print("-" * 62)
    for s in tabela:
        print(f"{s.ordem:<5}{s.lexema:<20}{s.categoria:<20}{s.tipo or '-':<10}{s.linha}")


def imprimir_erros(erros):
    print()
    print("=" * 62)
    print("ERROS LÉXICOS")
    print("=" * 62)
    if not erros:
        print("Nenhum erro léxico encontrado.\n")
    for e in erros:
        print(e)


def main():
    if len(sys.argv) != 2:
        print("Uso: python lexer.py arquivo.c")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    tokens, tabela, erros = tokenizar(codigo)
    imprimir_tokens(tokens)
    imprimir_tabela(tabela)
    imprimir_erros(erros)


if __name__ == "__main__":
    main()
