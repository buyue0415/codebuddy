<template>
  <div class="page-content">
    <div v-if="data.loading && !Object.keys(data.allKlineDaily).length" class="loading"><div class="spinner"></div></div>
    <template v-else>
      <div class="tab-bar" v-if="data.watchlist.length">
        <button v-for="s in data.watchlist" :key="s.code" class="tab-btn" :class="{ active: activeCode === s.code }" @click="switchStock(s.code)">{{ s.name }}</button>
      </div>

      <template v-if="activeCode">
        <div class="card">
          <h2 id="kline-title">{{ stockName }} 日K走势</h2>
          <div class="chart-wrap" style="height:380px">
            <canvas ref="klineCanvas"></canvas>
          </div>
          <div ref="sliderWrap" class="slider-wrap">
            <div ref="sliderBar" class="slider-bar"></div>
            <div ref="sliderHandle" class="slider-handle"></div>
            <div ref="sliderLKnob" class="slider-knob slider-lknob"></div>
            <div ref="sliderRKnob" class="slider-knob slider-rknob"></div>
            <div ref="sliderHint" class="slider-hint">
              <span ref="sliderStartDate"></span><span ref="sliderEndDate"></span>
            </div>
          </div>
          <div class="chart-wrap chart-dy-wrap" style="height:180px; margin-top:8px; border-top:1px solid #e5e7eb; padding-top:4px">
            <canvas ref="dyCanvas"></canvas>
          </div>
          <div class="chart-hint" ref="dyHint">滚轮平移 ｜ Ctrl+滚轮缩放</div>
        </div>

        <div class="card">
          <h2>{{ stockName }} 月度涨跌幅</h2>
          <div class="monthly-filter">
            <input type="date" v-model="mcStart" class="mc-date-input">
            <span class="mc-date-sep">至</span>
            <input type="date" v-model="mcEnd" class="mc-date-input">
            <span class="mc-stats" v-if="mcStats">
              <span class="mc-stat-item">{{ mcStats.total }}个月</span>
              <span class="mc-stat-sep">|</span>
              <span class="mc-stat-item">涨 <b style="color:#ef4444">{{ mcStats.upCount }}</b> 个</span>
              <span class="mc-stat-item">均 <b style="color:#ef4444">+{{ mcStats.upAvg }}%</b></span>
              <span class="mc-stat-sep">|</span>
              <span class="mc-stat-item">跌 <b style="color:#16a34a">{{ mcStats.downCount }}</b> 个</span>
              <span class="mc-stat-item">均 <b style="color:#16a34a">{{ mcStats.downAvg }}%</b></span>
              <span class="mc-stat-sep">|</span>
              <span class="mc-stat-item">最大 <b style="color:#ef4444">+{{ mcStats.maxUp }}%</b></span>
              <span class="mc-stat-sep">/</span>
              <span class="mc-stat-item"><b style="color:#16a34a">{{ mcStats.maxDown }}%</b></span>
              <span class="mc-stat-sep">|</span>
              <span class="mc-stat-item">平均 <b :style="{color:mcStats.avg>=0?'#ef4444':'#16a34a'}">{{ mcStats.avg >= 0 ? '+' : '' }}{{ mcStats.avg }}%</b></span>
            </span>
          </div>
          <div class="chart-wrap" style="height:300px"><canvas ref="monthlyCanvas"></canvas></div>
          <div ref="mSliderWrap" class="slider-wrap">
            <div class="slider-bar"></div>
            <div ref="mSliderHandle" class="slider-handle"></div>
            <div ref="mSliderLKnob" class="slider-knob slider-lknob"></div>
            <div ref="mSliderRKnob" class="slider-knob slider-rknob"></div>
            <div class="slider-hint"><span ref="mSliderStartDate"></span><span ref="mSliderEndDate"></span></div>
          </div>
        </div>

        <div class="card">
          <h2>季节性规律（月均涨跌幅 %）</h2>
          <div class="chart-wrap" style="height:280px"><canvas ref="seasonalCanvas"></canvas></div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useDataStore } from '@/stores/data.js'
import { fmt, apiCall } from '@/api/client.js'

const data = useDataStore()
const activeCode = ref('')
const klineCanvas = ref(null)
const dyCanvas = ref(null)
const monthlyCanvas = ref(null)
const seasonalCanvas = ref(null)
const dyHint = ref(null)
const klineTitle = ref(null)
const sliderWrap = ref(null)
const sliderHandle = ref(null)
const sliderLKnob = ref(null)
const sliderRKnob = ref(null)
const sliderHint = ref(null)
const sliderStartDate = ref(null)
const sliderEndDate = ref(null)
const mSliderWrap = ref(null)
const mSliderHandle = ref(null)
const mSliderLKnob = ref(null)
const mSliderRKnob = ref(null)
const mSliderStartDate = ref(null)
const mSliderEndDate = ref(null)
const mcStart = ref('')
const mcEnd = ref('')
const mcStats = ref(null)

let klineChart = null, dyChart = null, monthlyChart = null, seasonalChart = null
let klineBars = [], klineLabels = [], crossX = -1, crossIdx = -1
let klineTT = null, dyTT = null, monthlyTT = null
let mcSorted = []
let zoomState = null
let monthlyZoomState = null
let patternScanResult = null

const stockName = computed(() => data.watchlist.find(s => s.code === activeCode.value)?.name || activeCode.value)

function switchStock(code) { activeCode.value = code }

function calcSMA(arr, period) {
  const r = []
  for (let i = 0; i < arr.length; i++) {
    if (i < period - 1) { r.push(null); continue }
    let sum = 0; for (let j = i - period + 1; j <= i; j++) sum += arr[j]
    r.push(+(sum / period).toFixed(2))
  }
  return r
}

function ensureTooltip(container, id) {
  let el = document.getElementById(id)
  if (!el) {
    el = document.createElement('div')
    el.id = id
    el.style.cssText = 'position:absolute;pointer-events:none;background:rgba(0,0,0,.85);color:#fff;padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.7;z-index:200;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.3);display:none;font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif'
    container.appendChild(el)
  }
  return el
}

function computeMonthlyStats(mcData, startStr, endStr) {
  if (!mcData.length || !startStr || !endStr) return null
  const sm = startStr.slice(0, 7), em = endStr.slice(0, 7)
  const filtered = mcData.filter(([d]) => d >= sm && d <= em)
  if (!filtered.length) return null
  const vals = filtered.map(([, v]) => v)
  const up = vals.filter(v => v > 0), down = vals.filter(v => v < 0)
  return {
    total: filtered.length,
    upCount: up.length, downCount: down.length,
    upAvg: up.length ? +(up.reduce((a, b) => a + b, 0) / up.length).toFixed(2) : 0,
    downAvg: down.length ? +(down.reduce((a, b) => a + b, 0) / down.length).toFixed(2) : 0,
    maxUp: Math.max(...vals, 0),
    maxDown: Math.min(...vals, 0),
    avg: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2),
  }
}

function renderAll() {
  const code = activeCode.value
  if (!code) return
  const klineRaw = data.allKlineDaily[code] || []
  const kline = klineRaw.slice().reverse()
  if (!kline.length) return
  const divs = data.allDividends.filter(d => d.code === code)
  const mcRaw = data.allKlineMonthly[code] || []
  const mc = mcRaw.map(b => [b[0], b[6]])
  const sea = data.seasonal[code] || []

  const labels = kline.map(k => k[0])
  const closes = kline.map(k => k.length === 5 ? k[2] : k[4])
  const sma20 = calcSMA(closes, 20)
  const sma60 = calcSMA(closes, 60)
  klineLabels = labels

  // Candle data for candlestick chart
  const candleData = kline.map((k, i) => {
    const o = k[1], c = k.length === 5 ? k[2] : k[4], h = k.length === 5 ? k[3] : k[2], l = k.length === 5 ? k[4] : k[3]
    return { x: i, o, h, l, c }
  })
  const sma20Line = sma20.map((v, i) => ({ x: i, y: v }))
  const sma60Line = sma60.map((v, i) => ({ x: i, y: v }))

  // Dividend markers
  const divLookup = {}
  divs.forEach(d => { divLookup[d.date] = d })
  const divPoints = closes.map((c, i) => divLookup[labels[i]] ? c : null)
  const divScatter = []
  labels.forEach((date, i) => { if (divLookup[date]) divScatter.push({ x: i, y: closes[i] }) })

  // Bars for tooltip
  klineBars = kline.map(k => {
    const bar = { date: k[0], open: k[1], close: k.length === 5 ? k[2] : k[4], high: k.length === 5 ? k[3] : k[2], low: k.length === 5 ? k[4] : k[3] }
    const dv = divLookup[k[0]]
    if (dv) bar.dividend = { amount: dv.amount, price: dv.price, per_share: dv.per_share || 0 }
    return bar
  })

  const Chart = window.Chart
  if (!Chart) return

  // Chinese convention: 涨=红 #ef4444 跌=绿 #16a34a
  // (library default is western: up=green, down=red)
  if (Chart.defaults.elements && Chart.defaults.elements.candlestick) {
    Chart.defaults.elements.candlestick.color = {
      up: 'rgba(239,68,68,1)',     // 上涨 → 红色
      down: 'rgba(22,163,74,1)',   // 下跌 → 绿色
      unchanged: 'rgba(90,90,90,1)'
    }
  }

  // ---- X-axis date label helper (shared between kline & dy chart) ----
  function drawXDateLabel(ctx, ca, xPos, dateStr) {
    if (!dateStr || !ctx || !ca) return
    ctx.save()
    ctx.font = '11px -apple-system,PingFang SC,Microsoft YaHei,sans-serif'
    const tw = ctx.measureText(dateStr).width
    const pad = 5, r = 4
    const lw = tw + pad * 2, lh = 18
    let lx = xPos - lw / 2
    lx = Math.max(ca.left + 2, Math.min(ca.right - lw - 2, lx))
    const ly = ca.bottom + 10
    ctx.fillStyle = 'rgba(30,30,60,0.8)'
    ctx.beginPath(); ctx.roundRect(lx, ly, lw, lh, r); ctx.fill()
    ctx.fillStyle = '#93c5fd'
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    ctx.fillText(dateStr, lx + lw / 2, ly + lh / 2)
    ctx.restore()
  }

  const crossPlugin = {
    id: 'klineCross',
    afterDraw: function(chart) {
      try {
        const ctx = chart.ctx
        if (crossX >= 0) {
          const ra = chart.scales.y
          ctx.save(); ctx.setLineDash([4, 3])
          ctx.strokeStyle = 'rgba(100,100,255,.35)'; ctx.lineWidth = 1
          ctx.beginPath(); ctx.moveTo(crossX, ra.top); ctx.lineTo(crossX, ra.bottom)
          ctx.stroke(); ctx.restore()
        }
        // Pattern markers strip (inside chartArea, above X-axis labels)
        if (patternScanResult && chart.scales && chart.scales.x && chart.chartArea) {
          const xs = chart.scales.x; const ca = chart.chartArea
          const s = zoomState ? zoomState.start : 0; const e = zoomState ? zoomState.end : 0
          if (s == null) return
          const stripTop = ca.bottom - 14
          const byIdx = {}
          ;(patternScanResult.bullish || []).forEach(function(p) {
            if (!byIdx[p.idx]) byIdx[p.idx] = {}; byIdx[p.idx].bullish = (byIdx[p.idx].bullish||0) + 1
          })
          ;(patternScanResult.bearish || []).forEach(function(p) {
            if (!byIdx[p.idx]) byIdx[p.idx] = {}; byIdx[p.idx].bearish = (byIdx[p.idx].bearish||0) + 1
          })
          ctx.save()
          ctx.fillStyle = 'rgba(248,250,252,0.85)'; ctx.fillRect(ca.left, stripTop, ca.right - ca.left, 14)
          ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 0.5; ctx.strokeRect(ca.left, stripTop, ca.right - ca.left, 14)
          for (let gi = s; gi < e; gi++) {
            const info = byIdx[gi]
            if (!info) continue
            const px = xs.getPixelForValue(gi - s)
            const r = 3
            if (info.bullish && info.bearish) {
              ctx.beginPath(); ctx.arc(px, stripTop + 7, r, 0, Math.PI * 2); ctx.fillStyle = '#f59e0b'; ctx.fill()
              ctx.beginPath(); ctx.arc(px + 1, stripTop + 6, r * 0.4, 0, Math.PI * 2); ctx.fillStyle = '#8b5cf6'; ctx.fill()
            } else if (info.bullish) {
              ctx.beginPath(); ctx.arc(px, stripTop + 7, r, 0, Math.PI * 2); ctx.fillStyle = '#f59e0b'; ctx.fill()
            } else if (info.bearish) {
              ctx.beginPath(); ctx.arc(px, stripTop + 7, r, 0, Math.PI * 2); ctx.fillStyle = '#8b5cf6'; ctx.fill()
            }
          }
          ctx.restore()
        }
        // X-axis date label on hover
        if (crossX >= 0 && crossIdx >= 0 && chart.chartArea) {
          const ca = chart.chartArea
          ctx.save(); ctx.strokeStyle = 'rgba(100,100,255,.7)'; ctx.lineWidth = 2.5
          ctx.beginPath(); ctx.moveTo(crossX, ca.bottom); ctx.lineTo(crossX, ca.bottom + 8)
          ctx.stroke(); ctx.restore()
          drawXDateLabel(ctx, ca, crossX, klineLabels[crossIdx])
        }
      } catch (_) { /* prevent errors from breaking chart render */ }
    },
  }

  // ---- K-line chart (candlestick) ----
  if (klineChart) klineChart.destroy()
  const kCtx = klineCanvas.value
  klineTT = ensureTooltip(kCtx.parentElement, 'kline-tooltip')

  function buildKlineChart(type) {
    if (type === 'candlestick') {
      try {
        klineChart = new Chart(kCtx, {
          type: 'candlestick',
          data: {
            datasets: [
              { label: '日K线', data: candleData },
              { label: 'SMA20', data: sma20Line, type: 'line', borderColor: '#f59e0b', borderWidth: 1, pointRadius: 0, borderDash: [4, 2], fill: false, order: 1 },
              { label: 'SMA60', data: sma60Line, type: 'line', borderColor: '#ef4444', borderWidth: 1, pointRadius: 0, borderDash: [6, 3], fill: false, order: 1 },
              ...(divScatter.length ? [{ label: '分红', data: divScatter, type: 'scatter', borderColor: '#dc2626', backgroundColor: '#dc2626', pointRadius: 8, pointStyle: 'triangle', showLine: false, order: 2 }] : []),
            ],
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11 } } }, tooltip: { enabled: false } },
            scales: {
              x: { type: 'linear', ticks: { callback: function(v) { return labels[Math.round(v)] || '' }, font: { size: 9 }, autoSkipPadding: 1 } },
              y: { ticks: { font: { size: 10 } } },
            },
          },
          plugins: [crossPlugin],
        })
        return true
      } catch (e) { console.warn('Candlestick init failed, fallback to line:', e) }
    }
    // Fallback to line chart
    klineChart = new Chart(kCtx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: '收盘价', data: closes, borderColor: '#2563eb', borderWidth: 2, pointRadius: 1, tension: .3, fill: false },
          { label: 'SMA20', data: sma20, borderColor: '#f59e0b', borderWidth: 1, pointRadius: 0, borderDash: [4, 2], fill: false },
          { label: 'SMA60', data: sma60, borderColor: '#ef4444', borderWidth: 1, pointRadius: 0, borderDash: [6, 3], fill: false },
          { label: '分红', data: divPoints, borderColor: '#dc2626', backgroundColor: '#dc2626', pointRadius: 8, pointStyle: 'triangle', showLine: false },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11 } } }, tooltip: { enabled: false } },
        scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { ticks: { font: { size: 10 } } } },
      },
      plugins: [crossPlugin],
    })
    return true
  }
  const hasCandlestick = Chart.registry && typeof Chart.registry.getController === 'function' && !!Chart.registry.getController('candlestick')
  buildKlineChart(hasCandlestick ? 'candlestick' : 'line')

  // ---- Pattern scan ----
  apiCall('GET', '/api/v2/pattern-scan/' + code).then(resp => {
    if (!resp?.success) return
    patternScanResult = resp.data
    if (klineChart) klineChart.draw()
  })

  // ---- Monthly ----
  if (monthlyChart) monthlyChart.destroy()
  mcSorted = mc.slice().reverse()
  const mcLabels = mcSorted.map(m => m[0]), mcData = mcSorted.map(m => m[1])
  let monthlyHoverIdx = -1
  const monthlyCross = {
    id: 'monthlyCross',
    afterDraw: function(chart) {
      if (monthlyHoverIdx < 0 || !chart.chartArea) return
      const ctx = chart.ctx, xs = chart.scales.x, ra = chart.scales.y
      const xp = xs.getPixelForValue(monthlyHoverIdx)
      // vertical line
      ctx.save(); ctx.setLineDash([4, 3])
      ctx.strokeStyle = 'rgba(100,100,255,.35)'; ctx.lineWidth = 1
      ctx.beginPath(); ctx.moveTo(xp, ra.top); ctx.lineTo(xp, ra.bottom)
      ctx.stroke(); ctx.restore()
      // X-axis tick
      ctx.save(); ctx.strokeStyle = 'rgba(100,100,255,.7)'; ctx.lineWidth = 2.5
      ctx.beginPath(); ctx.moveTo(xp, chart.chartArea.bottom); ctx.lineTo(xp, chart.chartArea.bottom + 8)
      ctx.stroke(); ctx.restore()
      // date label
      drawXDateLabel(ctx, chart.chartArea, xp, mcLabels[monthlyHoverIdx])
    },
  }
  monthlyChart = new Chart(monthlyCanvas.value, {
    type: 'bar',
    data: { labels: mcLabels, datasets: [{ data: mcData, backgroundColor: mcData.map(v => v >= 0 ? '#dc2626' : '#16a34a') }] },
    options: { responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { ticks: { callback: v => v + '%', font: { size: 10 } } } } },
    plugins: [monthlyCross],
  })

  monthlyTT = ensureTooltip(monthlyCanvas.value.parentElement, 'monthly-tooltip')
  const mcCanvas = monthlyCanvas.value
  mcCanvas.onmousemove = function(e) {
    if (!monthlyChart || !monthlyChart.scales) return
    const rect = mcCanvas.getBoundingClientRect()
    const mx = e.clientX - rect.left, my = e.clientY - rect.top
    const xs = monthlyChart.scales.x, ys = monthlyChart.scales.y
    if (mx < xs.left || mx > xs.right || my < ys.top || my > ys.bottom) {
      if (monthlyHoverIdx >= 0) { monthlyHoverIdx = -1; monthlyChart.draw() }
      monthlyTT.style.display = 'none'; return
    }
    const idx = Math.round(xs.getValueForPixel(mx))
    if (idx < 0 || idx >= mcData.length) return
    monthlyHoverIdx = idx
    const val = mcData[idx], cls = val >= 0 ? '#ef4444' : '#16a34a', sn = val >= 0 ? '+' : ''
    monthlyTT.innerHTML = `<div style="font-weight:600;margin-bottom:4px;color:#93c5fd">${mcLabels[idx]}</div><div>涨跌幅: <span style="color:${cls};font-weight:700">${sn}${val.toFixed(2)}%</span></div>`
    monthlyTT.style.display = 'block'
    const bw = monthlyTT.offsetWidth || 130, bh = monthlyTT.offsetHeight || 60
    let left = mx + 16, top = my - bh / 2
    if (left + bw > rect.width - 4) left = mx - bw - 16
    if (left < 4) left = 4; if (top < 4) top = 4
    if (top + bh > rect.height - 4) top = rect.height - bh - 4
    monthlyTT.style.left = left + 'px'; monthlyTT.style.top = top + 'px'
    monthlyChart.draw()
  }
  mcCanvas.onmouseleave = function() { monthlyTT.style.display = 'none'; monthlyHoverIdx = -1; monthlyChart.draw() }

  // ---- Monthly Zoom/Pan ----
  const monthlyTotal = mcLabels.length
  monthlyZoomState = { start: Math.max(0, monthlyTotal - 60), end: monthlyTotal }
  function applyMonthlyZoom() {
    const s = monthlyZoomState.start, e = monthlyZoomState.end
    if (monthlyChart) {
      monthlyChart.options.scales.x.min = s
      monthlyChart.options.scales.x.max = e - 1
      monthlyChart.update('none')
    }
    updateMonthlySlider()
  }
  applyMonthlyZoom()

  mcCanvas.onwheel = function(e) {
    e.preventDefault()
    const range = monthlyZoomState.end - monthlyZoomState.start
    if (e.ctrlKey || e.metaKey) {
      const zf = e.deltaY > 0 ? 1.25 : 0.8
      const center = (monthlyZoomState.start + monthlyZoomState.end) / 2
      const nr = Math.max(6, Math.min(monthlyTotal, Math.round(range * zf)))
      monthlyZoomState.start = Math.max(0, Math.round(center - nr / 2))
      monthlyZoomState.end = Math.min(monthlyTotal, monthlyZoomState.start + nr)
    } else {
      const shift = Math.max(1, Math.round(range * 0.15))
      if (e.deltaY > 0) { monthlyZoomState.start = Math.min(monthlyTotal - 6, monthlyZoomState.start + shift); monthlyZoomState.end = Math.min(monthlyTotal, monthlyZoomState.end + shift) }
      else { monthlyZoomState.start = Math.max(0, monthlyZoomState.start - shift); monthlyZoomState.end = Math.max(6, monthlyZoomState.end - shift) }
    }
    applyMonthlyZoom()
  }

  buildMonthlySlider()

  function updateMonthlySlider() {
    if (!mSliderHandle.value) return
    const total = monthlyTotal
    const pStart = monthlyZoomState.start / total * 100
    const pEnd = monthlyZoomState.end / total * 100
    mSliderHandle.value.style.left = pStart + '%'
    mSliderHandle.value.style.width = (pEnd - pStart) + '%'
    mSliderLKnob.value.style.left = pStart + '%'
    mSliderRKnob.value.style.left = pEnd + '%'
  }
  function updateMonthlyFromSlider(x) {
    const wrap = mSliderWrap.value
    const rect = wrap.getBoundingClientRect()
    const w = rect.width || 1
    const pct = Math.max(0, Math.min(1, (x - rect.left) / w))
    const range = monthlyZoomState.end - monthlyZoomState.start
    if (mDragMode === 'pan') {
      const center = Math.round(pct * monthlyTotal)
      monthlyZoomState.start = Math.max(0, Math.min(monthlyTotal - range, center - Math.round(range / 2)))
      monthlyZoomState.end = monthlyZoomState.start + range
    } else if (mDragMode === 'left') {
      const ns = Math.round(pct * monthlyTotal)
      monthlyZoomState.start = Math.max(0, Math.min(monthlyZoomState.end - 6, ns))
    } else if (mDragMode === 'right') {
      const ne = Math.round(pct * monthlyTotal)
      monthlyZoomState.end = Math.min(monthlyTotal, Math.max(monthlyZoomState.start + 6, ne))
    }
    applyMonthlyZoom()
    updateMonthlySlider()
  }
  let mDragMode = null
  function buildMonthlySlider() {
    const wrap = mSliderWrap.value
    if (!wrap) return
    if (mSliderStartDate.value) mSliderStartDate.value.textContent = mcLabels[0] || ''
    if (mSliderEndDate.value) mSliderEndDate.value.textContent = mcLabels[monthlyTotal - 1] || ''
    wrap.onmousedown = e => { mDragMode = 'pan'; e.preventDefault() }
    mSliderLKnob.value.onmousedown = e => { mDragMode = 'left'; e.stopPropagation(); e.preventDefault() }
    mSliderRKnob.value.onmousedown = e => { mDragMode = 'right'; e.stopPropagation(); e.preventDefault() }
    wrap.ontouchstart = function() { mDragMode = 'pan' }
    updateMonthlySlider()
  }

  // Shared slider document handlers (supports both K-line & monthly sliders)
  const sGetX = e => e.touches ? e.touches[0].clientX : e.clientX
  document.onmousemove = function(e) {
    const x = sGetX(e)
    if (dragMode) updateFromSlider(x)
    if (mDragMode) updateMonthlyFromSlider(x)
  }
  document.onmouseup = function() { dragMode = null; mDragMode = null }
  document.ontouchmove = function(e) {
    const x = sGetX(e)
    if (dragMode) updateFromSlider(x)
    if (mDragMode) updateMonthlyFromSlider(x)
  }
  document.ontouchend = function() { dragMode = null; mDragMode = null }

  // ---- Monthly stats default: current year ----
  const now = new Date()
  mcStart.value = now.getFullYear() + '-01-01'
  mcEnd.value = now.getFullYear() + '-12-31'
  mcStats.value = computeMonthlyStats(mcSorted, mcStart.value, mcEnd.value)

  // ---- Seasonal ----
  if (seasonalChart) seasonalChart.destroy()
  seasonalChart = new Chart(seasonalCanvas.value, {
    type: 'bar',
    data: { labels: ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'], datasets: [{ data: sea, backgroundColor: sea.map(v => v >= 0 ? '#dc2626' : '#16a34a') }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => v + '%' } } } },
  })

  // ---- K-line mouse events (tooltip + crosshair) ----
  const kCanvas = klineCanvas.value
  let lastCrossIdx = -1
  kCanvas.onmousemove = function(e) {
    if (!klineChart || !klineChart.scales) return
    const rect = kCanvas.getBoundingClientRect()
    const mx = e.clientX - rect.left, my = e.clientY - rect.top
    const xs = klineChart.scales.x, ys = klineChart.scales.y
    if (mx < xs.left || mx > xs.right || my < ys.top || my > ys.bottom) {
      if (lastCrossIdx !== -1) { klineTT.style.display = 'none'; crossX = -1; crossIdx = -1; lastCrossIdx = -1; klineChart.draw(); if (dyChart) dyChart.draw() }
      return
    }
    const idx = Math.round(xs.getValueForPixel(mx)) + zoomState.start
    if (idx < 0 || idx >= klineBars.length) { klineTT.style.display = 'none'; return }
    if (idx === lastCrossIdx) return
    lastCrossIdx = idx
    crossX = xs.getPixelForValue(idx - zoomState.start)
    crossIdx = idx
    const bar = klineBars[idx]
    const prevBar = klineBars[idx > 0 ? idx - 1 : 0]
    const chg = prevBar ? ((bar.close - prevBar.close) / prevBar.close * 100) : 0
    const cls = chg >= 0 ? '#ef4444' : '#16a34a', sn = chg >= 0 ? '+' : ''

    let html = `<div style="font-weight:600;margin-bottom:4px;color:#93c5fd">${bar.date}</div>`
    html += `<div>开:<span>${fmt(bar.open)}</span></div>`
    html += `<div>收:<span style="color:${cls}">${fmt(bar.close)}</span></div>`
    html += `<div>高:<span style="color:#ef4444">${fmt(bar.high)}</span></div>`
    html += `<div>低:<span style="color:#16a34a">${fmt(bar.low)}</span></div>`
    html += `<div style="margin-top:3px;border-top:1px solid rgba(255,255,255,.15);padding-top:3px;color:${cls}">涨跌: ${sn}${fmt(chg)}%</div>`
    if (bar.dividend) {
      html += `<div style="margin-top:6px;border-top:2px solid #f59e0b;padding-top:5px;font-size:13px;line-height:1.8"><span style="color:#fbbf24">▼ 除权除息</span>`
      html += `<div>到账: <span style="color:#34d399;font-weight:700">${fmt(bar.dividend.amount)}</span> 元</div>`
      html += `<div>每股分红: <span style="color:#60a5fa;font-weight:700">${fmt(bar.dividend.per_share || 0)}</span> 元</div></div>`
    }
    // Show pattern info in tooltip
    if (patternScanResult) {
      const allP = (patternScanResult.bullish || []).concat(patternScanResult.bearish || [])
      const hits = allP.filter(p => p.idx === idx)
      if (hits.length) {
        html += `<div style="margin-top:6px;border-top:1px solid #6b7280;padding-top:5px;">`
        hits.forEach(p => {
          const icon = p.direction === 'bullish' ? '🟡' : '🟣'
          const nameColor = p.direction === 'bullish' ? '#f59e0b' : '#a78bfa'
          html += `<div style="line-height:1.6">${icon} <span style="color:${nameColor}">${p.name}</span> <span style="font-size:10px;color:#9ca3af">${'★'.repeat(p.strength)}</span></div>`
        })
        html += `</div>`
      }
    }
    klineTT.innerHTML = html; klineTT.style.display = 'block'
    const bw = klineTT.offsetWidth || 130, bh = klineTT.offsetHeight || 120
    let left = mx + 16, top = my - bh / 2
    if (left + bw > rect.width - 4) left = mx - bw - 16
    if (left < 4) left = 4; if (top < 4) top = 4
    if (top + bh > rect.height - 4) top = rect.height - bh - 4
    klineTT.style.left = left + 'px'; klineTT.style.top = top + 'px'
    klineChart.draw(); if (dyChart) dyChart.draw()
  }
  kCanvas.onmouseleave = function() { klineTT.style.display = 'none'; if (dyTT) dyTT.style.display = 'none'; crossX = -1; crossIdx = -1; klineChart.draw(); if (dyChart) dyChart.draw() }

  // ---- Zoom/Pan ----
  const totalBars = labels.length
  const currentYear = new Date().getFullYear() + '-'
  const yearStartIdx = labels.findIndex(l => l.startsWith(currentYear))
  zoomState = { start: yearStartIdx >= 0 ? yearStartIdx : Math.max(0, totalBars - 120), end: totalBars }
  function applyZoom() {
    const s = zoomState.start, e = zoomState.end
    if (klineChart) {
      // Re-index visible data so bar width scales with zoom
      klineChart.data.datasets[0].data = candleData.slice(s, e).map((d, i) => ({ ...d, x: i }))
      klineChart.data.datasets[1].data = sma20.slice(s, e).map((v, i) => ({ x: i, y: v }))
      klineChart.data.datasets[2].data = sma60.slice(s, e).map((v, i) => ({ x: i, y: v }))
      let dsIdx = 3
      if (klineChart.data.datasets[3]) {
        const divSlice = []
        for (let i = s; i < e; i++) { if (divLookup[labels[i]]) divSlice.push({ x: i - s, y: closes[i] }) }
        klineChart.data.datasets[3].data = divSlice
        dsIdx = 4
      }
      klineChart.options.scales.x.ticks.callback = function(v) { return labels[Math.round(v) + s] || '' }

      klineChart.options.scales.x.min = -0.5
      klineChart.options.scales.x.max = e - s - 0.5
      klineChart.update('none')
    }
    if (dyChart) {
      dyChart.options.scales.x.min = s - 0.5
      dyChart.options.scales.x.max = e - 0.5
      dyChart.update('none')
    }
  }

  applyZoom()

  // Pattern markers drawn in crossPlugin.afterDraw (inside chartArea)

  kCanvas.onwheel = function(e) {
    e.preventDefault()
    const range = zoomState.end - zoomState.start
    if (e.ctrlKey || e.metaKey) {
      const zf = e.deltaY > 0 ? 1.25 : 0.8
      const center = (zoomState.start + zoomState.end) / 2
      const nr = Math.max(15, Math.min(totalBars, Math.round(range * zf)))
      zoomState.start = Math.max(0, Math.round(center - nr / 2))
      zoomState.end = Math.min(totalBars, zoomState.start + nr)
    } else {
      const shift = Math.max(1, Math.round(range * 0.12))
      if (e.deltaY > 0) { zoomState.start = Math.min(totalBars - 15, zoomState.start + shift); zoomState.end = Math.min(totalBars, zoomState.end + shift) }
      else { zoomState.start = Math.max(0, zoomState.start - shift); zoomState.end = Math.max(15, zoomState.end - shift) }
    }
    applyZoom()
  }

  // ---- Slider ----
  buildSlider()

  function updateSlider() {
    if (!sliderHandle.value) return
    const total = totalBars
    const pStart = zoomState.start / total * 100
    const pEnd = zoomState.end / total * 100
    sliderHandle.value.style.left = pStart + '%'
    sliderHandle.value.style.width = (pEnd - pStart) + '%'
    sliderLKnob.value.style.left = pStart + '%'
    sliderRKnob.value.style.left = pEnd + '%'
  }

  function updateFromSlider(x) {
    const wrap = sliderWrap.value
    const rect = wrap.getBoundingClientRect()
    const w = rect.width || 1
    const pct = Math.max(0, Math.min(1, (x - rect.left) / w))
    const range = zoomState.end - zoomState.start

    if (dragMode === 'pan') {
      const center = Math.round(pct * totalBars)
      zoomState.start = Math.max(0, Math.min(totalBars - range, center - Math.round(range / 2)))
      zoomState.end = zoomState.start + range
    } else if (dragMode === 'left') {
      const ns = Math.round(pct * totalBars)
      zoomState.start = Math.max(0, Math.min(zoomState.end - 5, ns))
    } else if (dragMode === 'right') {
      const ne = Math.round(pct * totalBars)
      zoomState.end = Math.min(totalBars, Math.max(zoomState.start + 5, ne))
    }
    applyZoom()
    updateSlider()
  }

  let dragMode = null

  function buildSlider() {
    const wrap = sliderWrap.value
    if (!wrap) return
    if (sliderStartDate.value) sliderStartDate.value.textContent = labels[0] || ''
    if (sliderEndDate.value) sliderEndDate.value.textContent = labels[totalBars - 1] || ''

    wrap.onmousedown = function(e) { dragMode = 'pan'; e.preventDefault() }
    sliderLKnob.value.onmousedown = e => { dragMode = 'left'; e.stopPropagation(); e.preventDefault() }
    sliderRKnob.value.onmousedown = e => { dragMode = 'right'; e.stopPropagation(); e.preventDefault() }
    wrap.ontouchstart = function() { dragMode = 'pan' }

    updateSlider()
  }

  // ---- Dividend yield ----
  if (dyChart) dyChart.destroy()
  const dyCtx = dyCanvas.value
  dyTT = ensureTooltip(dyCtx.parentElement, 'dy-tooltip')

  apiCall('GET', '/api/v2/dividend-yield-series?code=' + code).then(resp => {
    if (!resp?.success) return
    const ds = resp.data
    const dyLabels = ds.labels || [], dySeries = ds.dy_series || [], dyEvents = ds.dividend_events || [], dyCloses = ds.close_prices || []
    const hasDivs = dyEvents.length > 0

    // Build dividend event points using ex_date
    const dyExLookup = {}
    dyEvents.forEach(e => { dyExLookup[e.ex_date] = e })
    const dyEventPts = dyLabels.map((d, i) => {
      const ev = dyExLookup[d]
      if (!ev) return null
      // Use dy value at this index, or search left/right for nearest
      let val = dySeries[i]
      if (val == null) {
        for (let l = i - 1; l >= 0; l--) { if (dySeries[l] != null) { val = dySeries[l]; break } }
      }
      if (val == null) {
        for (let r = i + 1; r < dySeries.length; r++) { if (dySeries[r] != null) { val = dySeries[r]; break } }
      }
      return val
    })

    // Convert dy data to global-index-based x values for linear axis alignment with kline chart
    const dyDataPts = dySeries.map((v, i) => ({ x: i, y: v }))
    const dyDivScatter = dyEvents
      .map(e => {
        const xi = dyLabels.indexOf(e.ex_date || e.date)
        if (xi < 0) return null
        const yv = dySeries[xi] != null ? dySeries[xi] : dySeries[Math.min(xi + 1, dySeries.length - 1)]
        return { x: xi, y: yv }
      })
      .filter(Boolean)

    dyChart = new Chart(dyCtx, {
      type: 'line',
      data: {
        datasets: [
          { label: '股息率(TTM推算)', data: dyDataPts, borderColor: '#dc2626', borderWidth: 2, pointRadius: 0, tension: 0, fill: false, spanGaps: false },
          ...(dyDivScatter.length ? [{ label: '分红除权日 ▼', data: dyDivScatter, borderColor: '#dc2626', backgroundColor: '#dc2626', pointRadius: 7, pointStyle: 'triangle', showLine: false }] : []),
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11 } } }, tooltip: { enabled: false } },
        scales: {
          x: { type: 'linear', ticks: { callback: function(v) { return klineLabels[Math.round(v)] || '' }, font: { size: 9 }, autoSkipPadding: 1 }, min: zoomState.start - 0.5, max: zoomState.end - 0.5 },
          y: { ticks: { callback: v => v.toFixed(1) + '%', font: { size: 10 } }, title: { display: true, text: '%', font: { size: 10 } } },
        },
      },
      plugins: [{ id: 'dyCross', afterDraw: function(chart) { if (crossX < 0 || crossIdx < 0) return; const ctx = chart.ctx, ra = chart.scales.y, ca = chart.chartArea; ctx.save(); ctx.setLineDash([4, 3]); ctx.strokeStyle = 'rgba(220,38,38,.25)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(crossX, ra.top); ctx.lineTo(crossX, ra.bottom); ctx.stroke(); ctx.restore(); drawXDateLabel(ctx, ca, crossX, klineLabels[crossIdx]) } }],
    })

    // Sync visible range with kline chart (same -0.5/+0.5 padding)
    const vs = zoomState.start, ve = zoomState.end
    dyChart.options.scales.x.min = vs - 0.5
    dyChart.options.scales.x.max = ve - 0.5
    dyChart.update('none')

    // Dy tooltip
    dyCtx.onmousemove = function(e) {
      if (!dyChart || !dyChart.scales) return
      const rect = dyCtx.getBoundingClientRect()
      const mx = e.clientX - rect.left, my = e.clientY - rect.top
      const xs = dyChart.scales.x, ys = dyChart.scales.y
      if (mx < xs.left || mx > xs.right || my < ys.top || my > ys.bottom) { dyTT.style.display = 'none'; return }
      const idx = Math.round(xs.getValueForPixel(mx))
      if (idx < 0 || idx >= dyLabels.length) { dyTT.style.display = 'none'; return }
      const date = dyLabels[idx], dyVal = dySeries[idx], closePr = dyCloses[idx]
      const dv = dyExLookup[date]

      if (klineChart && klineChart.scales) {
        if (idx >= 0 && idx < klineLabels.length && idx >= zoomState.start && idx < zoomState.end) { crossIdx = idx; crossX = klineChart.scales.x.getPixelForValue(idx - zoomState.start); klineChart.draw(); dyChart.draw() }
      }
      let html = `<div style="font-weight:600;margin-bottom:4px;color:#fbbf24">${date}</div><div>股息率(TTM推算): <span style="color:#f87171;font-weight:700">${dyVal != null ? dyVal.toFixed(2) + '%' : '--'}</span></div><div>收盘价: <span style="color:#93c5fd">${fmt(closePr)}</span></div><div style="font-size:10px;color:#9ca3af">公式计算值 · 可能与实际公布值存在差异</div>`
      if (dv) {
        html += `<div style="margin-top:5px;border-top:2px solid #dc2626;padding-top:5px"><span style="color:#f87171">▼ 分红除权日</span><div>每股: <span style="color:#60a5fa;font-weight:700">${fmt(dv.per_share || 0)}</span> 元</div></div>`
      }
      dyTT.innerHTML = html; dyTT.style.display = 'block'
      const bw = dyTT.offsetWidth || 150, bh = dyTT.offsetHeight || 100
      let left = mx + 16, top = my - bh / 2
      if (left + bw > rect.width - 4) left = mx - bw - 16
      if (left < 4) left = 4; if (top < 4) top = 4
      if (top + bh > rect.height - 4) top = rect.height - bh - 4
      dyTT.style.left = left + 'px'; dyTT.style.top = top + 'px'
    }
    dyCtx.onmouseleave = function() { dyTT.style.display = 'none'; crossX = -1; crossIdx = -1; if (klineChart) klineChart.draw(); dyChart.draw() }

    if (dyHint.value) {
      const latestDy = [...dySeries].reverse().find(v => v != null)
      dyHint.value.textContent = '滚轮平移 ｜ Ctrl+滚轮缩放 ｜ 公式计算值(TTM推算)' + (hasDivs ? ' ｜ ▼ = 分红除权日' : '') + (latestDy != null ? ' ｜ 当前: ' + latestDy.toFixed(2) + '%' : '')
    }
  })
}

onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  activeCode.value = data.watchlist[0]?.code || ''
  await nextTick()
  renderAll()
})
watch(activeCode, async () => { await nextTick(); renderAll() })

// Recompute monthly stats when date range changes
watch([mcStart, mcEnd], () => {
  if (!mcSorted) return
  mcStats.value = computeMonthlyStats(mcSorted, mcStart.value, mcEnd.value)
})
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.chart-wrap { position: relative; }
.chart-dy-wrap { border-top: 1px solid #e5e7eb; padding-top: 4px; }
.chart-hint { font-size: 11px; color: #9ca3af; text-align: center; padding: 4px 0 0; }
.monthly-filter { display: flex; align-items: center; gap: 6px; padding: 6px 0 4px; flex-wrap: wrap; }
.mc-date-input { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-size: 12px; outline: none; }
.mc-date-input:focus { border-color: #3b82f6; }
.mc-date-sep { color: #9ca3af; font-size: 12px; }
.mc-stats { display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; font-size: 12px; color: #cbd5e1; background: #1e293b; border-radius: 6px; padding: 4px 10px; }
.mc-stat-item { white-space: nowrap; }
.mc-stat-sep { color: #475569; }
.slider-wrap { position: relative; height: 40px; margin: 6px 0 0; background: #f3f4f6; border-radius: 4px; cursor: pointer; user-select: none; overflow: hidden; }
.slider-bar { position: absolute; inset: 0; }
.slider-handle { position: absolute; top: 0; bottom: 0; background: rgba(37,99,235,.25); border: 2px solid #2563eb; border-radius: 4px; pointer-events: none; z-index: 1; }
.slider-knob { position: absolute; top: 0; bottom: 0; width: 6px; background: #2563eb; cursor: ew-resize; z-index: 2; }
.slider-lknob { border-radius: 3px 0 0 3px; }
.slider-rknob { border-radius: 0 3px 3px 0; }
.slider-hint { position: absolute; bottom: -16px; left: 0; right: 0; display: flex; justify-content: space-between; font-size: 10px; color: #9ca3af; padding: 0 2px; }
</style>
