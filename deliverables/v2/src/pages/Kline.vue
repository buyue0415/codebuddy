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
          <div class="chart-wrap" style="height:300px"><canvas ref="monthlyCanvas"></canvas></div>
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

let klineChart = null, dyChart = null, monthlyChart = null, seasonalChart = null
let klineBars = [], klineLabels = [], crossX = null
let klineTT = null, dyTT = null
let zoomState = null

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

  // Candle data for candlestick chart (pre-computed colors)
  const candleData = kline.map((k, i) => {
    const o = k[1], c = k.length === 5 ? k[2] : k[4], h = k.length === 5 ? k[3] : k[2], l = k.length === 5 ? k[4] : k[3]
    const up = c >= o
    return { x: i, o, h, l, c, backgroundColor: up ? 'rgba(239,68,68,0.5)' : 'rgba(22,163,74,0.5)', borderColor: up ? '#ef4444' : '#16a34a' }
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

  const crossPlugin = {
    id: 'klineCross',
    afterDraw: function(chart) {
      if (!crossX) return
      const ctx = chart.ctx, ra = chart.scales.y
      ctx.save(); ctx.setLineDash([4, 3])
      ctx.strokeStyle = 'rgba(100,100,255,.35)'; ctx.lineWidth = 1
      ctx.beginPath(); ctx.moveTo(crossX, ra.top); ctx.lineTo(crossX, ra.bottom)
      ctx.stroke(); ctx.restore()
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
              { label: '日K线', data: candleData, backgroundColor: '#999', borderColor: '#666', borderWidth: 1 },
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
              x: { type: 'linear', ticks: { callback: function(v) { return labels[Math.round(v)] || '' }, maxTicksLimit: 12, font: { size: 10 } } },
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

  // ---- Monthly ----
  if (monthlyChart) monthlyChart.destroy()
  const mcSorted = mc.slice().reverse()
  monthlyChart = new Chart(monthlyCanvas.value, {
    type: 'bar',
    data: { labels: mcSorted.map(m => m[0]), datasets: [{ data: mcSorted.map(m => m[1]), backgroundColor: mcSorted.map(m => m[1] >= 0 ? '#dc2626' : '#16a34a') }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { ticks: { callback: v => v + '%', font: { size: 10 } } } } },
  })

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
      if (lastCrossIdx !== -1) { klineTT.style.display = 'none'; crossX = null; lastCrossIdx = -1; klineChart.draw(); if (dyChart) dyChart.draw() }
      return
    }
    const idx = Math.round(xs.getValueForPixel(mx)) + zoomState.start
    if (idx < 0 || idx >= klineBars.length) { klineTT.style.display = 'none'; return }
    if (idx === lastCrossIdx) return
    lastCrossIdx = idx
    const bar = klineBars[idx]
    const prevBar = klineBars[idx > 0 ? idx - 1 : 0]
    const chg = prevBar ? ((bar.close - prevBar.close) / prevBar.close * 100) : 0
    const cls = chg >= 0 ? '#ef4444' : '#16a34a', sn = chg >= 0 ? '+' : ''
    crossX = xs.getPixelForValue(idx - zoomState.start)

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
    klineTT.innerHTML = html; klineTT.style.display = 'block'
    const bw = klineTT.offsetWidth || 130, bh = klineTT.offsetHeight || 120
    let left = mx + 16, top = my - bh / 2
    if (left + bw > rect.width - 4) left = mx - bw - 16
    if (left < 4) left = 4; if (top < 4) top = 4
    if (top + bh > rect.height - 4) top = rect.height - bh - 4
    klineTT.style.left = left + 'px'; klineTT.style.top = top + 'px'
    klineChart.draw(); if (dyChart) dyChart.draw()
  }
  kCanvas.onmouseleave = function() { klineTT.style.display = 'none'; if (dyTT) dyTT.style.display = 'none'; crossX = null; klineChart.draw(); if (dyChart) dyChart.draw() }

  // ---- Zoom/Pan ----
  const totalBars = labels.length
  zoomState = { start: Math.max(0, totalBars - 120), end: totalBars }
  function applyZoom() {
    const s = zoomState.start, e = zoomState.end
    if (klineChart) {
      // Re-index visible data so bar width scales with zoom
      klineChart.data.datasets[0].data = candleData.slice(s, e).map((d, i) => ({ ...d, x: i }))
      klineChart.data.datasets[1].data = sma20.slice(s, e).map((v, i) => ({ x: i, y: v }))
      klineChart.data.datasets[2].data = sma60.slice(s, e).map((v, i) => ({ x: i, y: v }))
      if (klineChart.data.datasets[3]) {
        const divSlice = []
        for (let i = s; i < e; i++) { if (divLookup[labels[i]]) divSlice.push({ x: i - s, y: closes[i] }) }
        klineChart.data.datasets[3].data = divSlice
      }
      klineChart.options.scales.x.ticks.callback = function(v) { return labels[Math.round(v) + s] || '' }
      klineChart.options.scales.x.min = -0.5
      klineChart.options.scales.x.max = e - s - 0.5
      klineChart.update('none')
    }
    if (dyChart) { dyChart.options.scales.x.min = s; dyChart.options.scales.x.max = e - 1; dyChart.update('none') }
  }
  applyZoom()

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

    const getX = e => e.touches ? e.touches[0].clientX : e.clientX

    wrap.onmousedown = e => { dragMode = 'pan'; e.preventDefault() }
    sliderLKnob.value.onmousedown = e => { dragMode = 'left'; e.stopPropagation(); e.preventDefault() }
    sliderRKnob.value.onmousedown = e => { dragMode = 'right'; e.stopPropagation(); e.preventDefault() }

    document.onmousemove = e => { if (dragMode) updateFromSlider(getX(e)) }
    document.onmouseup = () => { dragMode = null }
    wrap.ontouchstart = e => { dragMode = 'pan' }
    document.ontouchmove = e => { if (dragMode) updateFromSlider(getX(e)) }
    document.ontouchend = () => { dragMode = null }

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

    const dyDivLookup = {}
    dyEvents.forEach(e => { dyDivLookup[e.date] = e })
    const dyEventPts = dyLabels.map((d, i) => dyDivLookup[d] && dySeries[i] != null ? dySeries[i] : null)

    dyChart = new Chart(dyCtx, {
      type: 'line',
      data: {
        labels: dyLabels,
        datasets: [
          { label: '股息率(TTM推算)', data: dySeries, borderColor: '#dc2626', borderWidth: 2, pointRadius: 0, tension: 0, fill: false },
          ...(hasDivs ? [{ label: '分红除权日 ▼', data: dyEventPts, borderColor: '#dc2626', backgroundColor: '#dc2626', pointRadius: 7, pointStyle: 'triangle', showLine: false }] : []),
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11 } } }, tooltip: { enabled: false } },
        scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { ticks: { callback: v => v.toFixed(1) + '%', font: { size: 10 } }, title: { display: true, text: '%', font: { size: 10 } } } },
      },
      plugins: [{ id: 'dyCross', afterDraw: function(chart) { if (!crossX) return; const ctx = chart.ctx, ra = chart.scales.y; ctx.save(); ctx.setLineDash([4, 3]); ctx.strokeStyle = 'rgba(220,38,38,.25)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(crossX, ra.top); ctx.lineTo(crossX, ra.bottom); ctx.stroke(); ctx.restore() } }],
    })

    // Sync apply zoom
    dyChart.options.scales.x.min = zoomState.start
    dyChart.options.scales.x.max = zoomState.end - 1
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
      const dv = dyDivLookup[date]

      if (klineChart && klineChart.scales) {
        const kxs = klineChart.scales.x
        const ki = klineLabels.indexOf(date)
        if (ki >= zoomState.start && ki < zoomState.end) { crossX = kxs.getPixelForValue(ki - zoomState.start); klineChart.draw(); dyChart.draw() }
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
    dyCtx.onmouseleave = function() { dyTT.style.display = 'none' }

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
</script>

<style scoped>
.page-content { max-width: 1200px; margin: 0 auto; }
.loading { text-align: center; padding: 60px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.chart-wrap { position: relative; }
.chart-dy-wrap { border-top: 1px solid #e5e7eb; padding-top: 4px; }
.chart-hint { font-size: 11px; color: #9ca3af; text-align: center; padding: 4px 0 0; }
.slider-wrap { position: relative; height: 40px; margin: 6px 0 0; background: #f3f4f6; border-radius: 4px; cursor: pointer; user-select: none; overflow: hidden; }
.slider-bar { position: absolute; inset: 0; }
.slider-handle { position: absolute; top: 0; bottom: 0; background: rgba(37,99,235,.25); border: 2px solid #2563eb; border-radius: 4px; pointer-events: none; z-index: 1; }
.slider-knob { position: absolute; top: 0; bottom: 0; width: 6px; background: #2563eb; cursor: ew-resize; z-index: 2; }
.slider-lknob { border-radius: 3px 0 0 3px; }
.slider-rknob { border-radius: 0 3px 3px 0; }
.slider-hint { position: absolute; bottom: -16px; left: 0; right: 0; display: flex; justify-content: space-between; font-size: 10px; color: #9ca3af; padding: 0 2px; }
</style>
