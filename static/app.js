const $ = (sel) => document.querySelector(sel);

const editor = $("#codigo");
const gutter = $("#gutter");
const contador = $("#contador");
const contadorMobile = $("#contador-mobile");
const badge = $("#badge-status");
const entradaArquivo = $("#entrada-arquivo");
const editorCorpo = $("#editor-corpo");
const rotuloArquivo = $("#rotulo-arquivo");
const barraMobile = $("#barra-mobile");

let ultimoRelatorio = "";
let nomeAtual = "";
let ultimoNomeArquivo = "relatorio.txt";

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

function ehTelaPequena() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function ajustarAlturaBarra() {
  if (!barraMobile) return;
  const altura = barraMobile.offsetHeight;
  document.documentElement.style.setProperty("--altura-barra-mobile", altura + "px");
}

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

function atualizarGutter() {
  const linhas = editor.value.split("\n").length;
  gutter.textContent = Array.from({ length: linhas }, (_, i) => i + 1).join("\n");
  const texto = `${linhas} linha${linhas === 1 ? "" : "s"} · ${editor.value.length} caracteres`;
  contador.textContent = texto;
  contadorMobile.textContent = `${linhas} linha${linhas === 1 ? "" : "s"}`;
  gutter.scrollTop = editor.scrollTop;
}

function marcarArquivo(nome) {
  nomeAtual = nome || "";
  if (nomeAtual) {
    rotuloArquivo.textContent = nomeAtual;
    rotuloArquivo.hidden = false;
    rotuloArquivo.title = nomeAtual;
    ultimoNomeArquivo = nomeAtual.replace(/\.[^.]+$/, "") + "_relatorio.txt";
  } else {
    rotuloArquivo.hidden = true;
    rotuloArquivo.textContent = "";
    ultimoNomeArquivo = "relatorio.txt";
  }
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

function lerArquivo(arquivo) {
  if (!arquivo) return;
  const leitor = new FileReader();
  leitor.onload = () => {
    editor.value = String(leitor.result || "");
    atualizarGutter();
    localStorage.setItem("compilador-codigo", editor.value);
    marcarArquivo(arquivo.name);
    toast(`Arquivo “${arquivo.name}” carregado.`, true);
    analisar();
  };
  leitor.onerror = () => toast("Não foi possível ler o arquivo.");
  leitor.readAsText(arquivo);
}

$("#btn-abrir").addEventListener("click", () => entradaArquivo.click());

entradaArquivo.addEventListener("change", () => {
  lerArquivo(entradaArquivo.files[0]);
  entradaArquivo.value = "";
});

["dragenter", "dragover"].forEach((evento) => {
  editorCorpo.addEventListener(evento, (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    editorCorpo.classList.add("soltando");
  });
});

["dragleave", "dragend"].forEach((evento) => {
  editorCorpo.addEventListener(evento, (ev) => {
    ev.preventDefault();
    editorCorpo.classList.remove("soltando");
  });
});

editorCorpo.addEventListener("drop", (ev) => {
  ev.preventDefault();
  editorCorpo.classList.remove("soltando");
  const arquivo = ev.dataTransfer && ev.dataTransfer.files[0];
  if (!arquivo) return;
  if (!/\.(c|h|txt)$/i.test(arquivo.name)) {
    toast("Formato não suportado. Envie um arquivo .c, .h ou .txt.");
    return;
  }
  lerArquivo(arquivo);
});

window.addEventListener("dragover", (ev) => ev.preventDefault());
window.addEventListener("drop", (ev) => ev.preventDefault());

async function analisar() {
  const botoes = [$("#btn-analisar"), $("#btn-analisar-mobile")];
  botoes.forEach((b) => { b.disabled = true; });
  const rotuloOriginal = $("#btn-analisar").textContent;
  $("#btn-analisar").textContent = "Analisando…";
  badge.className = "badge badge-neutro";
  badge.textContent = "analisando…";

  try {
    const resposta = await fetch("/api/analisar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo: editor.value, nome_arquivo: nomeAtual }),
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

    if (ehTelaPequena()) {
      $("#resultado-coluna").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (erro) {
    badge.className = "badge badge-erro";
    badge.textContent = "falha na análise";
    toast("Erro ao analisar: " + erro.message);
  } finally {
    botoes.forEach((b) => { b.disabled = false; });
    $("#btn-analisar").textContent = rotuloOriginal;
  }
}

function render(dados) {
  const r = dados.resumo;
  const erros = dados.erros;

  if (r.total_erros === 0) {
    badge.className = "badge badge-ok";
    badge.textContent = r.avisos > 0
      ? `análise concluída · ${r.avisos} aviso(s)`
      : "análise concluída · sem erros";
  } else {
    badge.className = "badge badge-erro";
    badge.textContent = `${r.total_erros} erro(s) encontrado(s)`;
  }

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

  const fases = $("#lista-fases");
  fases.textContent = "";
  const fase = (titulo, detalhe, tagTexto, tagClasse) => {
    const li = el("li");
    li.appendChild(el("b", titulo + " — "));
    li.appendChild(document.createTextNode(detalhe));
    li.appendChild(el("span", tagTexto, "tag " + tagClasse));
    fases.appendChild(li);
  };
  fase("Análise léxica", `${r.tokens} token(s), ${r.simbolos} símbolo(s).`,
       r.lexicos ? `${r.lexicos} erro(s)` : "sem erros", r.lexicos ? "tag-erro" : "tag-ok");
  fase("Análise sintática", `${r.comandos} comando(s) reconhecido(s) pela gramática.`,
       r.sintaticos ? `${r.sintaticos} erro(s)` : "sem erros", r.sintaticos ? "tag-erro" : "tag-ok");
  fase("Análise semântica", "variáveis não declaradas e compatibilidade de tipos.",
       r.semanticos ? `${r.semanticos} erro(s)` : "sem erros", r.semanticos ? "tag-erro" : "tag-ok");

  $("#pre-relatorio").textContent = dados.relatorio || "(sem saída)";

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

  const listaErros = $("#lista-erros");
  listaErros.textContent = "";
  let total = 0;

  const grupo = (titulo) => { listaErros.appendChild(el("div", titulo, "grupo-titulo")); };
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

$("#busca-tokens").addEventListener("input", (ev) => {
  const termo = ev.target.value.trim().toLowerCase();
  document.querySelectorAll("#corpo-tokens tr").forEach((tr) => {
    tr.hidden = termo !== "" && !tr.dataset.busca.includes(termo);
  });
});

$("#btn-analisar").addEventListener("click", analisar);
$("#btn-analisar-mobile").addEventListener("click", analisar);

$("#btn-limpar").addEventListener("click", () => {
  editor.value = "";
  marcarArquivo("");
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
  marcarArquivo(opcao.value);
  atualizarGutter();
  localStorage.setItem("compilador-codigo", editor.value);
  ev.target.value = "";
  analisar();
});

window.addEventListener("resize", ajustarAlturaBarra);

const salvo = localStorage.getItem("compilador-codigo");
if (salvo) editor.value = salvo;
atualizarGutter();
ajustarAlturaBarra();
carregarExemplos();

const parametros = new URLSearchParams(window.location.search);
const codigoPelaUrl = parametros.get("codigo");
if (codigoPelaUrl) {
  editor.value = codigoPelaUrl;
  marcarArquivo(parametros.get("arquivo") || "");
  atualizarGutter();
  analisar();
}
