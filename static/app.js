/* ============================================================ helpers ==== */
const $ = (sel) => document.querySelector(sel);

const editor = $("#codigo");
const gutter = $("#gutter");
const contador = $("#contador");
const badge = $("#badge-status");

let ultimoRelatorio = "";
let ultimoNomeArquivo = "relatorio.txt";

/** Cria um elemento com texto seguro (nunca injeta HTML do código do usuário). */
function el(tag, texto, classe) {
  const node = document.createElement(tag);
  if (texto !== undefined && texto !== null) node.textContent = String(texto);
  if (classe) node.className = classe;
  return node;
}

function toast(mensagem, ok = false) {
  const t = $("#toast");
  t.textContent = mensagem;
  t.classList.toggle("ok", ok);
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.hidden = true; }, 4000);
}

/* ============================================================== abas ==== */
document.querySelectorAll(".aba").forEach((aba) => {
  aba.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach((a) => a.classList.remove("ativa"));
    document.querySelectorAll(".painel-conteudo > div").forEach((p) => {
      p.hidden = true;
      p.classList.remove("painel-visivel");
    });
    aba.classList.add("ativa");
    const painel = $("#p-" + aba.dataset.alvo);
    painel.hidden = false;
    painel.classList.add("painel-visivel");
  });
});

/* ============================================================ editor ==== */
function atualizarGutter() {
  const linhas = editor.value.split("\n").length;
  gutter.textContent = Array.from({ length: linhas }, (_, i) => i + 1).join("\n");
  contador.textContent =
    `${linhas} linha${linhas === 1 ? "" : "s"} · ${editor.value.length} caracteres`;
  gutter.scrollTop = editor.scrollTop;
}

editor.addEventListener("input", () => {
  atualizarGutter();
  localStorage.setItem("compilador-codigo", editor.value);
});

editor.addEventListener("scroll", () => { gutter.scrollTop = editor.scrollTop; });

editor.addEventListener("keydown", (ev) => {
  if (ev.key === "Tab") {
    ev.preventDefault();
    const inicio = editor.selectionStart;
    const fim = editor.selectionEnd;
    editor.value = editor.value.slice(0, inicio) + "    " + editor.value.slice(fim);
    editor.selectionStart = editor.selectionEnd = inicio + 4;
    atualizarGutter();
  }
  if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
    ev.preventDefault();
    analisar();
  }
});

/* =========================================================== chamada ==== */
async function analisar() {
  const botao = $("#btn-analisar");
  botao.disabled = true;
  botao.textContent = "Analisando…";
  badge.className = "badge badge-neutro";
  badge.textContent = "analisando…";

  try {
    const resposta = await fetch("/api/analisar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo: editor.value }),
    });

    if (!resposta.ok) {
      let detalhe = `HTTP ${resposta.status}`;
      try {
        const corpo = await resposta.json();
        if (corpo && corpo.detail) detalhe = corpo.detail;
      } catch (_) { /* resposta não-JSON */ }
      throw new Error(detalhe);
    }

    const dados = await resposta.json();
    ultimoRelatorio = dados.relatorio || "";
    render(dados);
  } catch (erro) {
    badge.className = "badge badge-erro";
    badge.textContent = "falha na análise";
    toast("Erro ao analisar: " + erro.message);
  } finally {
    botao.disabled = false;
    botao.textContent = "Analisar";
  }
}

/* =========================================================== render ==== */
function render(dados) {
  const r = dados.resumo;
  const erros = dados.erros;

  /* ---- badge do topo ---- */
  if (r.total_erros === 0) {
    badge.className = "badge badge-ok";
    badge.textContent = r.avisos > 0
      ? `análise concluída · ${r.avisos} aviso(s)`
      : "análise concluída · sem erros";
  } else {
    badge.className = "badge badge-erro";
    badge.textContent = `${r.total_erros} erro(s) encontrado(s)`;
  }

  /* ---- cartões do resumo ---- */
  const cartoes = $("#cartoes-resumo");
  cartoes.textContent = "";
  const cartoesDef = [
    ["Tokens", r.tokens, "info"],
    ["Símbolos", r.simbolos, "info"],
    ["Comandos (AST)", r.comandos, "info"],
    ["Erros léxicos", r.lexicos, r.lexicos ? "erro" : "ok"],
    ["Erros sintáticos", r.sintaticos, r.sintaticos ? "erro" : "ok"],
    ["Erros semânticos", r.semanticos, r.semanticos ? "erro" : "ok"],
    ["Avisos", r.avisos, r.avisos ? "aviso" : "ok"],
  ];
  cartoesDef.forEach(([nome, valor, tipo]) => {
    const c = el("div", null, "cartao " + tipo);
    c.appendChild(el("div", valor, "valor"));
    c.appendChild(el("div", nome, "nome"));
    cartoes.appendChild(c);
  });

  /* ---- fases ---- */
  const fases = $("#lista-fases");
  fases.textContent = "";
  const fase = (titulo, detalhe, tagTexto, tagClasse) => {
    const li = el("li");
    li.appendChild(el("b", titulo + " — "));
    li.appendChild(document.createTextNode(detalhe));
    const tag = el("span", tagTexto, "tag " + tagClasse);
    li.appendChild(tag);
    fases.appendChild(li);
  };
  fase("Análise léxica", `${r.tokens} token(s), ${r.simbolos} símbolo(s).`,
       r.lexicos ? `${r.lexicos} erro(s)` : "sem erros", r.lexicos ? "tag-erro" : "tag-ok");
  fase("Análise sintática", `${r.comandos} comando(s) reconhecido(s) pela gramática.`,
       r.sintaticos ? `${r.sintaticos} erro(s)` : "sem erros", r.sintaticos ? "tag-erro" : "tag-ok");
  fase("Análise semântica", "variáveis não declaradas e compatibilidade de tipos.",
       r.semanticos ? `${r.semanticos} erro(s)` : "sem erros", r.semanticos ? "tag-erro" : "tag-ok");

  /* ---- relatório ---- */
  $("#pre-relatorio").textContent = dados.relatorio || "(sem saída)";

  /* ---- tokens ---- */
  const corpoTokens = $("#corpo-tokens");
  corpoTokens.textContent = "";
  dados.tokens.forEach((t) => {
    const tr = el("tr");
    tr.dataset.busca = `${t.tipo} ${t.lexema}`.toLowerCase();
    tr.appendChild(el("td", t.i, "num"));
    tr.appendChild(el("td", t.tipo, "tipo-tag"));
    tr.appendChild(el("td", t.lexema, "lexema"));
    tr.appendChild(el("td", t.linha, "num"));
    tr.appendChild(el("td", t.coluna, "num"));
    corpoTokens.appendChild(tr);
  });
  $("#vazio-tokens").hidden = dados.tokens.length > 0;

  /* ---- símbolos ---- */
  const corpoSimbolos = $("#corpo-simbolos");
  corpoSimbolos.textContent = "";
  dados.simbolos.forEach((s) => {
    const tr = el("tr");
    tr.appendChild(el("td", s.ordem, "num"));
    tr.appendChild(el("td", s.lexema, "lexema"));
    tr.appendChild(el("td", s.categoria, "cat"));
    tr.appendChild(el("td", s.tipo || "-", "tipo-col"));
    tr.appendChild(el("td", s.linha, "num"));
    corpoSimbolos.appendChild(tr);
  });
  $("#vazio-simbolos").hidden = dados.simbolos.length > 0;

  /* ---- AST ---- */
  const listaAst = $("#lista-ast");
  listaAst.textContent = "";
  dados.arvores.forEach((arvore) => {
    const bloco = el("div", null, "comando");
    const cabeca = el("div", null, "comando-cabeca");
    cabeca.appendChild(el("b", `Comando ${arvore.comando}`));
    cabeca.appendChild(document.createTextNode(` (linha ${arvore.linha})`));
    bloco.appendChild(cabeca);
    bloco.appendChild(el("pre", arvore.linhas.join("\n")));
    listaAst.appendChild(bloco);
  });
  $("#rotulo-ast").textContent = `${dados.arvores.length} comando(s)`;
  $("#vazio-ast").hidden = dados.arvores.length > 0;

  /* ---- erros e avisos ---- */
  const listaErros = $("#lista-erros");
  listaErros.textContent = "";
  let total = 0;

  const grupo = (titulo) => {
    listaErros.appendChild(el("div", titulo, "grupo-titulo"));
  };
  const item = (texto, tag, aviso) => {
    const div = el("div", null, "erro-item" + (aviso ? " aviso" : ""));
    div.appendChild(el("span", tag, "origem"));
    div.appendChild(el("span", texto, "msg"));
    listaErros.appendChild(div);
    total += 1;
  };

  if (erros.lexicos.length) {
    grupo("Erros léxicos");
    erros.lexicos.forEach((e) => item(e, "léxico"));
  }
  if (erros.sintaticos.length) {
    grupo("Erros sintáticos");
    erros.sintaticos.forEach((e) => item(e.texto, "sintático"));
  }
  if (erros.semanticos.length) {
    grupo("Erros semânticos");
    erros.semanticos.forEach((e) => item(e, "semântico"));
  }
  if (erros.avisos.length) {
    grupo("Avisos");
    erros.avisos.forEach((a) => item(a, "aviso", true));
  }

  $("#rotulo-erros").textContent = `${total} ocorrência(s)`;
  $("#vazio-erros").hidden = total > 0;
}

/* ========================================================== filtros ==== */
$("#busca-tokens").addEventListener("input", (ev) => {
  const termo = ev.target.value.trim().toLowerCase();
  document.querySelectorAll("#corpo-tokens tr").forEach((tr) => {
    tr.hidden = termo !== "" && !tr.dataset.busca.includes(termo);
  });
});

/* ========================================================== botoes ==== */
$("#btn-analisar").addEventListener("click", analisar);

$("#btn-limpar").addEventListener("click", () => {
  editor.value = "";
  atualizarGutter();
  localStorage.removeItem("compilador-codigo");
  editor.focus();
});

$("#btn-copiar").addEventListener("click", async () => {
  if (!ultimoRelatorio) { toast("Rode a análise primeiro."); return; }
  try {
    await navigator.clipboard.writeText(ultimoRelatorio);
    toast("Relatório copiado para a área de transferência.", true);
  } catch (_) {
    toast("Não foi possível copiar (use Baixar .txt).");
  }
});

$("#btn-baixar").addEventListener("click", () => {
  if (!ultimoRelatorio) { toast("Rode a análise primeiro."); return; }
  const blob = new Blob([ultimoRelatorio], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = el("a");
  link.href = url;
  link.download = ultimoNomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
});

/* ========================================================= exemplos ==== */
async function carregarExemplos() {
  try {
    const resposta = await fetch("/api/exemplos");
    const dados = await resposta.json();
    const sel = $("#sel-exemplos");
    Object.entries(dados.exemplos || {}).forEach(([nome, conteudo]) => {
      const opcao = el("option", nome);
      opcao.value = nome;
      opcao.dataset.conteudo = conteudo;
      sel.appendChild(opcao);
    });
  } catch (_) { /* exemplos são opcionais */ }
}

$("#sel-exemplos").addEventListener("change", (ev) => {
  const opcao = ev.target.selectedOptions[0];
  if (!opcao || !opcao.value) return;
  editor.value = opcao.dataset.conteudo || "";
  ultimoNomeArquivo = opcao.value.replace(/\.c$/i, "") + "_relatorio.txt";
  atualizarGutter();
  localStorage.setItem("compilador-codigo", editor.value);
  ev.target.value = "";
  analisar();
});

/* ============================================================ inicio ==== */
const salvo = localStorage.getItem("compilador-codigo");
if (salvo) editor.value = salvo;
atualizarGutter();
carregarExemplos();
