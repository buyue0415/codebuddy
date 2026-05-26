/**
 * KlineChart — 专业级烛形图引擎
 * 基于 Canvas 2D API，无外部依赖
 * 
 * 功能: 烛形图、MA5/10/20/60、MACD/KDJ/布林带、
 *       十字光标、悬浮提示、滚轮缩放、拖拽平移、画线工具
 */
class KlineChart {
  constructor(canvasId, tooltipId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.tooltip = document.getElementById(tooltipId);
    this.dpr = window.devicePixelRatio || 1;

    // Data
    this.bars = [];        // [{date,open,close,high,low}]
    this.visibleRange = {}; // {start, end} indices into this.bars
    this.currentCode = '';

    // Display state
    this.maFlags = {5:true, 10:true, 20:false, 60:false};
    this.subChart = 'none'; // 'macd'|'kdj'|'volume'|'none'
    this.drawMode = 'cursor'; // 'cursor'|'trend'|'hori'
    this.drawings = [];     // [{type:'trend'|'hori', x1,y1, x2,y2}]
    this.undoStack = [];

    // Interaction state
    this.mouseX = -1;
    this.mouseY = -1;
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartRange = {};
    this.isDrawing = false;
    this.drawStartX = 0;
    this.drawStartY = 0;
    this.hoveredBar = -1;

    // Layout
    this.mainRatio = 0.65; // 主图占 65%
    this.subRatio = 0.20;  // 副图占 20%
    this.margin = {top: 20, right: 20, bottom: 24, left: 60};
    this.subMargin = {top: 8, right: 20, bottom: 20, left: 60};

    // Theme
    this.colors = {
      up: '#ef4444', down: '#22c55e',
      grid: '#1e293b', text: '#94a3b8',
      crosshair: 'rgba(148,163,184,0.5)',
      ma5: '#3b82f6', ma10: '#f59e0b', ma20: '#a855f7', ma60: '#ec4899',
      macd: '#3b82f6', signal: '#f59e0b', histogram: '#a855f7',
      kLine: '#3b82f6', dLine: '#f59e0b', jLine: '#a855f7',
      volume: '#3b82f6',
      bollMid: '#3b82f6', bollUp: 'rgba(59,130,246,0.3)', bollDown: 'rgba(59,130,246,0.3)',
    };

    // Bind and register events
    this._bindEvents();
    // Auto-fit on first draw
    this._autoFit = true;
  }

  // ===================== Data =====================

  setData(code, rawBars) {
    this.currentCode = code;
    // rawBars: [[date,open,close,high,low], ...] newest-first
    // Convert to oldest-first for chart
    this.bars = rawBars.slice().reverse().map(b => ({
      date: b[0], open: b[1], close: b[2], high: b[3], low: b[4]
    }));
    if (this.bars.length === 0) return;
    if (this._autoFit) {
      this.visibleRange = { start: 0, end: this.bars.length - 1 };
      this._autoFit = false;
    }
    this.resize();
    this.draw();
  }

  appendBars(newBars) {
    // Append new bars (newest-first) to the end
    const reversed = newBars.slice().reverse().map(b => ({
      date: b[0], open: b[1], close: b[2], high: b[3], low: b[4]
    }));
    this.bars = this.bars.concat(reversed);
    this.visibleRange.end = this.bars.length - 1;
    this.draw();
  }

  resize() {
    const parent = this.canvas.parentElement;
    const w = parent.clientWidth;
    const h = parent.clientHeight;
    this.canvas.width = w * this.dpr;
    this.canvas.height = h * this.dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.W = w;
    this.H = h;
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  // ===================== Layout =====================

  _mainRect() {
    const m = this.margin;
    return {x: m.left, y: m.top, w: this.W - m.left - m.right,
            h: (this.H - m.top - m.bottom) * this.mainRatio};
  }

  _subRect() {
    const m = this.margin, sm = this.subMargin;
    const mainH = (this.H - m.top - m.bottom) * this.mainRatio;
    const subTop = m.top + mainH + sm.top;
    return {x: sm.left, y: subTop, w: this.W - sm.left - sm.right,
            h: (this.H - m.top - m.bottom) * this.subRatio};
  }

  // ===================== Coordinate Helpers =====================

  _calcScale(rect) {
    const {start, end} = this.visibleRange;
    if (start >= end || this.bars.length === 0) return null;
    const visibleBars = this.bars.slice(start, end + 1);
    let minP = Infinity, maxP = -Infinity;
    for (const b of visibleBars) {
      if (b.low < minP) minP = b.low;
      if (b.high > maxP) maxP = b.high;
    }
    const pad = (maxP - minP) * 0.08 || minP * 0.02;
    return {
      xUnit: rect.w / (end - start),
      yMin: minP - pad,
      yMax: maxP + pad,
      xStart: rect.x,
      yStart: rect.y,
      yEnd: rect.y + rect.h,
    };
  }

  _barX(idx, scale) { return scale.xStart + (idx - this.visibleRange.start) * scale.xUnit; }
  _priceY(price, scale) {
    return scale.yStart + (scale.yMax - price) / (scale.yMax - scale.yMin) * (scale.yEnd - scale.yStart);
  }
  _pixelToBar(px, scale) {
    const idx = Math.round(this.visibleRange.start + (px - scale.xStart) / scale.xUnit);
    return Math.max(this.visibleRange.start, Math.min(this.visibleRange.end, idx));
  }

  // ===================== Technical Indicators =====================

  _calcSMA(arr, period) {
    const result = [];
    for (let i = 0; i < arr.length; i++) {
      if (i < period - 1) { result.push(null); continue; }
      let sum = 0;
      for (let j = 0; j < period; j++) sum += arr[i - j];
      result.push(sum / period);
    }
    return result;
  }

  _calcEMA(arr, period) {
    const k = 2 / (period + 1);
    const result = [];
    for (let i = 0; i < arr.length; i++) {
      if (i === 0) { result.push(arr[0]); continue; }
      result.push(arr[i] * k + result[i - 1] * (1 - k));
    }
    return result;
  }

  _calcMACD(closes) {
    const ema12 = this._calcEMA(closes, 12);
    const ema26 = this._calcEMA(closes, 26);
    const dif = ema12.map((v, i) => v - ema26[i]);
    const dea = this._calcEMA(dif, 9);
    const macd = dif.map((v, i) => (v - dea[i]) * 2);
    return {dif, dea, macd};
  }

  _calcKDJ(highs, lows, closes) {
    const kArr = [], dArr = [], jArr = [];
    for (let i = 0; i < closes.length; i++) {
      if (i < 8) { kArr.push(50); dArr.push(50); jArr.push(50); continue; }
      const h9 = Math.max(...highs.slice(i - 8, i + 1));
      const l9 = Math.min(...lows.slice(i - 8, i + 1));
      const rsv = h9 !== l9 ? (closes[i] - l9) / (h9 - l9) * 100 : 50;
      const k = (2 / 3) * (kArr[i - 1] || 50) + (1 / 3) * rsv;
      const d = (2 / 3) * (dArr[i - 1] || 50) + (1 / 3) * k;
      const j = 3 * k - 2 * d;
      kArr.push(k); dArr.push(d); jArr.push(j);
    }
    return {k: kArr, d: dArr, j: jArr};
  }

  _calcBollinger(closes, period = 20) {
    const mid = this._calcSMA(closes, period);
    const upper = [], lower = [];
    for (let i = 0; i < closes.length; i++) {
      if (i < period - 1 || mid[i] === null) { upper.push(null); lower.push(null); continue; }
      let sumSq = 0;
      for (let j = 0; j < period; j++) sumSq += (closes[i - j] - mid[i]) ** 2;
      const std = Math.sqrt(sumSq / period);
      upper.push(mid[i] + 2 * std);
      lower.push(mid[i] - 2 * std);
    }
    return {mid, upper, lower};
  }

  _calcVolumeSMA(volumes, period = 5) {
    return this._calcSMA(volumes, period);
  }

  // ===================== Main Draw =====================

  draw() {
    const ctx = this.ctx;
    const W = this.W, H = this.H;
    if (!W || !H || this.bars.length === 0) return;

    // Clear
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);

    const mainRect = this._mainRect();
    const subRect = this._subRect();
    const scale = this._calcScale(mainRect);
    if (!scale) return;

    // Main chart
    this._drawGrid(mainRect, scale);
    this._drawCandlesticks(mainRect, scale);

    // MA lines
    if (this.maFlags[5]) this._drawMA(mainRect, scale, this._calcSMA, 5, this.colors.ma5);
    if (this.maFlags[10]) this._drawMA(mainRect, scale, this._calcSMA, 10, this.colors.ma10);
    if (this.maFlags[20]) this._drawMA(mainRect, scale, this._calcSMA, 20, this.colors.ma20);
    if (this.maFlags[60]) this._drawMA(mainRect, scale, this._calcSMA, 60, this.colors.ma60);

    // Bollinger bands (overlay on main chart)
    if (this.subChart === 'boll') this._drawBollinger(mainRect, scale);

    // Sub chart
    if (this.subChart === 'macd') this._drawMACD(subRect);
    else if (this.subChart === 'kdj') this._drawKDJ(subRect);
    else if (this.subChart === 'volume') this._drawVolume(subRect);

    // Drawing tools
    this._drawAllDrawings(mainRect, scale);

    // Crosshair
    if (this.mouseX >= 0 && this.mouseY >= 0) {
      this._drawCrosshair(mainRect, subRect, scale);
    }

    // Price scale labels
    this._drawPriceLabels(mainRect, scale);
  }

  // ===================== Drawing Primitives =====================

  _drawGrid(rect, scale) {
    const ctx = this.ctx;
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    // Horizontal lines (5 levels)
    for (let i = 0; i <= 4; i++) {
      const y = rect.y + (rect.h / 4) * i;
      ctx.beginPath(); ctx.moveTo(rect.x, y); ctx.lineTo(rect.x + rect.w, y); ctx.stroke();
    }
    // Vertical lines (≈8 lines)
    const nBars = this.visibleRange.end - this.visibleRange.start;
    const step = Math.max(1, Math.floor(nBars / 8));
    for (let i = this.visibleRange.start; i <= this.visibleRange.end; i += step) {
      const x = this._barX(i, scale);
      ctx.beginPath(); ctx.moveTo(x, rect.y); ctx.lineTo(x, rect.y + rect.h); ctx.stroke();
    }
  }

  _drawPriceLabels(rect, scale) {
    const ctx = this.ctx;
    ctx.fillStyle = this.colors.text;
    ctx.font = '11px Consolas,monospace';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const y = rect.y + (rect.h / 4) * i;
      const price = scale.yMax - (scale.yMax - scale.yMin) * (i / 4);
      ctx.fillText(price.toFixed(2), rect.x - 6, y + 4);
    }
  }

  _drawCandlesticks(rect, scale) {
    const ctx = this.ctx;
    const {start, end} = this.visibleRange;

    for (let i = start; i <= end; i++) {
      const bar = this.bars[i];
      const x = this._barX(i, scale);
      const candleW = Math.max(1, scale.xUnit * 0.6);
      const isUp = bar.close >= bar.open;

      const highY = this._priceY(bar.high, scale);
      const lowY = this._priceY(bar.low, scale);
      const openY = this._priceY(bar.open, scale);
      const closeY = this._priceY(bar.close, scale);

      // Wick
      ctx.strokeStyle = isUp ? this.colors.up : this.colors.down;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // Body
      const bodyTop = Math.min(openY, closeY);
      const bodyH = Math.max(1, Math.abs(closeY - openY));
      ctx.fillStyle = isUp ? this.colors.up : this.colors.down;
      ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);
    }
  }

  _drawMA(rect, scale, smaFn, period, color) {
    const ctx = this.ctx;
    const closes = this.bars.map(b => b.close);
    const ma = smaFn(closes, period);
    const {start, end} = this.visibleRange;

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let started = false;
    for (let i = start; i <= end; i++) {
      if (ma[i] === null) continue;
      const x = this._barX(i, scale);
      const y = this._priceY(ma[i], scale);
      if (!started) { ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  _drawBollinger(rect, scale) {
    const closes = this.bars.map(b => b.close);
    const bb = this._calcBollinger(closes);
    const ctx = this.ctx;
    const {start, end} = this.visibleRange;

    // Upper band
    ctx.strokeStyle = this.colors.bollMid;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    let started = false;
    for (let i = start; i <= end; i++) {
      if (bb.upper[i] === null) continue;
      const x = this._barX(i, scale);
      const y = this._priceY(bb.upper[i], scale);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Mid band
    ctx.setLineDash([]);
    ctx.strokeStyle = this.colors.bollMid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    started = false;
    for (let i = start; i <= end; i++) {
      if (bb.mid[i] === null) continue;
      const x = this._barX(i, scale);
      const y = this._priceY(bb.mid[i], scale);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Lower band
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = this.colors.bollMid;
    ctx.beginPath();
    started = false;
    for (let i = start; i <= end; i++) {
      if (bb.lower[i] === null) continue;
      const x = this._barX(i, scale);
      const y = this._priceY(bb.lower[i], scale);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Fill between upper and lower
    ctx.globalAlpha = 0.08;
    ctx.fillStyle = this.colors.bollMid;
    ctx.beginPath();
    started = false;
    for (let i = start; i <= end; i++) {
      if (bb.upper[i] === null) continue;
      const x = this._barX(i, scale);
      const y = this._priceY(bb.upper[i], scale);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    for (let i = end; i >= start; i--) {
      if (bb.lower[i] === null) continue;
      const x = this._barX(i, scale);
      const y = this._priceY(bb.lower[i], scale);
      ctx.lineTo(x, y);
    }
    ctx.closePath(); ctx.fill();
    ctx.globalAlpha = 1;
  }

  // ===================== Sub Charts =====================

  _drawMACD(rect) {
    const closes = this.bars.map(b => b.close);
    const macd = this._calcMACD(closes);
    const ctx = this.ctx;
    const {start, end} = this.visibleRange;

    // Background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.strokeStyle = '#1e293b';
    ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);

    // Find min/max
    let minV = Infinity, maxV = -Infinity;
    for (let i = start; i <= end; i++) {
      for (const arr of [macd.macd[i], macd.dif[i], macd.dea[i]]) {
        if (arr < minV) minV = arr; if (arr > maxV) maxV = arr;
      }
    }
    const pad = (maxV - minV) * 0.1 || 0.1;
    minV -= pad; maxV += pad;

    const xUnit = rect.w / (end - start);
    const toY = v => rect.y + rect.h - (v - minV) / (maxV - minV) * rect.h;

    // Histogram (MACD bar)
    const zeroY = toY(0);
    for (let i = start; i <= end; i++) {
      const x = rect.x + (i - start) * xUnit;
      const barH = toY(0) - toY(macd.macd[i]);
      ctx.fillStyle = macd.macd[i] >= 0 ? '#ef4444' : '#22c55e';
      ctx.fillRect(x - xUnit * 0.3, macd.macd[i] >= 0 ? toY(macd.macd[i]) : zeroY, xUnit * 0.6, Math.max(1, Math.abs(barH)));
    }

    // DIF line
    ctx.strokeStyle = this.colors.macd; ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = start; i <= end; i++) {
      const x = rect.x + (i - start) * xUnit;
      i === start ? ctx.moveTo(x, toY(macd.dif[i])) : ctx.lineTo(x, toY(macd.dif[i]));
    }
    ctx.stroke();

    // DEA line
    ctx.strokeStyle = this.colors.signal; ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = start; i <= end; i++) {
      const x = rect.x + (i - start) * xUnit;
      i === start ? ctx.moveTo(x, toY(macd.dea[i])) : ctx.lineTo(x, toY(macd.dea[i]));
    }
    ctx.stroke();

    // Label
    ctx.fillStyle = this.colors.text; ctx.font = '11px monospace';
    ctx.textAlign = 'left';
    const last = macd.dif[end];
    ctx.fillText('MACD(12,26,9)  DIF:' + (last ? last.toFixed(3) : '-'), rect.x + 4, rect.y + 14);
  }

  _drawKDJ(rect) {
    const highs = this.bars.map(b => b.high);
    const lows = this.bars.map(b => b.low);
    const closes = this.bars.map(b => b.close);
    const kdj = this._calcKDJ(highs, lows, closes);
    const ctx = this.ctx;
    const {start, end} = this.visibleRange;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.strokeStyle = '#1e293b';
    ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);

    const xUnit = rect.w / (end - start);
    const toY = v => rect.y + rect.h - (v - 0) / (100 - 0) * rect.h;

    // 50 line
    ctx.strokeStyle = '#334155'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(rect.x, toY(50)); ctx.lineTo(rect.x + rect.w, toY(50)); ctx.stroke();
    ctx.setLineDash([]);

    // Lines
    const lines = [
      {data: kdj.k, color: this.colors.kLine, label: 'K'},
      {data: kdj.d, color: this.colors.dLine, label: 'D'},
      {data: kdj.j, color: this.colors.jLine, label: 'J'},
    ];
    for (const line of lines) {
      ctx.strokeStyle = line.color; ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = start; i <= end; i++) {
        const x = rect.x + (i - start) * xUnit;
        const y = toY(line.data[i]);
        i === start ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.fillStyle = this.colors.text; ctx.font = '11px monospace';
    ctx.fillText('KDJ(9,3,3)', rect.x + 4, rect.y + 14);
  }

  _drawVolume(rect) {
    const ctx = this.ctx;
    const {start, end} = this.visibleRange;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.strokeStyle = '#1e293b';
    ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);

    // Use (close - open) as volume proxy (actual volume not available in current data)
    // Draw each bar with width
    const xUnit = rect.w / (end - start);
    for (let i = start; i <= end; i++) {
      const bar = this.bars[i];
      const vol = Math.abs(bar.close - bar.open) * 10000; // scaled proxy
      const maxVol = 1000;
      const h = Math.min(rect.h * 0.9, (vol / maxVol) * rect.h);
      const x = rect.x + (i - start) * xUnit;
      ctx.fillStyle = bar.close >= bar.open ? this.colors.up : this.colors.down;
      ctx.fillRect(x - xUnit * 0.4, rect.y + rect.h - h, xUnit * 0.8, h);
    }
    ctx.fillStyle = this.colors.text; ctx.font = '11px monospace';
    ctx.fillText('成交量', rect.x + 4, rect.y + 14);
  }

  // ===================== Crosshair & Tooltip =====================

  _drawCrosshair(mainRect, subRect, scale) {
    const ctx = this.ctx;
    ctx.save();

    // Vertical line
    ctx.strokeStyle = this.colors.crosshair;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(this.mouseX, mainRect.y);
    ctx.lineTo(this.mouseX, mainRect.y + mainRect.h);
    ctx.stroke();
    if (this.subChart !== 'none') {
      ctx.beginPath();
      ctx.moveTo(this.mouseX, subRect.y);
      ctx.lineTo(this.mouseX, subRect.y + subRect.h);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // Horizontal line
    ctx.beginPath();
    ctx.moveTo(mainRect.x, this.mouseY);
    ctx.lineTo(mainRect.x + mainRect.w, this.mouseY);
    ctx.stroke();

    ctx.restore();
  }

  _updateTooltip(barIdx) {
    const bar = this.bars[barIdx];
    if (!bar) { this.tooltip.style.display = 'none'; return; }
    const change = ((bar.close - bar.open) / bar.open * 100);
    const isUp = bar.close >= bar.open;

    this.tooltip.innerHTML = `
      <div class="tt-date">${bar.date}</div>
      <div class="tt-row"><span class="tt-label">开</span><span class="tt-val">${bar.open.toFixed(2)}</span></div>
      <div class="tt-row"><span class="tt-label">高</span><span class="tt-val">${bar.high.toFixed(2)}</span></div>
      <div class="tt-row"><span class="tt-label">低</span><span class="tt-val">${bar.low.toFixed(2)}</span></div>
      <div class="tt-row"><span class="tt-label">收</span><span class="tt-val ${isUp ? 'up' : 'dn'}">${bar.close.toFixed(2)}</span></div>
      <div class="tt-row"><span class="tt-label">涨跌</span><span class="tt-val ${isUp ? 'up' : 'dn'}">${change >= 0 ? '+' : ''}${change.toFixed(2)}%</span></div>
    `.trim();
    this.tooltip.style.display = 'block';

    // Position tooltip
    const ttW = this.tooltip.offsetWidth || 170;
    const ttH = this.tooltip.offsetHeight || 120;
    let tx = this.mouseX + 14;
    let ty = this.mouseY - ttH - 10;
    if (tx + ttW > this.W) tx = this.mouseX - ttW - 14;
    if (ty < 0) ty = this.mouseY + 14;
    this.tooltip.style.left = tx + 'px';
    this.tooltip.style.top = ty + 'px';
  }

  // ===================== Drawing Tools =====================

  _drawAllDrawings(rect, scale) {
    const ctx = this.ctx;
    for (const d of this.drawings) {
      ctx.strokeStyle = 'rgba(251,191,36,0.85)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
      ctx.beginPath();
      if (d.type === 'trend') {
        ctx.moveTo(this._barX(d.i1, scale), this._priceY(d.p1, scale));
        ctx.lineTo(this._barX(d.i2, scale), this._priceY(d.p2, scale));
      } else if (d.type === 'hori') {
        const y = this._priceY(d.price, scale);
        ctx.moveTo(rect.x, y);
        ctx.lineTo(rect.x + rect.w, y);
      }
      ctx.stroke();
    }
  }

  // ===================== Events =====================

  _bindEvents() {
    const c = this.canvas;
    c.addEventListener('mousemove', e => this._onMouseMove(e));
    c.addEventListener('mouseleave', () => { this.mouseX = -1; this.tooltip.style.display = 'none'; this.draw(); });
    c.addEventListener('mousedown', e => this._onMouseDown(e));
    c.addEventListener('mouseup', e => this._onMouseUp(e));
    c.addEventListener('wheel', e => this._onWheel(e), {passive: false});
    window.addEventListener('resize', () => { this.resize(); this.draw(); });
  }

  _onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    this.mouseX = e.clientX - rect.left;
    this.mouseY = e.clientY - rect.top;
    const mainRect = this._mainRect();
    const scale = this._calcScale(mainRect);
    if (!scale) return;

    if (this.isDragging && this.drawMode === 'cursor') {
      // Pan
      const dx = this.mouseX - this.dragStartX;
      const barDelta = -Math.round(dx / scale.xUnit);
      const newStart = this.dragStartRange.start + barDelta;
      const newEnd = this.dragStartRange.end + barDelta;
      if (newStart >= 0 && newEnd < this.bars.length) {
        this.visibleRange = {start: newStart, end: newEnd};
      }
      this.dragStartX = this.mouseX;
      this.dragStartRange = {...this.visibleRange};
      this.draw();
    } else if (this.isDrawing && (this.drawMode === 'trend' || this.drawMode === 'hori')) {
      // Update drawing end point
      if (this.drawMode === 'trend') {
        const endIdx = this._pixelToBar(this.mouseX, scale);
        const endPrice = scale.yMax - (this.mouseY - scale.yStart) / (scale.yEnd - scale.yStart) * (scale.yMax - scale.yMin);
        if (this._tempDrawing) {
          this._tempDrawing.i2 = endIdx;
          this._tempDrawing.p2 = endPrice;
        }
      } else if (this.drawMode === 'hori') {
        if (this._tempDrawing) {
          const price = scale.yMax - (this.mouseY - scale.yStart) / (scale.yEnd - scale.yStart) * (scale.yMax - scale.yMin);
          this._tempDrawing.price = price;
        }
      }
      this.draw();
      // Re-draw temp drawing on top
      this._drawTempDrawing(mainRect, scale);
    } else {
      // Update hovered bar index
      this.hoveredBar = this._pixelToBar(this.mouseX, scale);
      this._updateTooltip(this.hoveredBar);
      this.draw();
    }
  }

  _drawTempDrawing(rect, scale) {
    if (!this._tempDrawing) return;
    const ctx = this.ctx;
    ctx.strokeStyle = 'rgba(251,191,36,0.9)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    const d = this._tempDrawing;
    if (d.type === 'trend') {
      ctx.moveTo(this._barX(d.i1, scale), this._priceY(d.p1, scale));
      ctx.lineTo(this._barX(d.i2, scale), this._priceY(d.p2, scale));
    } else if (d.type === 'hori') {
      const y = this._priceY(d.price, scale);
      ctx.moveTo(rect.x, y);
      ctx.lineTo(rect.x + rect.w, y);
    }
    ctx.stroke();
  }

  _onMouseDown(e) {
    const mainRect = this._mainRect();
    const scale = this._calcScale(mainRect);
    if (!scale) return;

    if (this.drawMode === 'cursor') {
      this.isDragging = true;
      this.dragStartX = this.mouseX;
      this.dragStartRange = {...this.visibleRange};
    } else if (this.drawMode === 'trend') {
      const idx = this._pixelToBar(this.mouseX, scale);
      const price = scale.yMax - (this.mouseY - scale.yStart) / (scale.yEnd - scale.yStart) * (scale.yMax - scale.yMin);
      this._tempDrawing = {type: 'trend', i1: idx, p1: price, i2: idx, p2: price};
      this.isDrawing = true;
    } else if (this.drawMode === 'hori') {
      const price = scale.yMax - (this.mouseY - scale.yStart) / (scale.yEnd - scale.yStart) * (scale.yMax - scale.yMin);
      this._tempDrawing = {type: 'hori', price: price};
      this.isDrawing = true;
    }
  }

  _onMouseUp(e) {
    if (this.isDrawing && this._tempDrawing) {
      this.undoStack.push({action: 'add', drawing: {...this._tempDrawing}});
      this.drawings.push({...this._tempDrawing});
      this._tempDrawing = null;
      this.isDrawing = false;
      this.draw();
    }
    this.isDragging = false;
  }

  _onWheel(e) {
    e.preventDefault();
    const mainRect = this._mainRect();
    const scale = this._calcScale(mainRect);
    if (!scale) return;

    const delta = e.deltaY > 0 ? 1 : -1;
    const zoomFactor = 0.15;
    const range = this.visibleRange.end - this.visibleRange.start;
    const zoomAmount = Math.max(1, Math.round(range * zoomFactor));

    // Zoom around mouse position
    const mouseBar = this._pixelToBar(this.mouseX, scale);
    const mouseRatio = (mouseBar - this.visibleRange.start) / range;

    if (delta < 0) {
      // Zoom in
      const newRange = Math.max(5, range - zoomAmount);
      const newStart = Math.round(mouseBar - mouseRatio * newRange);
      this.visibleRange = {
        start: Math.max(0, newStart),
        end: Math.min(this.bars.length - 1, newStart + newRange),
      };
    } else {
      // Zoom out
      const newRange = range + zoomAmount;
      const newStart = Math.round(mouseBar - mouseRatio * newRange);
      this.visibleRange = {
        start: Math.max(0, newStart),
        end: Math.min(this.bars.length - 1, newStart + newRange),
      };
    }
    this.draw();
  }

  // ===================== Public API =====================

  setMA(period, show) {
    this.maFlags[period] = show;
    this.draw();
  }

  setSubChart(type) {
    this.subChart = type;
    this.draw();
  }

  setDrawMode(mode) {
    this.drawMode = mode;
    this.isDrawing = false;
    this._tempDrawing = null;
    if (mode === 'clear') {
      this.undoStack = [];
      this.drawings = [];
      this.drawMode = 'cursor';
      this.draw();
    } else if (mode === 'undo') {
      if (this.undoStack.length > 0) {
        const last = this.undoStack.pop();
        if (last.action === 'add') {
          this.drawings.pop();
        }
      }
      this.drawMode = 'cursor';
      this.draw();
    }
  }

  autoFit() {
    this.visibleRange = {start: 0, end: this.bars.length - 1};
    this.draw();
  }

  destroy() {
    // Events are removed by replacing canvas in DOM
    this.canvas = null;
    this.ctx = null;
  }
}
