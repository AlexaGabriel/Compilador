"""
PARTE II - ANÁLISE SINTÁTICA SIMPLIFICADA + AST

Parser descendente recursivo (um método por regra da gramática).
Reconhece apenas dois tipos de comando; o resto do código C (#include,
main(), if, return...) é ignorado nesta etapa.

Gramática livre de contexto (BNF):

    <Declaracao> ::= <tipo> <declarador> ( "," <declarador> )* ";"
    <declarador> ::= ( "*" )? <identificador> ( "=" <Expressao> )?
    <Atribuicao> ::= <identificador> "=" <Expressao> ";"
    <Expressao>  ::= <produto> ( ( "+" | "-" ) <produto> )*
    <produto>    ::= <termo> ( ( "*" | "/" ) <termo> )*
    <termo>      ::= <identificador> | <numero> | <string> | <caractere>

(A gramática do enunciado é <termo> (+|-) <termo>; esta é uma extensão
mínima que aceita 'b / 2.5', 'a + b + c' e respeita a precedência de * e /.)

Uso: python sintatico.py arquivo.c [--json]
"""
import json
import sys
from dataclasses import dataclass, field

from lexer import TIPOS, tokenizar

TERMOS = {
    "ID": "ID",
    "NUM_INT": "NUM",
    "NUM_REAL": "NUM_REAL",
    "STRING": "STRING",
    "CHAR": "CHAR",
}


@dataclass
class No:
    tipo: str
    lexema: str = ""
    linha: int = 0
    filhos: list = field(default_factory=list)

    def rotulo(self):
        return f"{self.tipo} ({self.lexema})" if self.lexema else self.tipo

    def para_dict(self):
        d = {"tipo": self.tipo, "linha": self.linha}
        if self.lexema:
            d["lexema"] = self.lexema
        if self.filhos:
            d["filhos"] = [f.para_dict() for f in self.filhos]
        return d


def desenhar_arvore(raiz):
    """Devolve a AST como linhas de texto com ├── └── │."""
    linhas = [raiz.rotulo()]

    def percorrer(no, prefixo):
        for i, filho in enumerate(no.filhos):
            ultimo = i == len(no.filhos) - 1
            linhas.append(prefixo + ("└── " if ultimo else "├── ") + filho.rotulo())
            percorrer(filho, prefixo + ("    " if ultimo else "│   "))

    percorrer(raiz, "")
    return linhas


class ErroSintatico(Exception):
    def __init__(self, mensagem, linha, coluna, falta_ponto_virgula=False):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna
        self.falta_ponto_virgula = falta_ponto_virgula

    def __str__(self):
        return (f"[ERRO SINTÁTICO] Linha {self.linha}, coluna {self.coluna}: "
                f"{self.mensagem}")


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def atual(self, deslocamento=0):
        i = self.pos + deslocamento
        return self.tokens[i] if i < len(self.tokens) else None

    def avancar(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def erro(self, esperado):
        t = self.atual()
        if t is None:
            ult = self.tokens[-1]
            return ErroSintatico(f"{esperado}, mas o arquivo terminou",
                                 ult.linha, ult.coluna + len(ult.lexema))
        return ErroSintatico(f"{esperado}, encontrado '{t.lexema}'", t.linha, t.coluna)

    def esperar(self, tipo, descricao):
        t = self.atual()
        if t is None or t.tipo != tipo:
            raise self.erro(f"esperado {descricao}")
        return self.avancar()

    def esperar_ponto_virgula(self):
        t = self.atual()
        if t is None or t.tipo != "PONTO_VIRGULA":
            ant = self.tokens[self.pos - 1]
            raise ErroSintatico(f"esperado ';' após '{ant.lexema}'",
                                ant.linha, ant.coluna + len(ant.lexema),
                                falta_ponto_virgula=True)
        return self.avancar()

    def termo(self):
        t = self.atual()
        if t is None or t.tipo not in TERMOS:
            raise self.erro("esperado identificador, número, string ou caractere")
        self.avancar()
        return No(TERMOS[t.tipo], t.lexema, t.linha)

    def _binaria(self, operando, operadores):
        """Operador binário associativo à esquerda: operando (op operando)*"""
        esquerda = operando()
        while True:
            t = self.atual()
            if t is None or t.tipo != "OP_ARIT" or t.lexema not in operadores:
                return esquerda
            self.avancar()
            direita = operando()
            esquerda = No("Expressao", t.lexema, t.linha, [esquerda, direita])

    def produto(self):
        return self._binaria(self.termo, "*/")

    def expressao(self):
        return self._binaria(self.produto, "+-")

    def atribuicao(self):
        ident = self.avancar()
        op = self.esperar("OP_ATRIB", "'='")
        expr = self.expressao()
        self.esperar_ponto_virgula()
        return No("Atribuicao", "", ident.linha, [
            No("ID", ident.lexema, ident.linha),
            No("OP_ATRIB", op.lexema, op.linha),
            expr,
        ])

    def declaracao(self):
        tipo = self.avancar()
        no = No("Declaracao", "", tipo.linha, [No("TIPO", tipo.lexema, tipo.linha)])
        while True:
            ponteiro = False
            while self._eh_asterisco(self.atual()):
                self.avancar()
                ponteiro = True
            ident = self.esperar("ID", "identificador")
            declarador = No("Declarador", "*" if ponteiro else "", ident.linha,
                            [No("ID", ident.lexema, ident.linha)])
            t = self.atual()
            if t is not None and t.tipo == "OP_ATRIB":
                self.avancar()
                declarador.filhos.append(No("OP_ATRIB", "=", t.linha))
                declarador.filhos.append(self.expressao())
            no.filhos.append(declarador)

            t = self.atual()
            if t is not None and t.tipo == "VIRGULA":
                self.avancar()
                continue
            break
        self.esperar_ponto_virgula()
        return no

    @staticmethod
    def _eh_asterisco(t):
        return t is not None and t.tipo == "OP_ARIT" and t.lexema == "*"

    def _inicia_declaracao(self):
        t = self.atual()
        if not (t.tipo == "PALAVRA_RESERVADA" and t.lexema in TIPOS):
            return False
        k = 1
        while self._eh_asterisco(self.atual(k)):
            k += 1
        prox, depois = self.atual(k), self.atual(k + 1)
        return (prox is not None and prox.tipo == "ID"
                and not (depois is not None and depois.tipo == "ABRE_PAR"))

    def _inicia_atribuicao(self):
        t, prox = self.atual(), self.atual(1)
        return t.tipo == "ID" and prox is not None and prox.tipo == "OP_ATRIB"

    def _sincronizar(self, inicio, erro):
        """Recuperação de erro: pula até o fim do comando para continuar analisando."""
        self.pos = max(self.pos, inicio + 1)
        if erro.falta_ponto_virgula:
            return
        while self.pos < len(self.tokens):
            t = self.tokens[self.pos]
            if t.tipo == "PONTO_VIRGULA":
                self.pos += 1
                return
            if t.tipo in ("ABRE_CHAVE", "FECHA_CHAVE"):
                return
            self.pos += 1

    def analisar(self):
        """Retorna (lista_de_ASTs, lista_de_erros)."""
        arvores, erros = [], []
        parenteses = 0
        while self.pos < len(self.tokens):
            t = self.atual()
            inicio = self.pos
            try:
                if parenteses == 0 and self._inicia_declaracao():
                    arvores.append(self.declaracao())
                elif parenteses == 0 and self._inicia_atribuicao():
                    arvores.append(self.atribuicao())
                else:
                    if t.tipo == "ABRE_PAR":
                        parenteses += 1
                    elif t.tipo == "FECHA_PAR":
                        parenteses = max(0, parenteses - 1)
                    self.pos += 1
            except ErroSintatico as e:
                erros.append(e)
                self._sincronizar(inicio, e)
        return arvores, erros


def imprimir_arvores(arvores):
    print("=" * 62)
    print("ANÁLISE SINTÁTICA - ÁRVORES SINTÁTICAS (AST)")
    print("=" * 62)
    for i, arvore in enumerate(arvores, 1):
        print(f"\nComando {i} (linha {arvore.linha}):")
        print("\n".join(desenhar_arvore(arvore)))


def imprimir_erros_sintaticos(erros):
    print()
    print("=" * 62)
    print("ERROS SINTÁTICOS")
    print("=" * 62)
    if not erros:
        print("Nenhum erro sintático encontrado.\n")
    for e in erros:
        print(e)


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    em_json = "--json" in sys.argv
    if len(argumentos) != 1:
        print("Uso: python sintatico.py arquivo.c [--json]")
        sys.exit(1)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    with open(argumentos[0], encoding="utf-8") as f:
        codigo = f.read()

    tokens, _tabela, erros_lexicos = tokenizar(codigo)
    arvores, erros = Parser(tokens).analisar()

    if em_json:
        print(json.dumps([a.para_dict() for a in arvores], indent=2, ensure_ascii=False))
        return

    for e in erros_lexicos:
        print(e)
    if erros_lexicos:
        print()

    imprimir_arvores(arvores)
    imprimir_erros_sintaticos(erros)


if __name__ == "__main__":
    main()
