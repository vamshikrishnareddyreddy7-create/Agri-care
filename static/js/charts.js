/* AgriCare — dependency-free SVG charts (no CDN required). */
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";

  function el(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  function tooltipFor(container) {
    let tip = container.querySelector(".chart-tooltip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "chart-tooltip";
      container.appendChild(tip);
    }
    return tip;
  }

  function showTip(tip, x, y, html) {
    tip.innerHTML = html;
    tip.style.opacity = "1";
    tip.style.left = `${x}px`;
    tip.style.top = `${y - 10}px`;
  }

  function hideTip(tip) {
    tip.style.opacity = "0";
  }

  // ------------------------------------------------------------------ //
  //  Donut chart
  // ------------------------------------------------------------------ //
  function donut(container, { labels = [], values = [], colors = [] }, opts = {}) {
    const sum = values.reduce((a, b) => a + b, 0);
    const total = sum || 1;
    const size = opts.size || 170;
    const stroke = opts.stroke || 22;
    const r = (size - stroke) / 2 - 2;
    const c = 2 * Math.PI * r;

    container.innerHTML = "";
    container.style.width = `${size}px`;
    container.style.height = `${size}px`;
    container.classList.add("chart-box");

    const svg = el("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size });
    const g = el("g", { transform: `rotate(-90 ${size / 2} ${size / 2})` });
    g.appendChild(el("circle", {
      cx: size / 2, cy: size / 2, r, fill: "none",
      stroke: getComputedStyle(document.documentElement).getPropertyValue("--bg-soft") || "#eef2ee",
      "stroke-width": stroke,
    }));

    let offset = 0;
    values.forEach((v, i) => {
      if (v <= 0) return;
      const frac = v / total;
      const dash = frac * c;
      const seg = el("circle", {
        cx: size / 2, cy: size / 2, r, fill: "none",
        stroke: colors[i] || "#22c55e",
        "stroke-width": stroke,
        "stroke-dasharray": `${dash} ${c - dash}`,
        "stroke-dashoffset": -offset,
        "stroke-linecap": "butt",
      });
      seg.style.transition = "stroke-dasharray .7s ease";
      seg.addEventListener("mousemove", (e) => {
        const tip = tooltipFor(container);
        showTip(tip, e.offsetX + 12, e.offsetY,
          `<b>${escapeHtml(String(labels[i] || ""))}</b> — ${v} (${Math.round(frac * 100)}%)`);
      });
      seg.addEventListener("mouseleave", () => hideTip(tooltipFor(container)));
      g.appendChild(seg);
      offset += dash;
    });
    svg.appendChild(g);
    container.appendChild(svg);

    const center = document.createElement("div");
    center.className = "donut-center-label";
    center.innerHTML = `<b>${opts.centerValue ?? sum}</b><span>${escapeHtml(String(opts.centerLabel || "total"))}</span>`;
    container.appendChild(center);
  }

  // ------------------------------------------------------------------ //
  //  Horizontal bar list (usage / comparisons)
  // ------------------------------------------------------------------ //
  function hbars(container, { labels = [], values = [], color = "#166534" }) {
    const max = Math.max(...values, 1);
    container.innerHTML = "";
    container.classList.add("chart-legend");
    values.forEach((v, i) => {
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `
        <span class="swatch" style="background:${color}"></span>
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(String(labels[i]))}</span>
        <span class="val">${escapeHtml(window.fmtNumber ? fmtNumber(v) : v)}</span>`;
      container.appendChild(row);
      const bar = document.createElement("div");
      bar.className = "risk-bar";
      bar.style.marginTop = "4px";
      bar.style.marginBottom = "10px";
      bar.innerHTML = `<i style="width:0%;background:${color}" data-w="${Math.max(4, (v / max) * 100)}%"></i>`;
      container.appendChild(bar);
      requestAnimationFrame(() => {
        const i2 = bar.querySelector("i");
        i2.style.width = i2.dataset.w;
      });
    });
  }

  // ------------------------------------------------------------------ //
  //  Vertical bar chart
  // ------------------------------------------------------------------ //
  function vbars(container, { labels = [], values = [], color = "#166534", height = 190 }) {
    const max = Math.max(...values, 1);
    const W = Math.max(300, labels.length * 46);
    const pad = { t: 12, r: 8, b: 26, l: 8 };
    const innerH = height - pad.t - pad.b;
    container.innerHTML = "";
    container.classList.add("chart-box");
    const svg = el("svg", { viewBox: `0 0 ${W} ${height}`, width: "100%", preserveAspectRatio: "xMidYMid meet" });
    const step = (W - pad.l - pad.r) / labels.length;

    labels.forEach((lb, i) => {
      const v = values[i] || 0;
      const bw = step * 0.55;
      const x = pad.l + i * step + (step - bw) / 2;
      const bh = (v / max) * innerH;
      const y = pad.t + innerH - bh;
      const bar = el("rect", {
        x, y, width: bw, height: Math.max(bh, v > 0 ? 3 : 0),
        rx: 6, fill: color, "data-v": v,
      });
      bar.style.transition = "height .6s ease, y .6s ease";
      bar.addEventListener("mousemove", (e) => {
        const tip = tooltipFor(container);
        showTip(tip, e.offsetX + 12, e.offsetY, `<b>${escapeHtml(String(lb))}</b> — ${fmtNumber(v)}`);
      });
      bar.addEventListener("mouseleave", () => hideTip(tooltipFor(container)));
      svg.appendChild(bar);
      const lbl = el("text", {
        x: x + bw / 2, y: height - 8, "text-anchor": "middle",
        fill: "var(--muted)", "font-size": 11,
      });
      lbl.textContent = String(lb);
      svg.appendChild(lbl);
    });

    // grid lines
    for (let g = 1; g <= 4; g++) {
      const gy = pad.t + (innerH / 4) * g;
      svg.appendChild(el("line", {
        x1: pad.l, y1: gy, x2: W - pad.r, y2: gy,
        stroke: "var(--border)", "stroke-width": 1, "stroke-dasharray": "3 4",
      }));
    }
    container.appendChild(svg);
  }

  // ------------------------------------------------------------------ //
  //  Line chart (maintenance history over months)
  // ------------------------------------------------------------------ //
  function line(container, { labels = [], values = [], color = "#166534", height = 190 }) {
    const W = Math.max(340, labels.length * 60);
    const pad = { t: 16, r: 10, b: 28, l: 34 };
    const innerH = height - pad.t - pad.b;
    const max = Math.max(...values, 1);
    container.innerHTML = "";
    container.classList.add("chart-box");
    const svg = el("svg", { viewBox: `0 0 ${W} ${height}`, width: "100%", preserveAspectRatio: "xMidYMid meet" });

    for (let g = 0; g <= 4; g++) {
      const gy = pad.t + (innerH / 4) * g;
      const val = Math.round((max / 4) * (4 - g));
      svg.appendChild(el("line", {
        x1: pad.l, y1: gy, x2: W - pad.r, y2: gy,
        stroke: "var(--border)", "stroke-width": 1, "stroke-dasharray": "3 4",
      }));
      const tx = el("text", { x: pad.l - 8, y: gy + 4, "text-anchor": "end", fill: "var(--muted)", "font-size": 10 });
      tx.textContent = val;
      svg.appendChild(tx);
    }

    const pts = labels.map((_, i) => {
      const x = pad.l + (W - pad.l - pad.r) * (labels.length === 1 ? 0.5 : i / (labels.length - 1));
      const y = pad.t + innerH - (values[i] / max) * innerH;
      return [x, y];
    });

    // area fill
    if (pts.length > 1) {
      const area = el("path", {
        d: `M${pts[0][0]},${pad.t + innerH} L${pts.map((p) => p.join(",")).join(" L")} L${pts[pts.length - 1][0]},${pad.t + innerH} Z`,
        fill: color, opacity: "0.12",
      });
      svg.appendChild(area);
    }
    // line
    if (pts.length > 1) {
      svg.appendChild(el("path", {
        d: `M${pts.map((p) => p.join(",")).join(" L")}`,
        fill: "none", stroke: color, "stroke-width": 2.5, "stroke-linecap": "round",
        "stroke-linejoin": "round",
      }));
    }
    pts.forEach((p, i) => {
      const dot = el("circle", { cx: p[0], cy: p[1], r: 4.5, fill: color, stroke: "var(--card)", "stroke-width": 2 });
      dot.addEventListener("mousemove", (e) => {
        const tip = tooltipFor(container);
        showTip(tip, e.offsetX + 12, e.offsetY,
          `<b>${escapeHtml(String(labels[i]))}</b> — ${fmtNumber(values[i])} services`);
      });
      dot.addEventListener("mouseleave", () => hideTip(tooltipFor(container)));
      svg.appendChild(dot);
      const lbl = el("text", {
        x: p[0], y: height - 8, "text-anchor": "middle", fill: "var(--muted)", "font-size": 11,
      });
      lbl.textContent = String(labels[i]);
      svg.appendChild(lbl);
    });
    container.appendChild(svg);
  }

  return { donut, hbars, vbars, line };
})();