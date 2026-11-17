"""
PARTE III - ANÁLISE SEMÂNTICA SIMPLIFICADA

Percorre as ASTs (na ordem do código) consultando a Tabela de Símbolos e
valida DUAS regras:

  Opção 2 - Variável não declarada:
      toda variável usada (no lado esquerdo ou dentro de uma expressão)
      precisa ter sido declarada ANTES, na ordem do arquivo.

  Opção 1 - Compatibilidade de tipos em atribuições/inicializações:
      o tipo da expressão atribuída deve ser compatível com o tipo
      declarado da variável.

Regras de tipo:
    destino int/short/long/char : aceita int e char; float -> AVISO; resto -> ERRO
    destino float/double        : aceita int, char e float; resto -> ERRO
    destino ponteiro (char *s)  : char* aceita String; todos aceitam int (ex.: 0)

Simplificação: um único escopo global (não há escopo de função/bloco).

Uso: python semantico.py arquivo.c
"""

INTEIROS = {"int", "short", "long", "char"}
REAIS = {"float", "double"}


def nome_do_tipo(tipo):
    return "String" if tipo == "string" else tipo


def compatibilidade(destino, origem):
    """Retorna 'ok', 'aviso' ou 'erro' para atribuir 'origem' a 'destino'."""
    if destino.endswith("*"):
        if origem == "int" or origem == destino:
            return "ok"
        if origem == "string" and destino == "char*":
            return "ok"
        return "erro"
    if destino in INTEIROS:
        if origem in ("int", "char"):
            return "ok"
        if origem == "float":
            return "aviso"          # float -> int perde a parte fracionária
        return "erro"
    if destino in REAIS:
        return "ok" if origem in ("int", "char", "float") else "erro"
    return "ok"


class Semantico:
    def __init__(self, tabela):
        self.tabela = tabela            # TabelaSimbolos criada pelo lexer
        self.declaradas = set()         # nomes já declarados até este ponto do código
        self.erros = []
        self.avisos = []

    # ---- ponto de entrada

    def analisar(self, arvores):
        for no in arvores:
            if no.tipo == "Declaracao":
                self.declaracao(no)
            elif no.tipo == "Atribuicao":
                self.atribuicao(no)
        return self.erros, self.avisos

    # ---- comandos

    def declaracao(self, no):
        tipo_base = no.filhos[0].lexema
        for declarador in no.filhos[1:]:
            ident = declarador.filhos[0]
            tipo = tipo_base + ("*" if declarador.lexema == "*" else "")

            # a declaração grava o tipo na Tabela de Símbolos
            self.tabela.buscar(ident.lexema).tipo = tipo
            self.declaradas.add(ident.lexema)

            if len(declarador.filhos) == 3:     # ID, OP_ATRIB, expressão
                origem = self.tipo_da_expressao(declarador.filhos[2])
                self.checar_atribuicao(tipo, origem, ident.linha)

    def atribuicao(self, no):
        ident, _op, expressao = no.filhos
        destino = self.tipo_da_variavel(ident)          # Opção 2 (lado esquerdo)
        origem = self.tipo_da_expressao(expressao)      # Opção 2 (lado direito)
        self.checar_atribuicao(destino, origem, ident.linha)

    # ---- tipos

    def tipo_da_variavel(self, no):
        """Consulta a Tabela de Símbolos; None se a variável não foi declarada."""
        if no.lexema not in self.declaradas:
            self.erros.append(
                f"[ERRO SEMÂNTICO] Variável '{no.lexema}' utilizada na linha "
                f"{no.linha} não foi declarada previamente.")
            return None
        return self.tabela.buscar(no.lexema).tipo

    def tipo_da_expressao(self, no):
        """Deduz o tipo da expressão; None quando é desconhecido (evita erros em cascata)."""
        if no.tipo == "NUM":
            return "int"
        if no.tipo == "NUM_REAL":
            return "float"
        if no.tipo == "STRING":
            return "string"
        if no.tipo == "CHAR":
            return "char"
        if no.tipo == "ID":
            return self.tipo_da_variavel(no)

        # Expressao binária
        esq = self.tipo_da_expressao(no.filhos[0])
        dir_ = self.tipo_da_expressao(no.filhos[1])
        if esq is None or dir_ is None:
            return None
        if "string" in (esq, dir_):
            self.erros.append(
                f"[ERRO SEMÂNTICO] Operador '{no.lexema}' na linha {no.linha}: "
                f"não é possível usar String em operação aritmética.")
            return None
        if esq.endswith("*") or dir_.endswith("*"):
            return None                 # aritmética de ponteiros: fora do escopo
        if esq in REAIS or dir_ in REAIS or "float" in (esq, dir_):
            return "float"
        return "int"

    # ---- Opção 1

    def checar_atribuicao(self, destino, origem, linha):
        if destino is None or origem is None:
            return                      # já houve erro de variável não declarada
        resultado = compatibilidade(destino, origem)
        if resultado == "erro":
            self.erros.append(
                f"[ERRO SEMÂNTICO] Incompatibilidade de tipos na linha {linha}: "
                f"Não é possível atribuir {nome_do_tipo(origem)} a um tipo {destino}.")
        elif resultado == "aviso":
            self.avisos.append(
                f"[AVISO SEMÂNTICO] Linha {linha}: atribuir {origem} a um tipo "
                f"{destino} pode perder precisão.")


# ---------------------------------------------------------------- exibição

def imprimir_semantica(erros, avisos):
    print()
    print("=" * 62)
    print("ANÁLISE SEMÂNTICA")
    print("=" * 62)
    if not erros and not avisos:
        print("Nenhum erro semântico encontrado.")
    for e in erros:
        print(e)
    for a in avisos:
        print(a)


def main():
    import sys
    from lexer import tokenizar
    from sintatico import Parser

    if len(sys.argv) != 2:
        print("Uso: python semantico.py arquivo.c")
        sys.exit(1)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    tokens, tabela, _erros_lexicos = tokenizar(codigo)
    arvores, _erros_sintaticos = Parser(tokens).analisar()
    erros, avisos = Semantico(tabela).analisar(arvores)
    imprimir_semantica(erros, avisos)


if __name__ == "__main__":
    main()
