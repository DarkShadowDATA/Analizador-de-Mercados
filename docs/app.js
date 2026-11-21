/* Analizador de mercados - web estática.
 * Lee docs/data/indice.json y docs/data/<mercado>_<tf>.json (generados por
 * scripts/actualizar_datos.py) y dibuja velas + volumen con Lightweight Charts.
 * Para cripto añade precio en vivo desde el WebSocket público de Bitget.
 * Las señales, el perfil de volumen, el RSI y el backtest los dibuja analisis.js.
 */
(() => {
  "use strict";

  const SEGUNDOS = { "1h": 3600, "4h": 14400, "1d": 86400 };
  const NOMBRE_TF = { "1h": "1 hora", "4h": "4 horas", "1d": "Diario" };

  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  let indice = null;
  let estado = { mercado: null, tf: "1d" };
  let velas = [];          // [{time, open, high, low, close, volume}]
  let grafico, serieVelas, serieVolumen;
  let ws = null, pingWs = null;

  // ---------------------------------------------------------------- formato
  const fmtPrecio = (x, d = 2) =>
    x == null ? "—" : x.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmtVol = (x) =>
    x == null ? "—" : Intl.NumberFormat("es-ES", { notation: "compact", maximumFractionDigits: 2 }).format(x);
  const fmtFecha = (t, tf) => {
    const d = new Date(t * 1000);
    const op = tf === "1d"
      ? { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }
      : { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" };
    return d.toLocaleString("es-ES", op);
  };

  // ---------------------------------------------------------------- gráfico
  function crearGrafico() {
    const cont = $("grafico");
    grafico = LightweightCharts.createChart(cont, {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: css("--tenue"), fontFamily: "system-ui, sans-serif" },
      grid: { vertLines: { color: css("--rejilla") }, horzLines: { color: css("--rejilla") } },
      rightPriceScale: { borderColor: css("--borde") },
      timeScale: { borderColor: css("--borde"), timeVisible: true, secondsVisible: false },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      localization: { locale: "es-ES" },
    });
    serieVelas = grafico.addCandlestickSeries({
      upColor: css("--sube"), downColor: css("--baja"),
      borderUpColor: css("--sube"), borderDownColor: css("--baja"),
      wickUpColor: css("--sube"), wickDownColor: css("--baja"),
    });
    serieVelas.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.28 } });
    serieVolumen = grafico.addHistogramSeries({
      priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false,
    });
    grafico.priceScale("vol").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });

    window.Analisis && Analisis.iniciar({ grafico, serieVelas, velas: () => velas,
      mercado: mercadoActual, tf: () => estado.tf, seleccionar });

    grafico.subscribeCrosshairMove((p) => {
      const v = p && p.time != null ? velas.find((x) => x.time === p.time) : null;
      pintarLeyenda(v || velas[velas.length - 1]);
    });
  }

  function colorVolumen(v) {
    const base = v.close >= v.open ? css("--sube") : css("--baja");
    return base + "80"; // 50% transparencia
  }

  function pintarLeyenda(v) {
    if (!v) { $("leyenda").textContent = ""; return; }
    const d = mercadoActual().decimales;
    const cambio = ((v.close / v.open - 1) * 100);
    $("leyenda").innerHTML =
      `<span>${fmtFecha(v.time, estado.tf)}</span>` +
      `<span>A <b>${fmtPrecio(v.open, d)}</b></span>` +
      `<span>Máx <b>${fmtPrecio(v.high, d)}</b></span>` +
      `<span>Mín <b>${fmtPrecio(v.low, d)}</b></span>` +
      `<span>C <b class="${cambio >= 0 ? "sube" : "baja"}">${fmtPrecio(v.close, d)}</b></span>` +
      `<span>Vol <b>${fmtVol(v.volume)}</b></span>`;
  }

  // ---------------------------------------------------------------- datos
  const mercadoActual = () => indice.mercados.find((m) => m.id === estado.mercado);

  async function json(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  async function cargarSerie() {
    const m = mercadoActual();
    const tf = m.series[estado.tf] ? estado.tf : Object.keys(m.series)[0];
    estado.tf = tf;
    pintarControles();
    location.hash = `${m.id}/${tf}`;
    $("nombre").textContent = `${m.nombre} · ${NOMBRE_TF[tf]}`;

    const d = await json(`data/${m.id}_${tf}.json`);
    velas = d.t.map((t, i) => ({ time: t, open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i], volume: d.v[i] }));
    serieVelas.applyOptions({ priceFormat: { type: "price", precision: m.decimales, minMove: 1 / 10 ** m.decimales } });
    serieVelas.setData(velas);
    serieVolumen.setData(velas.map((v) => ({ time: v.time, value: v.volume, color: colorVolumen(v) })));
    grafico.timeScale().applyOptions({ timeVisible: tf !== "1d" });
    const visibles = { "1h": 240, "4h": 240, "1d": 365 }[tf];
    grafico.timeScale().setVisibleLogicalRange({ from: velas.length - visibles, to: velas.length + 3 });
    pintarLeyenda(velas[velas.length - 1]);

    const s = m.series[tf];
    $("nota").textContent =
      `${m.descripcion} Fuente: ${s.fuente}. Histórico guardado: ${s.velas.toLocaleString("es-ES")} velas desde ${s.desde}` +
      (velas.length < s.velas ? ` (en el gráfico, las últimas ${velas.length.toLocaleString("es-ES")}).` : ".");

    conectarVivo(m, tf);
    if (window.Analisis) await Analisis.cargar(m, tf);
  }

  function seleccionar(id, tf) {
    estado.mercado = id;
    if (tf) estado.tf = tf;
    window.scrollTo({ top: 0, behavior: "smooth" });
    return cargarSerie().catch(mostrarError);
  }

  // ---------------------------------------------------------------- en vivo (cripto)
  function desconectarVivo() {
    if (pingWs) clearInterval(pingWs);
    if (ws) { ws.onclose = null; ws.close(); }
    ws = null; pingWs = null;
    $("vivo").hidden = true;
  }

  function conectarVivo(m, tf) {
    desconectarVivo();
    if (!m.bitget || !("WebSocket" in window)) return;
    const simbolo = m.bitget;
    const socket = new WebSocket("wss://ws.bitget.com/v2/ws/public");
    ws = socket;
    socket.onopen = () => {
      socket.send(JSON.stringify({ op: "subscribe", args: [{ instType: "SPOT", channel: "ticker", instId: simbolo }] }));
      pingWs = setInterval(() => socket.readyState === 1 && socket.send("ping"), 25000);
    };
    socket.onmessage = (e) => {
      if (e.data === "pong") return;
      let msg; try { msg = JSON.parse(e.data); } catch { return; }
      const t = msg.data && msg.data[0];
      if (!t || !t.lastPr) return;
      $("vivo").hidden = false;
      aplicarPrecioVivo(parseFloat(t.lastPr), Math.floor(Number(t.ts) / 1000), tf);
    };
    socket.onclose = () => {
      $("vivo").hidden = true;
      if (ws === socket) setTimeout(() => ws === socket && conectarVivo(m, tf), 5000);
    };
  }

  function aplicarPrecioVivo(precio, ts, tf) {
    if (!velas.length || !isFinite(precio)) return;
    const inicio = Math.floor(ts / SEGUNDOS[tf]) * SEGUNDOS[tf];
    const ultima = velas[velas.length - 1];
    if (inicio < ultima.time) return;
    if (inicio === ultima.time) {
      ultima.close = precio;
      ultima.high = Math.max(ultima.high, precio);
      ultima.low = Math.min(ultima.low, precio);
    } else {
      // Empieza una vela nueva (el volumen llegará en la próxima actualización de datos)
      velas.push({ time: inicio, open: ultima.close, high: Math.max(ultima.close, precio),
                   low: Math.min(ultima.close, precio), close: precio, volume: 0 });
    }
    const v = velas[velas.length - 1];
    serieVelas.update(v);
    serieVolumen.update({ time: v.time, value: v.volume, color: colorVolumen(v) });
    pintarLeyenda(v);
    actualizarTarjeta(estado.mercado, precio);
  }

  // ---------------------------------------------------------------- interfaz
  function pintarMercados() {
    const nav = $("mercados");
    nav.innerHTML = "";
    for (const m of indice.mercados) {
      const b = document.createElement("button");
      b.className = "tarjeta";
      b.dataset.id = m.id;
      const clase = m.cambio_pct >= 0 ? "sube" : "baja";
      const signo = m.cambio_pct > 0 ? "+" : "";
      b.innerHTML = `<div class="n">${m.nombre}</div>` +
        `<div class="p">${fmtPrecio(m.ultimo, m.decimales)}</div>` +
        `<div class="c ${clase}">${m.cambio_pct == null ? "" : signo + fmtPrecio(m.cambio_pct) + " % día"}</div>`;
      b.onclick = () => { estado.mercado = m.id; cargarSerie().catch(mostrarError); };
      nav.appendChild(b);
    }
  }

  function actualizarTarjeta(id, precio) {
    const m = indice.mercados.find((x) => x.id === id);
    const b = document.querySelector(`.tarjeta[data-id="${id}"] .p`);
    if (m && b) b.textContent = fmtPrecio(precio, m.decimales);
  }

  function pintarControles() {
    document.querySelectorAll(".tarjeta").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.id === estado.mercado)));
    const m = mercadoActual();
    const cont = $("tfs");
    cont.innerHTML = "";
    for (const tf of indice.temporalidades) {
      const b = document.createElement("button");
      b.textContent = tf.toUpperCase();
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(tf === estado.tf));
      b.disabled = !m.series[tf];
      b.onclick = () => { estado.tf = tf; cargarSerie().catch(mostrarError); };
      cont.appendChild(b);
    }
  }

  function mostrarError(e) {
    console.error(e);
    $("nota").textContent = "No se pudieron cargar los datos: " + e.message;
  }

  async function iniciar() {
    crearGrafico();
    indice = await json("data/indice.json");
    const act = new Date(indice.actualizado);
    $("actualizado").textContent = "Datos actualizados: " +
      act.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" });
    const [mh, th] = location.hash.slice(1).split("/");
    estado.mercado = indice.mercados.some((m) => m.id === mh) ? mh : indice.mercados[0].id;
    if (SEGUNDOS[th]) estado.tf = th;
    pintarMercados();
    if (window.Analisis) {
      Analisis.resumen().catch((e) => console.warn("Resumen de señales:", e));
      Analisis.demo().catch((e) => console.warn("Cuenta demo:", e));
    }
    await cargarSerie();
  }

  iniciar().catch(mostrarError);
})();
