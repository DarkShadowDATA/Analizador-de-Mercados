/* Capa de análisis: señales Wyckoff, perfil de volumen anclado, RSI y backtest.
 * Lee docs/data/analisis_<mercado>_<tf>.json y docs/data/resumen_senales.json
 * (generados por scripts/generar_senales.py).
 */
window.Analisis = (() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const NOMBRE = { spring: "Spring", upthrust: "Upthrust", test_spring: "Test de spring", test_upthrust: "Test de upthrust" };
  const NOMBRE_TF = { "1h": "1H", "4h": "4H", "1d": "1D" };
  const SALIDA = { objetivo: "Objetivo", stop: "Stop", tiempo: "Tiempo", abierta: "Abierta" };

  let app, rsiChart, serieRsi, seriesNiveles = {}, serieMedia;
  let datos = null;         // análisis del gráfico actual
  let resumenDatos = null;
  const capas = { senales: true, perfil: true, niveles: true, media: false };

  const num = (x, d = 2) => x == null || !isFinite(x) ? "—"
    : Number(x).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
  const signo = (x, d = 2) => x == null ? "—" : (x > 0 ? "+" : "") + num(x, d);
  const fecha = (iso, tf) => {
    const d = new Date(iso);
    return tf === "1d"
      ? d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" })
      : d.toLocaleString("es-ES", { day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit" });
  };
  const ts = (iso) => Math.floor(new Date(iso).getTime() / 1000);
  const linea = (t, v) => t.map((x, i) => (v[i] == null ? { time: x } : { time: x, value: v[i] }));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function json(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  // ------------------------------------------------------------ montaje
  function iniciar(a) {
    app = a;
    const g = app.grafico;
    const opcLinea = { lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false };
    seriesNiveles.poc = g.addLineSeries({ ...opcLinea, color: css("--poc"), lineType: 1, lineWidth: 2, title: "POC" });
    seriesNiveles.vah = g.addLineSeries({ ...opcLinea, color: css("--va"), lineType: 1, lineStyle: 2, title: "VAH" });
    seriesNiveles.val = g.addLineSeries({ ...opcLinea, color: css("--va"), lineType: 1, lineStyle: 2, title: "VAL" });
    serieMedia = g.addLineSeries({ ...opcLinea, color: css("--media"), visible: false });

    rsiChart = LightweightCharts.createChart($("rsi"), {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: css("--tenue"), fontFamily: "system-ui, sans-serif" },
      grid: { vertLines: { color: css("--rejilla") }, horzLines: { visible: false } },
      rightPriceScale: { borderColor: css("--borde"), scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { visible: false },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      handleScroll: false, handleScale: false,
    });
    serieRsi = rsiChart.addLineSeries({ color: css("--acento"), lineWidth: 1.5, priceLineVisible: false,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
    for (const [v, c] of [[70, css("--baja")], [30, css("--sube")], [50, css("--borde")]]) {
      serieRsi.createPriceLine({ price: v, color: c, lineWidth: 1, lineStyle: 2, axisLabelVisible: v !== 50 });
    }
    // El RSI sigue el desplazamiento y zoom del gráfico principal
    g.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (r) rsiChart.timeScale().setVisibleLogicalRange(r);
      dibujarPerfil();
    });

    document.querySelectorAll("#capas input").forEach((el) => {
      el.onchange = () => { capas[el.dataset.capa] = el.checked; aplicarCapas(); };
    });
    new ResizeObserver(dibujarPerfil).observe($("grafico"));
    setInterval(dibujarPerfil, 500); // la escala de precios cambia al desplazar o en vivo
  }

  // ------------------------------------------------------------ por gráfico
  async function cargar(m, tf) {
    datos = null;
    try {
      datos = await json(`data/analisis_${m.id}_${tf}.json`);
    } catch (e) {
      console.warn("Sin análisis para", m.id, tf, e);
      for (const s of Object.values(seriesNiveles)) s.setData([]);
      serieRsi.setData([]); serieMedia.setData([]); app.serieVelas.setMarkers([]);
      $("lista-senales").innerHTML = "<li>Todavía no hay análisis para este gráfico.</li>";
      $("metricas").innerHTML = ""; $("operaciones").innerHTML = "";
      dibujarPerfil();
      return;
    }
    serieRsi.setData(linea(datos.rsi.t, datos.rsi.v));
    for (const k of ["poc", "vah", "val"]) seriesNiveles[k].setData(linea(datos.niveles.t, datos.niveles[k]));
    serieMedia.setData(linea(datos.media.t, datos.media.v));
    serieMedia.applyOptions({ title: `Media ${datos.media.periodo}` });
    const r = app.grafico.timeScale().getVisibleLogicalRange();
    if (r) rsiChart.timeScale().setVisibleLogicalRange(r);
    aplicarCapas();
    pintarSenales(m, tf);
    pintarBacktest(m, tf);
    marcarFilaResumen();
  }

  function aplicarCapas() {
    for (const s of Object.values(seriesNiveles)) s.applyOptions({ visible: capas.niveles });
    serieMedia.applyOptions({ visible: capas.media });
    marcadores();
    dibujarPerfil();
  }

  function marcadores() {
    if (!datos || !capas.senales) { app.serieVelas.setMarkers([]); return; }
    const minimo = resumenDatos ? resumenDatos.reglas.puntos_min : 3;
    const conocidas = new Set(app.velas().map((v) => v.time));
    const marcas = datos.senales
      .filter((s) => s.puntos >= 2 && conocidas.has(ts(s.fecha)))
      .map((s) => {
        const largo = s.direccion > 0;
        const fuerte = s.puntos >= minimo;
        const letra = { spring: "S", upthrust: "U", test_spring: "T", test_upthrust: "T" }[s.tipo];
        return {
          time: ts(s.fecha),
          position: largo ? "belowBar" : "aboveBar",
          shape: largo ? "arrowUp" : "arrowDown",
          color: largo ? css("--sube") : css("--baja"),
          text: fuerte ? `${letra}${s.puntos}` : "",
          size: fuerte ? 1 : 0.5,
        };
      })
      .sort((a, b) => a.time - b.time);
    app.serieVelas.setMarkers(marcas);
  }

  function dibujarPerfil() {
    const cv = $("perfil");
    const cont = $("grafico");
    const dpr = window.devicePixelRatio || 1;
    const w = cont.clientWidth, h = cont.clientHeight;
    if (cv.width !== w * dpr || cv.height !== h * dpr) {
      cv.width = w * dpr; cv.height = h * dpr;
      cv.style.width = w + "px"; cv.style.height = h + "px";
    }
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!datos || !datos.perfil || !capas.perfil) return;

    const p = datos.perfil;
    const ancho = app.grafico.timeScale().width();
    const maxVol = Math.max(...p.volumen);
    if (!(maxVol > 0) || p.precios.length < 2) return;
    const paso = p.precios[1] - p.precios[0];
    const anchoMax = ancho * 0.22;
    const colorVa = css("--va"), colorPoc = css("--poc");
    for (let i = 0; i < p.precios.length; i++) {
      const y1 = app.serieVelas.priceToCoordinate(p.precios[i] + paso / 2);
      const y2 = app.serieVelas.priceToCoordinate(p.precios[i] - paso / 2);
      if (y1 == null || y2 == null) continue;
      const largo = (p.volumen[i] / maxVol) * anchoMax;
      const dentro = p.precios[i] >= p.val && p.precios[i] <= p.vah;
      const esPoc = Math.abs(p.precios[i] - p.poc) < paso / 2;
      ctx.globalAlpha = esPoc ? 0.55 : dentro ? 0.3 : 0.14;
      ctx.fillStyle = esPoc ? colorPoc : colorVa;
      ctx.fillRect(ancho - largo, Math.min(y1, y2), largo, Math.max(1, Math.abs(y2 - y1) - 1));
    }
    ctx.globalAlpha = 1;
  }

  function pintarSenales(m, tf) {
    const lista = $("lista-senales");
    const recientes = datos.senales.filter((s) => s.puntos >= 2).slice(-8).reverse();
    if (!recientes.length) { lista.innerHTML = "<li>Sin señales en el periodo del gráfico.</li>"; return; }
    lista.innerHTML = "";
    for (const s of recientes) {
      const li = document.createElement("li");
      const clase = s.direccion > 0 ? "sube" : "baja";
      li.innerHTML =
        `<div class="cab"><span class="${clase}">${NOMBRE[s.tipo]} · ${s.direccion > 0 ? "largo" : "corto"}</span>` +
        `<span class="pts">${s.puntos}/4 pts</span></div>` +
        `<div>${fecha(s.fecha, tf)} · cierre ${num(s.cierre, m.decimales)} · nivel ${num(s.nivel, m.decimales)}</div>` +
        `<div class="mot">${esc(s.motivos.join(" · ") || "sin confirmaciones")}</div>`;
      li.onclick = () => irA(ts(s.fecha));
      lista.appendChild(li);
    }
  }

  function irA(t) {
    const velas = app.velas();
    const i = velas.findIndex((v) => v.time === t);
    if (i >= 0) app.grafico.timeScale().setVisibleLogicalRange({ from: i - 80, to: i + 40 });
  }

  function kpis(mt) {
    if (!mt || !mt.operaciones) return "<p class='nota'>Sin operaciones.</p>";
    const k = (titulo, valor, clase = "") => `<div class="kpi"><div class="k">${titulo}</div><div class="v ${clase}">${valor}</div></div>`;
    const c = (x) => (x > 0 ? "sube" : x < 0 ? "baja" : "");
    return `<div class="kpis">` +
      k("Operaciones", mt.operaciones) +
      k("Aciertos", num(mt.aciertos_pct, 0) + " %") +
      k("R medio", signo(mt.r_medio), c(mt.r_medio)) +
      k("Factor de beneficio", mt.factor_beneficio == null ? "—" : num(mt.factor_beneficio)) +
      k("Resultado (1 % riesgo)", signo(mt.rentabilidad_pct, 1) + " %", c(mt.rentabilidad_pct)) +
      k("Máx. caída", num(mt.max_caida_pct, 1) + " %") +
      `</div>`;
  }

  function pintarBacktest(m, tf) {
    const t = datos.metricas.total, u = datos.metricas.ultimos_2_anios;
    let aviso = "";
    if (t.operaciones) {
      const ok = t.r_medio > 0 && (u.r_medio || 0) > 0;
      aviso = `<p class="aviso ${ok ? "ok" : ""}">` + (ok
        ? "En este gráfico las reglas ganaron en el histórico y en los últimos 2 años. Aun así son pocas operaciones: validar en demo."
        : "Con estas reglas este gráfico no muestra ventaja en el histórico. No usar con dinero real.") + "</p>";
    }
    $("metricas").innerHTML =
      `<h4>Todo el histórico ${t.desde ? `(${t.desde} a ${t.hasta})` : ""}</h4>` + kpis(t) +
      `<h4>Últimos 2 años</h4>` + kpis(u) + aviso;

    const ops = datos.operaciones.slice(-10).reverse();
    $("operaciones").innerHTML = ops.length
      ? "<thead><tr><th class='izq'>Entrada</th><th class='izq'>Señal</th><th>Precio</th><th>Salida</th><th class='izq'>Motivo</th><th>R</th></tr></thead><tbody>" +
        ops.map((o) =>
          `<tr class="clic" data-t="${ts(o.fecha_entrada)}"><td>${fecha(o.fecha_entrada, tf)}</td>` +
          `<td class="izq ${o.direccion > 0 ? "sube" : "baja"}">${NOMBRE[o.tipo]}</td>` +
          `<td>${num(o.entrada, m.decimales)}</td><td>${num(o.salida, m.decimales)}</td>` +
          `<td class="izq">${SALIDA[o.motivo_salida]}</td>` +
          `<td class="${o.r > 0 ? "sube" : "baja"}">${signo(o.r)}</td></tr>`).join("") + "</tbody>"
      : "<tbody><tr><td>Sin operaciones en el periodo del gráfico.</td></tr></tbody>";
    $("operaciones").querySelectorAll("tr.clic").forEach((tr) => { tr.onclick = () => irA(Number(tr.dataset.t)); });
  }

  // ------------------------------------------------------------ resumen general
  async function resumen() {
    resumenDatos = await json("data/resumen_senales.json");
    const rg = resumenDatos.reglas;
    $("reglas").textContent =
      `Reglas: señales de ${rg.puntos_min} puntos o más, solo a favor de la media de ${rg.filtro_tendencia} velas, ` +
      `stop ${num(rg.colchon_atr, 1)} ATR detrás del extremo, objetivo entre ${num(rg.r_min, 1)}R y ${num(rg.r_max, 1)}R, ` +
      `salida por tiempo a las ${rg.max_barras} velas, riesgo ${num(rg.riesgo_pct, 0)} % por operación, con comisiones. ` +
      `Calculado: ${new Date(resumenDatos.generado).toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" })}.`;

    const c = (x) => (x > 0 ? "sube" : x < 0 ? "baja" : "");
    const filas = resumenDatos.filas;
    $("resumen").innerHTML =
      "<thead><tr><th class='izq'>Mercado</th><th class='izq'>TF</th><th class='izq'>Tendencia</th><th>Ops.</th>" +
      "<th>Aciertos</th><th>R medio</th><th>F. benef.</th><th>Resultado</th><th>Máx. caída</th>" +
      "<th>R medio 2 años</th><th class='izq'>Última señal</th></tr></thead><tbody>" +
      filas.map((f) => {
        const t = f.total, u = f.ultimos_2_anios, s = f.ultima_senal;
        return `<tr class="clic" data-m="${f.mercado}" data-tf="${f.tf}">` +
          `<td>${esc(f.nombre)}</td><td class="izq">${NOMBRE_TF[f.tf]}</td>` +
          `<td class="izq ${f.tendencia === "alcista" ? "sube" : "baja"}">${f.tendencia}</td>` +
          `<td>${t.operaciones || 0}</td><td>${t.operaciones ? num(t.aciertos_pct, 0) + " %" : "—"}</td>` +
          `<td class="${c(t.r_medio)}">${signo(t.r_medio)}</td>` +
          `<td>${t.factor_beneficio == null ? "—" : num(t.factor_beneficio)}</td>` +
          `<td class="${c(t.rentabilidad_pct)}">${t.operaciones ? signo(t.rentabilidad_pct, 1) + " %" : "—"}</td>` +
          `<td>${t.operaciones ? num(t.max_caida_pct, 1) + " %" : "—"}</td>` +
          `<td class="${c(u.r_medio)}">${u.operaciones ? signo(u.r_medio) : "—"}</td>` +
          `<td class="izq">${s ? `${NOMBRE[s.tipo]} ${s.puntos}p · ${fecha(s.fecha, f.tf)}` : "—"}</td></tr>`;
      }).join("") + "</tbody>";
    $("resumen").querySelectorAll("tr.clic").forEach((tr) => {
      tr.onclick = () => app.seleccionar(tr.dataset.m, tr.dataset.tf);
    });
    marcarFilaResumen();

    const activas = filas.filter((f) => f.senal_activa);
    const caja = $("activa");
    if (activas.length) {
      caja.hidden = false;
      caja.innerHTML = "<b>Señales activas ahora:</b> " + activas.map((f) => {
        const s = f.senal_activa;
        return `<a href="#${f.mercado}/${f.tf}" data-m="${f.mercado}" data-tf="${f.tf}">${esc(f.nombre)} ${NOMBRE_TF[f.tf]}: ` +
          `${NOMBRE[s.tipo]} (${s.direccion > 0 ? "largo" : "corto"}, ${s.puntos} pts)</a>`;
      }).join(" · ");
      caja.querySelectorAll("a").forEach((a) => {
        a.onclick = (e) => { e.preventDefault(); app.seleccionar(a.dataset.m, a.dataset.tf); };
      });
    } else {
      caja.hidden = false;
      caja.innerHTML = "Sin señales activas de " + resumenDatos.reglas.puntos_min +
        " puntos o más en las últimas velas de ningún mercado.";
    }
    marcadores();
  }

  function marcarFilaResumen() {
    const m = app.mercado(), tf = app.tf();
    document.querySelectorAll("#resumen tr.clic").forEach((tr) =>
      tr.classList.toggle("sel", tr.dataset.m === (m && m.id) && tr.dataset.tf === tf));
  }

  return { iniciar, cargar, resumen };
})();
