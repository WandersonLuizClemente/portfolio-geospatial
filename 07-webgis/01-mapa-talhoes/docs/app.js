// Mapa de talhoes colorido por NDVI. Dados: arquivos estaticos em data/ ou a API (?api=http://127.0.0.1:8000).
// Todo texto vindo dos dados entra na pagina com textContent (sem montar HTML a partir dos dados).
(function () {
  "use strict";

  var ESCALA = [[0.4, "#ffffcc"], [0.5, "#c2e699"], [0.65, "#78c679"], [0.8, "#31a354"], [0.9, "#006837"]];
  var SEM_DADO = "#9aa39d";
  var NS = "http://www.w3.org/2000/svg";

  var estado = { talhoes: null, ndvi: [], datas: [], indice: 0, selecionado: null, camadas: {}, porTalhaoData: {}, porTalhao: {} };

  function el(tag, props, filhos) {
    var e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === "texto") e.textContent = props[k]; else e.setAttribute(k, props[k]);
    });
    (filhos || []).forEach(function (f) { e.appendChild(f); });
    return e;
  }
  function svg(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }
  function pt(v, casas) { return Number(v).toFixed(casas).replace(".", ","); }
  function dataBr(iso) { var p = iso.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
  function mostrarErro(msg) { var e = document.getElementById("erro"); e.textContent = msg; e.style.display = "block"; }

  function cor(v) {
    if (v === null || v === undefined) return SEM_DADO;
    if (v <= ESCALA[0][0]) return ESCALA[0][1];
    for (var i = 1; i < ESCALA.length; i++) {
      if (v <= ESCALA[i][0]) return mistura(ESCALA[i - 1], ESCALA[i], v);
    }
    return ESCALA[ESCALA.length - 1][1];
  }
  function mistura(a, b, v) {
    var t = (v - a[0]) / (b[0] - a[0]), ca = hex(a[1]), cb = hex(b[1]);
    return "rgb(" + [0, 1, 2].map(function (i) { return Math.round(ca[i] + (cb[i] - ca[i]) * t); }).join(",") + ")";
  }
  function hex(h) { return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }

  function urls() {
    var api = new URLSearchParams(location.search).get("api");
    if (!api) return { talhoes: "data/talhoes.geojson", ndvi: "data/ndvi.json", origem: "dados estáticos" };
    var u;
    try { u = new URL(api); } catch (e) { throw new Error("Parâmetro 'api' inválido."); }
    if (u.protocol !== "http:" && u.protocol !== "https:") throw new Error("Parâmetro 'api' inválido.");
    var base = u.origin + u.pathname.replace(/\/$/, "");
    return { talhoes: base + "/talhoes", ndvi: base + "/ndvi", origem: "API " + u.origin };
  }

  function buscar(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("Falha ao carregar " + url + " (" + r.status + ")");
      return r.json();
    });
  }

  function indexar() {
    estado.datas = Array.from(new Set(estado.ndvi.map(function (o) { return o.data; }))).sort();
    estado.ndvi.forEach(function (o) {
      estado.porTalhaoData[o.talhao_id + "|" + o.data] = o;
      (estado.porTalhao[o.talhao_id] = estado.porTalhao[o.talhao_id] || []).push(o);
    });
  }

  function ndviEm(id, data) {
    var o = estado.porTalhaoData[id + "|" + data];
    return o ? o.ndvi_medio : null;
  }

  // ---------------------------------------------------------------- mapa
  var mapa;
  function iniciarMapa() {
    mapa = L.map("mapa", { zoomControl: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "© OpenStreetMap"
    }).addTo(mapa);
    var camada = L.geoJSON(estado.talhoes, {
      style: function () { return { color: "#1f2a24", weight: 2, fillOpacity: 0.85, fillColor: SEM_DADO }; },
      onEachFeature: function (f, l) {
        estado.camadas[f.properties.id] = l;
        l.on("click", function () { selecionar(f.properties.id); });
      }
    }).addTo(mapa);
    var limites = camada.getBounds();
    if (limites.isValid()) mapa.fitBounds(limites.pad(0.15));
  }

  function pintar() {
    var data = estado.datas[estado.indice];
    Object.keys(estado.camadas).forEach(function (id) {
      var v = data ? ndviEm(id, data) : null;
      estado.camadas[id].setStyle({
        fillColor: cor(v),
        weight: id === estado.selecionado ? 4 : 2
      });
      estado.camadas[id].bindTooltip(id + (v === null ? ": sem observação" : ": NDVI " + pt(v, 2)), { sticky: true });
    });
  }

  // ---------------------------------------------------------------- painel
  function montarLista() {
    var corpo = document.getElementById("lista");
    corpo.textContent = "";
    estado.talhoes.features.forEach(function (f) {
      var p = f.properties;
      var amostra = el("span", { "class": "amostra" });
      amostra.dataset.id = p.id;
      var tr = el("tr", { "class": "item", tabindex: "0", "data-id": p.id }, [
        el("td", {}, [amostra, document.createTextNode(p.id)]),
        el("td", { texto: p.cultura }),
        el("td", { "class": "num", "data-ndvi": p.id, texto: "–" })
      ]);
      tr.addEventListener("click", function () { selecionar(p.id, true); });
      tr.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selecionar(p.id, true); }
      });
      corpo.appendChild(tr);
    });
  }

  function atualizarLista() {
    var data = estado.datas[estado.indice];
    estado.talhoes.features.forEach(function (f) {
      var id = f.properties.id, v = data ? ndviEm(id, data) : null;
      document.querySelector('[data-ndvi="' + id + '"]').textContent = v === null ? "–" : pt(v, 2);
      document.querySelector('.amostra[data-id="' + id + '"]').style.background = cor(v);
    });
    document.querySelectorAll("tr.item").forEach(function (tr) {
      tr.classList.toggle("sel", tr.getAttribute("data-id") === estado.selecionado);
    });
  }

  function selecionar(id, centralizar) {
    estado.selecionado = id;
    if (centralizar && estado.camadas[id]) mapa.fitBounds(estado.camadas[id].getBounds().pad(1.5));
    atualizar();
  }

  function desenharSerie(id) {
    var obs = (estado.porTalhao[id] || []).slice().sort(function (a, b) { return a.data < b.data ? -1 : 1; });
    var W = 320, H = 150, m = { e: 30, d: 8, t: 8, b: 22 };
    var raiz = svg("svg", { "class": "serie", viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Série temporal de NDVI do talhão " + id });
    if (!obs.length) { return el("div", { "class": "vazio", texto: "Sem observações aprovadas para este talhão." }); }
    var t0 = Date.parse(estado.datas[0]), t1 = Date.parse(estado.datas[estado.datas.length - 1]);
    if (t1 === t0) t1 = t0 + 86400000;
    var y0 = 0.3, y1 = 1.0;
    function X(iso) { return m.e + (Date.parse(iso) - t0) / (t1 - t0) * (W - m.e - m.d); }
    function Y(v) { return m.t + (y1 - v) / (y1 - y0) * (H - m.t - m.b); }
    [0.4, 0.6, 0.8, 1.0].forEach(function (v) {
      raiz.appendChild(svg("line", { "class": "grade", x1: m.e, x2: W - m.d, y1: Y(v), y2: Y(v) }));
      var tx = svg("text", { x: m.e - 4, y: Y(v) + 3, "text-anchor": "end" }); tx.textContent = pt(v, 1);
      raiz.appendChild(tx);
    });
    var vistos = {};
    estado.datas.forEach(function (d) {
      var mes = d.slice(0, 7);
      if (vistos[mes]) return; vistos[mes] = true;
      var tx = svg("text", { x: X(mes + "-01") < m.e ? m.e : X(mes + "-01"), y: H - 6, "text-anchor": "start" });
      tx.textContent = mes.slice(5) + "/" + mes.slice(2, 4);
      if (Object.keys(vistos).length % 2 === 1) raiz.appendChild(tx);
    });
    var atual = estado.datas[estado.indice];
    if (atual) raiz.appendChild(svg("line", { "class": "atual", x1: X(atual), x2: X(atual), y1: m.t, y2: H - m.b }));
    raiz.appendChild(svg("polyline", { "class": "linha", points: obs.map(function (o) { return X(o.data) + "," + Y(o.ndvi_medio); }).join(" ") }));
    obs.forEach(function (o) {
      var c = svg("circle", { "class": "ponto", cx: X(o.data), cy: Y(o.ndvi_medio), r: 2.2 });
      var t = svg("title"); t.textContent = dataBr(o.data) + ": NDVI " + pt(o.ndvi_medio, 2);
      c.appendChild(t); raiz.appendChild(c);
    });
    return raiz;
  }

  function atualizarDetalhe() {
    var box = document.getElementById("detalhe");
    box.textContent = "";
    var id = estado.selecionado;
    if (!id) { box.appendChild(el("div", { "class": "vazio", texto: "Clique em um talhão no mapa ou na tabela." })); return; }
    var f = estado.talhoes.features.filter(function (x) { return x.properties.id === id; })[0];
    var p = f.properties, data = estado.datas[estado.indice], v = data ? ndviEm(id, data) : null;
    var obs = estado.porTalhao[id] || [];
    var media = obs.length ? obs.reduce(function (s, o) { return s + o.ndvi_medio; }, 0) / obs.length : null;
    box.appendChild(el("div", { "class": "kv" }, [
      el("span", { texto: id + " · " + p.cultura }),
      el("span", { texto: p.area_ha === null ? "" : "Área " + pt(p.area_ha, 1) + " ha" }),
      el("span", { texto: v === null ? "Sem observação na data" : "NDVI na data: " + pt(v, 2) }),
      el("span", { texto: media === null ? "" : "Média do período: " + pt(media, 2) + " (" + obs.length + " obs.)" })
    ]));
    box.appendChild(desenharSerie(id));
  }

  function atualizar() { pintar(); atualizarLista(); atualizarDetalhe(); }

  // Abre na data com mais talhoes aprovados (a mais recente em caso de empate)
  function dataInicial() {
    var contagem = {};
    estado.ndvi.forEach(function (o) { contagem[o.data] = (contagem[o.data] || 0) + 1; });
    var melhor = estado.datas.length - 1;
    estado.datas.forEach(function (d, i) {
      if (contagem[d] >= contagem[estado.datas[melhor]]) melhor = i;
    });
    return melhor;
  }

  function iniciarSlider() {
    var s = document.getElementById("slider");
    if (!estado.datas.length) {
      document.getElementById("dataAtual").textContent = "Sem observações aprovadas";
      return;
    }
    s.max = estado.datas.length - 1; s.value = 0; s.disabled = false;
    estado.indice = dataInicial(); s.value = estado.indice;
    function rotulo() {
      document.getElementById("dataAtual").textContent = dataBr(estado.datas[estado.indice]);
      document.getElementById("contagemDatas").textContent =
        "Data " + (estado.indice + 1) + " de " + estado.datas.length + " com ao menos um talhão aprovado";
    }
    s.addEventListener("input", function () { estado.indice = Number(s.value); rotulo(); atualizar(); });
    rotulo();
  }

  function iniciar() {
    var u;
    try { u = urls(); } catch (e) { mostrarErro(e.message); return; }
    document.getElementById("fonte").textContent = "Fonte: " + u.origem;
    var barra = document.getElementById("barra");
    barra.style.background = "linear-gradient(to right," + ESCALA.map(function (c) {
      return c[1] + " " + ((c[0] - 0.4) / 0.5 * 100) + "%";
    }).join(",") + ")";
    Promise.all([buscar(u.talhoes), buscar(u.ndvi)]).then(function (r) {
      estado.talhoes = r[0]; estado.ndvi = r[1];
      indexar(); iniciarMapa(); montarLista(); iniciarSlider(); atualizar();
    }).catch(function (e) {
      mostrarErro("Não foi possível carregar os dados. " + e.message +
        " Se for a versão estática, rode 'python projeto3.py exportar' para gerar docs/data/.");
    });
  }
  iniciar();
})();
