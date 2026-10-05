// Verificação visual e automática de acessibilidade da interface local (ferramenta de desenvolvimento; NÃO roda na suíte).
// Pré-requisitos, fora do projeto: npm install playwright-core axe-core (numa pasta qualquer) e Chromium em /opt/pw-browsers.
// Uso: scripts/interface.sh (em outro terminal) e depois
//      NODE_PATH=<pasta>/node_modules node scripts/verificar_interface.js http://127.0.0.1:8765 saida/capturas
// O axe-core cobre só o que é automático (cerca de um terço dos critérios WCAG); leitor de tela e teste com usuários
// continuam NÃO EXECUTADOS. bypassCSP é usado só aqui, para injetar o axe-core na página.
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");
const BASE = process.argv[2] || "http://127.0.0.1:8765";
const OUT = process.argv[3] || "capturas";
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const CHROME = fs.readdirSync("/opt/pw-browsers").filter((d) => d.startsWith("chromium-")).map((d) => `/opt/pw-browsers/${d}/chrome-linux/chrome`)[0];
fs.mkdirSync(OUT, { recursive: true });

async function medir(page, largura) {
  return page.evaluate((largura) => {
    const doc = document.documentElement;
    const largos = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && (r.right > largura + 1 || r.left < -1) && getComputedStyle(el).position !== "absolute") {
        largos.push(`${el.tagName.toLowerCase()}.${el.className || ""} (${Math.round(r.left)}..${Math.round(r.right)})`);
      }
    }
    const pequenos = [];
    for (const el of document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary, label.opcao")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      // links dentro de texto corrido são exceção do critério 2.5.8 (WCAG 2.2): só contamos controles e links "soltos"
      const emTexto = el.tagName === "A" && el.closest("p, li, td, figcaption") && !el.classList.contains("botao");
      if (!emTexto && (r.height < 44 || r.width < 44)) {
        pequenos.push(`${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${el.className ? "." + el.className : ""} "${(el.innerText || el.value || el.getAttribute("aria-label") || "").trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
      }
    }
    const cortados = [];
    for (const el of document.querySelectorAll("body *")) {
      const cs = getComputedStyle(el);
      if ((cs.overflow === "hidden" || cs.overflowX === "hidden" || cs.textOverflow === "ellipsis") && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
        cortados.push(`${el.tagName.toLowerCase()}.${el.className}`);
      }
    }
    const tabelasExcedem = [...document.querySelectorAll("table")].filter((t) =>
      t.getBoundingClientRect().right > t.parentElement.getBoundingClientRect().right + 1).map((t) => (t.caption || {}).innerText);
    const titulos = [...document.querySelectorAll("h1,h2,h3,h4")].map((h) => +h.tagName[1]);
    let salto = false;
    for (let i = 1; i < titulos.length; i++) if (titulos[i] > titulos[i - 1] + 1) salto = true;
    return {
      rolagem_horizontal: doc.scrollWidth > doc.clientWidth, tabelas_excedem: tabelasExcedem,
      scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth,
      largos: largos.slice(0, 8), pequenos: pequenos.slice(0, 12), n_pequenos: pequenos.length, cortados: cortados.slice(0, 8),
      h1: document.querySelectorAll("h1").length, salto_de_titulo: salto,
      proxima_acao: !!document.querySelector(".proxima"),
      faixa: document.body.innerText.includes("PROTÓTIPO DE TESTE, SEM VALIDADE CIENTÍFICA"),
    };
  }, largura);
}

async function axe(page) {
  await page.addScriptTag({ content: AXE });
  return page.evaluate(async () => {
    const r = await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] } });
    return {
      violacoes: r.violations.map((v) => ({ id: v.id, impacto: v.impact, n: v.nodes.length, alvo: v.nodes.slice(0, 3).map((n) => n.target.join(" ")), resumo: v.help })),
      incompletos: r.incomplete.map((v) => ({ id: v.id, n: v.nodes.length,
        nos: v.nodes.slice(0, 20).map((n) => ({ alvo: n.target.join(" "), dados: (n.any[0] || {}).data || null,
                                                 motivo: ((n.any[0] || {}).message || "").slice(0, 160) })) })),
      aprovadas: r.passes.length,
    };
  });
}

async function entrar(page, usuario) {
  await page.goto(BASE + "/entrar");
  await Promise.all([page.waitForURL("**/painel"),
                     page.click(`form[action='/entrar']:has(input[name=usuario][value=${usuario}]) button[type=submit]`)]);
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
  const relatorio = [];
  // descobre ids uma vez
  let demandaIds = [];
  {
    const ctx = await browser.newContext();
    const p = await ctx.newPage();
    await entrar(p, "coord");
    await p.goto(BASE + "/painel");
    demandaIds = await p.$$eval("a[href^='/demanda/']", (as) => [...new Set(as.map((a) => a.getAttribute("href")))]);
    await ctx.close();
  }
  const roteiro = [
    ["anonimo", ["/entrar", "/nao-existe"]],
    ["coord", ["/painel", "/painel?situacao=EM_CAMPO&municipio=x", "/candidatas", ...demandaIds, demandaIds[0] + "?ponto=P01#ponto-P01",
               "/conflitos", "/exportar", "/ajuda", "/demanda/nova"]],
    ["analista", [demandaIds[0], "/demanda/nova", "/candidatas"]],
    ["tecnico", ["/painel", "/campo", "/campo/coleta", "/backup"]],
    ["auditor", ["/auditoria"]],
    ["admin", ["/backup", "/acessos"]],
  ];
  for (const largura of [360, 1280]) {
    for (const esquema of ["light", "dark"]) {
      for (const [usuario, paginas] of roteiro) {
        const ctx = await browser.newContext({ viewport: { width: largura, height: 800 }, colorScheme: esquema, bypassCSP: true,
                                               reducedMotion: "reduce" });
        const page = await ctx.newPage();
        if (usuario !== "anonimo") await entrar(page, usuario);
        for (const caminho of paginas) {
          const resp = await page.goto(BASE + caminho);
          const nome = `${largura}-${esquema}-${usuario}-${caminho.replace(/[^a-z0-9]+/gi, "_").slice(0, 40)}`;
          await page.screenshot({ path: path.join(OUT, nome + ".png"), fullPage: true });
          const m = await medir(page, largura);
          const a = await axe(page);
          relatorio.push({ nome, largura, esquema, usuario, caminho, status: resp.status(), ...m, axe: a });
        }
        if (usuario === "tecnico") {   // coleta em etapas: preenche e captura cada etapa
          await page.goto(BASE + "/campo/coleta");
          const missao = await page.$eval("select[name=missao] option:not([value=''])", (o) => o.value).catch(() => null);
          if (missao) {
            await page.selectOption("select[name=missao]", missao);
            await page.fill("input[name=codigo]", "P9" + largura + (esquema === "dark" ? "E" : "C"));
            await page.fill("input[name=latitude]", "-10,4955");
            await page.fill("input[name=longitude]", "-48,4952");
            await page.fill("input[name=precisao]", "4");
            await page.fill("input[name=capturado_em]", "2026-10-03T09:30");
            await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/ponto'] button[type=submit]")]);
            for (const etapa of [2, 3, 4, 5]) {
              const nome = `${largura}-${esquema}-tecnico-coleta-etapa${etapa}`;
              await page.screenshot({ path: path.join(OUT, nome + ".png"), fullPage: true });
              const m = await medir(page, largura);
              const a = await axe(page);
              // botões sim/não/não observado: tamanho real de cada rótulo clicável
              m.opcoes_menor = await page.$$eval("label.opcao", (ls) => ls.length ? ls.map((l) => {
                const r = l.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)];
              }).reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1])]) : null);
              relatorio.push({ nome, largura, esquema, usuario, caminho: `/campo/coleta (etapa ${etapa})`, status: 200, ...m, axe: a });
              if (etapa === 2) {
                await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/visto'] button[type=submit]")]);
              } else if (etapa === 3) {
                await page.setInputFiles("input[name=foto]", { name: "ponto-sintetico.png", mimeType: "image/png",
                  buffer: Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.from("foto sintetica " + largura + esquema)]) });
                await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/foto'] button[type=submit]")]);
                const nomeF = `${largura}-${esquema}-tecnico-coleta-etapa3-com-foto`;
                await page.screenshot({ path: path.join(OUT, nomeF + ".png"), fullPage: true });
                relatorio.push({ nome: nomeF, largura, esquema, usuario, caminho: "/campo/coleta (etapa 3, 1 foto)", status: 200,
                                 foto_anexada: (await page.content()).includes("Foto 1 anexada"),
                                 ...(await medir(page, largura)), axe: await axe(page) });
                await page.fill("input[name=altura]", "35");
                await page.fill("input[name=solo]", "Solo sintético");
                await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/ambiente'] button[type=submit]")]);
              } else if (etapa === 4) {
                await page.fill("input[name=profundidade]", "20");
                await page.fill("input[name=resistencia]", "1,4");
                await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/medicao'] button[type=submit]")]);
                const nome4 = `${largura}-${esquema}-tecnico-coleta-etapa4-com-medicao`;
                await page.screenshot({ path: path.join(OUT, nome4 + ".png"), fullPage: true });
                relatorio.push({ nome: nome4, largura, esquema, usuario, caminho: "/campo/coleta (etapa 4, 1 medição)", status: 200,
                                 ...(await medir(page, largura)), axe: await axe(page) });
                await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/conferir'] button[type=submit]")]);
              }
            }
            await Promise.all([page.waitForNavigation(), page.click("form[action='/campo/coleta/descartar'] button[type=submit]")]);
          }
        }
        await ctx.close();
      }
    }
  }
  // Rodada 3: pedido de usuário de teste (anônimo), demanda nova com erro (analista) e acessos com pedido pendente (admin)
  {
    const ctx = await browser.newContext({ viewport: { width: 360, height: 800 }, bypassCSP: true });
    const page = await ctx.newPage();
    await page.goto(BASE + "/entrar");
    await page.fill("input[name=identificador]", "usuario-sintetico-verificacao");
    await page.fill("input[name=motivo]", "verificação automática da tela");
    await Promise.all([page.waitForNavigation(), page.click("form[action='/acesso/pedir'] button[type=submit]")]);
    relatorio.push({ nome: "360-anonimo-pedido-enviado", largura: 360, esquema: "light", usuario: "anonimo", caminho: "/entrar (pedido)",
                     status: 200, pedido_registrado: (await page.content()).includes("Pedido registrado"),
                     ...(await medir(page, 360)), axe: await axe(page) });
    await entrar(page, "analista");
    await page.goto(BASE + "/demanda/nova");
    await page.fill("input[name=titulo]", "Demanda da verificação (sintética)");
    await page.fill("input[name=descricao]", "texto sintético");
    for (const [k, v] of [["lat_max", "-10,50"], ["lat_min", "-10,40"], ["lon_min", "-48,52"], ["lon_max", "-48,50"]]) await page.fill(`input[name=${k}]`, v);
    await Promise.all([page.waitForNavigation(), page.click("form[action='/demanda/nova'] button[type=submit]")]);
    await page.screenshot({ path: path.join(OUT, "360-analista-demanda-nova-erro.png"), fullPage: true });
    relatorio.push({ nome: "360-analista-demanda-nova-erro", largura: 360, esquema: "light", usuario: "analista", caminho: "/demanda/nova (erro)",
                     status: 422, ...(await medir(page, 360)), axe: await axe(page) });
    await page.fill("input[name=lat_min]", "-10,52");
    await Promise.all([page.waitForNavigation(), page.click("form[action='/demanda/nova'] button[type=submit]")]);
    relatorio.push({ nome: "360-analista-demanda-criada", largura: 360, esquema: "light", usuario: "analista", caminho: page.url().replace(BASE, ""),
                     status: 200, criada: (await page.content()).includes("Demanda criada"), ...(await medir(page, 360)), axe: await axe(page) });
    // Rodada 4: importação de áreas candidatas (arquivo sintético com 1 item recusado) e resultado por item
    await page.goto(BASE + "/candidatas");
    await page.setInputFiles("input[name=arquivo]", { name: "areas.csv", mimeType: "text/csv", buffer: Buffer.from(
      "geometria_wkt,data_deteccao,origem_declarada,incerteza,fonte\n" +
      '"POLYGON ((-48.36 -10.26, -48.35 -10.26, -48.35 -10.25, -48.36 -10.25, -48.36 -10.26))",2026-08-15,planilha sintética,aproximada,P\n' +
      '"POLYGON ((-48.34 -10.24, -48.33 -10.24, -48.33 -10.23, -48.34 -10.23, -48.34 -10.24))",2026-08-16,,,P\n') });
    await Promise.all([page.waitForNavigation(), page.click("form[action='/candidatas/importar'] button[type=submit]")]);
    await page.screenshot({ path: path.join(OUT, "360-analista-candidatas-importadas.png"), fullPage: true });
    relatorio.push({ nome: "360-analista-candidatas-importadas", largura: 360, esquema: "light", usuario: "analista",
                     caminho: "/candidatas (importação)", status: 200,
                     importou: (await page.content()).includes("1 área(s) registrada(s) e 1 recusada(s)"),
                     ...(await medir(page, 360)), axe: await axe(page) });
    await entrar(page, "admin");
    await page.goto(BASE + "/acessos");
    await page.screenshot({ path: path.join(OUT, "360-admin-acessos-pendente.png"), fullPage: true });
    relatorio.push({ nome: "360-admin-acessos-pendente", largura: 360, esquema: "light", usuario: "admin", caminho: "/acessos (pendente)",
                     status: 200, ...(await medir(page, 360)), axe: await axe(page) });
    await ctx.close();
  }
  // tema escuro escolhido na própria tela (data-tema), com o sistema em modo claro
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: "light", bypassCSP: true });
    const page = await ctx.newPage();
    await entrar(page, "coord");
    await page.selectOption("select#tema", "escuro");
    await Promise.all([page.waitForNavigation(), page.click("form[action='/tema'] button[type=submit]")]);
    const tema = await page.getAttribute("html", "data-tema");
    await page.screenshot({ path: path.join(OUT, "1280-escolhido-escuro-coord-painel.png"), fullPage: true });
    relatorio.push({ nome: "1280-escolhido-escuro-coord-painel", largura: 1280, esquema: "data-tema=" + tema, usuario: "coord",
                     caminho: "/painel", status: 200, ...(await medir(page, 1280)), axe: await axe(page) });
    // zoom de 200%: 1280 px com fator 2 equivale a 640 px CSS
    const z = await browser.newContext({ viewport: { width: 640, height: 400 }, deviceScaleFactor: 2, bypassCSP: true });
    const pz = await z.newPage();
    await entrar(pz, "coord");
    for (const caminho of ["/painel", demandaIds[0]]) {
      await pz.goto(BASE + caminho);
      const nome = `zoom200-coord-${caminho.replace(/[^a-z0-9]+/gi, "_").slice(0, 30)}`;
      await pz.screenshot({ path: path.join(OUT, nome + ".png"), fullPage: true });
      relatorio.push({ nome, largura: 640, esquema: "zoom 200%", usuario: "coord", caminho, status: 200, ...(await medir(pz, 640)), axe: { violacoes: [], incompletos: [], aprovadas: 0 } });
    }
    await ctx.close(); await z.close();
  }
  // navegação por teclado: ordem do Tab nas primeiras 15 paradas e foco visível
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await entrar(page, "coord");
    await page.goto(BASE + demandaIds[0]);
    const paradas = [];
    for (let i = 0; i < 15; i++) {
      await page.keyboard.press("Tab");
      paradas.push(await page.evaluate(() => {
        const el = document.activeElement;
        const cs = getComputedStyle(el);
        return `${el.tagName.toLowerCase()} "${(el.innerText || el.value || "").trim().slice(0, 25)}" contorno=${cs.outlineStyle}/${cs.outlineWidth}`;
      }));
    }
    relatorio.push({ nome: "teclado-demanda", paradas_tab: paradas });
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "relatorio.json"), JSON.stringify(relatorio, null, 2));
  console.log("capturas:", relatorio.length);
})().catch((e) => { console.error(e); process.exit(1); });
