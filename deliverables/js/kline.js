function renderKline(code){
const D=DATA, klineRaw=D.kline_daily&&D.kline_daily[code]||D.kline&&D.kline[code]||[], divs=D['dividends_'+code]||[], mc=D['monthly_changes_'+code]||[];
const kline=klineRaw.slice().reverse();

const name=getStockName(code);

document.getElementById('kline-title').textContent=name+' 日K走势';
document.getElementById('monthly-title').textContent=name+' 月度涨跌幅';

const labels=kline.map(k=>k[0]);
const closes=kline.map(k=>k.length===5?k[2]:k[4]);
const sma20=calcSMA(closes,7);
const sma60=calcSMA(closes,14);

// Build dividend lookup map: date -> {amount, price}
const divLookup = {};
divs.forEach(function(d){ divLookup[d.date] = d; });

const divPoints=closes.map(function(c,i){
  // Exact date match: mark the precise trading day where dividend was paid
  return divLookup[labels[i]] ? c : null;
});

// Store bars for OHLC tooltip + dividend info
var klineBars=kline.map(function(k){
  var bar={date:k[0],open:k[1],close:k.length===5?k[2]:k[4],high:k.length===5?k[3]:k[2],low:k.length===5?k[4]:k[3]};
  var dv=divLookup[k[0]];
  if(dv){ bar.dividend={amount:dv.amount, price:dv.price, per_share:dv.per_share||0}; }
  return bar;
});

// Tooltip element
var klineCanvas=document.getElementById('klineChart');
var klineTT=document.getElementById('kline-tooltip');
if(!klineCanvas||!klineCanvas.parentElement) return;
if(!klineTT){
 klineTT=document.createElement('div');klineTT.id='kline-tooltip';
 klineTT.style.cssText='position:absolute;pointer-events:none;background:rgba(0,0,0,.85);color:#fff;padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.7;z-index:200;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.3);display:none;font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif';
 klineCanvas.parentElement.appendChild(klineTT);
}
var onKlineMove=function(e){
 var chart=klineChartInst;if(!chart||!chart.scales) return;
 var rect=klineCanvas.getBoundingClientRect();
 var mx=e.clientX-rect.left, my=e.clientY-rect.top;
 var xs=chart.scales.x, ys=chart.scales.y;
 if(mx<xs.left||mx>xs.right||my<ys.top||my>ys.bottom){klineTT.style.display='none';window._klineCrossX=null;if(klineChartInst)klineChartInst.draw();return;}
 var idx=Math.round(xs.getValueForPixel(mx));
 if(idx<0||idx>=klineBars.length){klineTT.style.display='none';return;}
 var bar=klineBars[idx];
 var prevBar=klineBars[idx>0?idx-1:0];
 var chg=prevBar?((bar.close-prevBar.close)/prevBar.close*100):0;
 var cls=chg>=0?'#ef4444':'#16a34a',sn=chg>=0?'+':'';
 var dotX=xs.getPixelForValue(idx);
 klineTT.innerHTML='<div style=\"font-weight:600;margin-bottom:4px;color:#93c5fd\">'+bar.date+'</div><div>开:<span>'+fmt(bar.open)+'</span></div><div>收:<span style=\"color:'+cls+'\">'+fmt(bar.close)+'</span></div><div>高:<span style=\"color:#ef4444\">'+fmt(bar.high)+'</span></div><div>低:<span style=\"color:#16a34a\">'+fmt(bar.low)+'</span></div><div style=\"margin-top:3px;border-top:1px solid rgba(255,255,255,.15);padding-top:3px;color:'+cls+'\">涨跌: '+sn+fmt(chg)+'%</div>'+(bar.dividend?'<div style=\"margin-top:6px;border-top:2px solid #f59e0b;padding-top:5px;font-size:13px;line-height:1.8\"><span style=\"color:#fbbf24\">▼ 除权除息</span><div>到账: <span style=\"color:#34d399;font-weight:700\">'+fmt(bar.dividend.amount)+'</span> 元</div><div>每股分红: <span style=\"color:#60a5fa;font-weight:700\">'+fmt(bar.dividend.per_share||0)+'</span> 元</div></div>':'');
 klineTT.style.display='block';
 var bw=klineTT.offsetWidth||130,bh=klineTT.offsetHeight||120;
 var left=mx+16,top=my-bh/2;
 if(left+bw>rect.width-4)left=mx-bw-16;if(left<4)left=4;if(top<4)top=4;if(top+bh>rect.height-4)top=rect.height-bh-4;
 klineTT.style.left=left+'px';klineTT.style.top=top+'px';
 window._klineCrossX=dotX;klineChartInst.draw();
 if(dividendYieldChartInst)dividendYieldChartInst.draw();
};
if(window._klineMoveFn)klineCanvas.removeEventListener('mousemove',window._klineMoveFn);
if(window._klineLeaveFn)klineCanvas.removeEventListener('mouseleave',window._klineLeaveFn);
window._klineMoveFn=onKlineMove;
window._klineLeaveFn=function(){klineTT.style.display='none';var dyT=document.getElementById('dy-tooltip');if(dyT)dyT.style.display='none';window._klineCrossX=null;if(klineChartInst)klineChartInst.draw();if(dividendYieldChartInst)dividendYieldChartInst.draw();};
klineCanvas.addEventListener('mousemove',onKlineMove);
klineCanvas.addEventListener('mouseleave',window._klineLeaveFn);

// Crosshair
var klineXPlugin={id:'klineX',afterDraw:function(chart){if(!window._klineCrossX)return;var ctx=chart.ctx,ra=chart.scales.y;ctx.save();ctx.setLineDash([4,3]);ctx.strokeStyle='rgba(100,100,255,.35)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(window._klineCrossX,ra.top);ctx.lineTo(window._klineCrossX,ra.bottom);ctx.stroke();ctx.restore();}};

if(klineChartInst)klineChartInst.destroy();
try{klineChartInst=new Chart(klineCanvas,{
type:'line',
data:{labels,datasets:[
{label:'收盘价',data:closes,borderColor:'#2563eb',borderWidth:2,pointRadius:1,tension:.3,fill:false},
{label:'SMA20',data:sma20,borderColor:'#f59e0b',borderWidth:1,pointRadius:0,borderDash:[4,2],fill:false},
{label:'SMA60',data:sma60,borderColor:'#ef4444',borderWidth:1,pointRadius:0,borderDash:[6,3],fill:false},
{label:'分红',data:divPoints,borderColor:'#dc2626',backgroundColor:'#dc2626',pointRadius:8,pointStyle:'triangle',showLine:false}
]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:11}}},tooltip:{enabled:false}},scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},y:{ticks:{font:{size:10}}}}},
plugins:[klineXPlugin]
});

}catch(e){console.warn('Kline chart:',e.message);}

// ── Click-to-enlarge system (all 4 charts) ──

// Store all chart configs
window._klineCharts = window._klineCharts || {};
window._klineCharts.kline = {
  code: code, name: name, type: 'kline',
  labels: labels, closes: closes, sma20: sma20, sma60: sma60,
  divPoints: divPoints, klineBars: klineBars, divLookup: divLookup
};
window._klineCharts.monthly = {
  code: code, name: name, type: 'monthly',
  mcData: mc
};
window._klineCharts.seasonal = {
  code: code, name: name, type: 'seasonal',
  seaData: DATA.seasonal[code] || []
};

// Add enlarge button & click handler to a chart canvas
function _addEnlargeButton(canvas, btnId, title, chartType) {
  var btn = document.getElementById(btnId);
  if (!btn) {
    btn = document.createElement('button');
    btn.id = btnId;
    btn.textContent = '⛶';
    btn.title = title;
    btn.style.cssText = 'position:absolute;top:8px;right:8px;z-index:50;background:rgba(0,0,0,.6);color:#fff;border:1px solid rgba(255,255,255,.15);border-radius:6px;padding:4px 8px;cursor:pointer;font-size:14px;line-height:1;opacity:.7;transition:opacity .2s';
    canvas.parentElement.style.position = 'relative';
    canvas.parentElement.appendChild(btn);
    btn.addEventListener('mouseenter', function(){this.style.opacity='1';});
    btn.addEventListener('mouseleave', function(){this.style.opacity='.7';});
  }
  btn.onclick = function(e) { e.stopPropagation(); openChartFullscreen(chartType); };

  // Click on canvas (pure click, no drag) opens fullscreen
  canvas.style.cursor = 'pointer';
  var _start = null;
  canvas.addEventListener('mousedown', function(e) { _start = {x: e.clientX, y: e.clientY}; });
  canvas.addEventListener('mouseup', function(e) {
    if (!_start) return;
    var dx = e.clientX - _start.x, dy = e.clientY - _start.y;
    if (Math.abs(dx) < 3 && Math.abs(dy) < 3) openChartFullscreen(chartType);
    _start = null;
  });
}

_addEnlargeButton(klineCanvas, 'kline-enlarge-btn', '放大日K线图', 'kline');
_addEnlargeButton(document.getElementById('monthlyChart'), 'monthly-enlarge-btn', '放大月度涨跌幅', 'monthly');
_addEnlargeButton(document.getElementById('seasonalChart'), 'seasonal-enlarge-btn', '放大季节性规律', 'seasonal');

// Titles per chart type
var _fsTitles = {
  kline: '日K走势',
  monthly: '月度涨跌幅',
  seasonal: '季节性规律（月均涨跌幅 %）',
  dy: '股息率走势 (TTM)'
};

function openChartFullscreen(type) {
  var cfg = window._klineCharts[type];
  if (!cfg) return;

  closeKlineFullscreen(false);

  var overlay = document.createElement('div');
  overlay.id = 'kline-fs-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.85);display:flex;flex-direction:column;align-items:center;justify-content:center;opacity:0;transition:opacity .3s ease';
  document.body.appendChild(overlay);

  var title = cfg.name + '(' + cfg.code + ') ' + (_fsTitles[type] || '');
  var header = document.createElement('div');
  header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;width:96%;max-width:96vw;padding:8px 16px;color:#fff;font-size:15px;font-weight:600';
  header.innerHTML = '<span>'+title+' — 全屏模式</span>' +
    '<button id="kline-fs-close" style="background:rgba(255,255,255,.1);color:#fff;border:1px solid rgba(255,255,255,.2);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:13px;transition:background .2s" onmouseenter="this.style.background=\'rgba(255,255,255,.2)\'" onmouseleave="this.style.background=\'rgba(255,255,255,.1)\'">✕ 关闭 (Esc)</button>';
  overlay.appendChild(header);

  var chartBox = document.createElement('div');
  chartBox.style.cssText = 'position:relative;width:96vw;height:80vh;margin:0 auto';
  var canvas = document.createElement('canvas');
  canvas.id = 'kline-fs-canvas';
  chartBox.appendChild(canvas);
  overlay.appendChild(chartBox);

  var hint = document.createElement('div');
  hint.style.cssText = 'color:rgba(255,255,255,.5);font-size:12px;text-align:center;padding:6px';
  hint.textContent = (type === 'kline' ? '滚轮平移 | Ctrl+滚轮缩放 | ' : '') + '点击背景关闭';
  overlay.appendChild(hint);

  requestAnimationFrame(function(){ overlay.style.opacity = '1'; });

  setTimeout(function(){
    canvas.style.width = '100%'; canvas.style.height = '100%';

    var fsTT = document.createElement('div');
    fsTT.id = 'kline-fs-tt';
    fsTT.style.cssText = 'position:absolute;pointer-events:none;background:rgba(0,0,0,.9);color:#fff;padding:12px 16px;border-radius:8px;font-size:13px;line-height:1.8;z-index:200;white-space:nowrap;box-shadow:0 2px 12px rgba(0,0,0,.5);display:none;font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif';
    chartBox.appendChild(fsTT);

    var fsChart = null, fsCrossX = null;
    var crossPlugin = {id:'fsCross',afterDraw:function(chart){
      if(!fsCrossX)return;var c=chart.ctx,ra=chart.scales.y;
      c.save();c.setLineDash([4,3]);c.strokeStyle='rgba(100,100,255,.35)';c.lineWidth=1;
      c.beginPath();c.moveTo(fsCrossX,ra.top);c.lineTo(fsCrossX,ra.bottom);c.stroke();c.restore();
    }};

    var chartConfig;
    if (type === 'kline') {
      chartConfig = {
        type: 'line',
        data: { labels: cfg.labels, datasets: [
          {label:'收盘价',data:cfg.closes,borderColor:'#2563eb',borderWidth:2,pointRadius:1,tension:.3,fill:false},
          {label:'SMA20',data:cfg.sma20,borderColor:'#f59e0b',borderWidth:1,pointRadius:0,borderDash:[4,2],fill:false},
          {label:'SMA60',data:cfg.sma60,borderColor:'#ef4444',borderWidth:1,pointRadius:0,borderDash:[6,3],fill:false},
          {label:'分红',data:cfg.divPoints,borderColor:'#dc2626',backgroundColor:'#dc2626',pointRadius:8,pointStyle:'triangle',showLine:false}
        ]},
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:13}}},tooltip:{enabled:false}},
          scales:{x:{ticks:{maxTicksLimit:20,font:{size:11}}},y:{ticks:{font:{size:11}}}}},
        plugins: [crossPlugin]
      };
    } else if (type === 'monthly') {
      var mcSorted = (cfg.mcData || []).slice().reverse();
      var mcLabels = mcSorted.map(function(m){return m[0];});
      var mcVals = mcSorted.map(function(m){return m[1];});
      var mcColors = mcVals.map(function(v){return v>=0?'#dc2626':'#16a34a';});
      chartConfig = {
        type: 'bar',
        data: { labels: mcLabels, datasets: [{label:'涨跌幅%',data:mcVals,backgroundColor:mcColors}]},
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{legend:{display:false}},
          scales:{x:{ticks:{maxTicksLimit:20,font:{size:11}}},y:{ticks:{callback:function(v){return v+'%';},font:{size:11}}}}}
      };
    } else if (type === 'seasonal') {
      var seaData = cfg.seaData || [];
      var seaLabels = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
      var seaColors = seaData.map(function(v){return v>=0?'#dc2626':'#16a34a';});
      chartConfig = {
        type: 'bar',
        data: { labels: seaLabels, datasets: [{label:'月均涨跌幅%',data:seaData,backgroundColor:seaColors}]},
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{legend:{display:false}},
          scales:{y:{ticks:{callback:function(v){return v+'%';},font:{size:12}},title:{display:true,text:'%',font:{size:12}}}}}
      };
    } else if (type === 'dy') {
      var dyLabels = cfg.labels || [];
      var dySeries = cfg.dySeries || [];
      var dyEventPts = cfg.dyEventPts || [];
      var hasDivs = cfg.hasDivs;
      chartConfig = {
        type: 'line',
        data: { labels: dyLabels, datasets: [
          {label:'股息率(TTM推算)',data:dySeries,borderColor:'#dc2626',backgroundColor:'transparent',fill:false,borderWidth:2,pointRadius:0,tension:0,spanGaps:false},
          hasDivs ? {label:'分红除权日',data:dyEventPts,borderColor:'#dc2626',backgroundColor:'#dc2626',pointRadius:8,pointStyle:'triangle',showLine:false} : null
        ].filter(Boolean)},
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:13}}},tooltip:{enabled:false}},
          scales:{x:{ticks:{maxTicksLimit:20,font:{size:11}}},y:{ticks:{callback:function(v){return v.toFixed(1)+'%';},font:{size:11}},title:{display:true,text:'%',font:{size:11}}}}},
        plugins: [crossPlugin]
      };
    } else { return; }

    fsChart = new Chart(canvas, chartConfig);
    window._fsChart = fsChart;

    // Mouse tooltip + crosshair for line charts (kline, dy)
    if (type === 'kline' || type === 'dy') {
      canvas.onmousemove = function(e) {
        if (!fsChart || !fsChart.scales) return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left, my = e.clientY - rect.top;
        var xs = fsChart.scales.x, ys = fsChart.scales.y;
        if (mx < xs.left || mx > xs.right || my < ys.top || my > ys.bottom) {
          fsTT.style.display = 'none'; fsCrossX = null; fsChart.draw(); return;
        }
        var idx = Math.round(xs.getValueForPixel(mx));
        if (idx < 0 || idx >= cfg.labels.length) { fsTT.style.display = 'none'; return; }
        fsCrossX = xs.getPixelForValue(idx);

        if (type === 'kline') {
          var bar = cfg.klineBars[idx];
          var prevBar = cfg.klineBars[idx > 0 ? idx - 1 : 0];
          var chg = prevBar ? (bar.close - prevBar.close) / prevBar.close * 100 : 0;
          var cls = chg >= 0 ? '#ef4444' : '#16a34a';
          fsTT.innerHTML = '<div style="font-weight:600;margin-bottom:4px;color:#93c5fd">'+bar.date+'</div>' +
            '<div>开:<span>'+fmt(bar.open)+'</span></div><div>收:<span style="color:'+cls+'">'+fmt(bar.close)+'</span></div>' +
            '<div>高:<span style="color:#ef4444">'+fmt(bar.high)+'</span></div><div>低:<span style="color:#16a34a">'+fmt(bar.low)+'</span></div>' +
            '<div style="margin-top:3px;border-top:1px solid rgba(255,255,255,.15);padding-top:3px;color:'+cls+'">涨跌: '+(chg>=0?'+':'')+fmt(chg)+'%</div>' +
            (bar.dividend ? '<div style="margin-top:6px;border-top:2px solid #f59e0b;padding-top:5px;font-size:14px;line-height:1.8"><span style="color:#fbbf24">▼ 除权除息</span><div>到账: <span style="color:#34d399;font-weight:700">'+fmt(bar.dividend.amount)+'</span> 元</div><div>每股分红: <span style="color:#60a5fa;font-weight:700">'+fmt(bar.dividend.per_share||0)+'</span> 元</div></div>' : '');
        } else if (type === 'dy') {
          var date = cfg.labels[idx];
          var dyVal = cfg.dySeries[idx];
          var dyStr = dyVal != null ? '<span style="color:#f87171;font-weight:700">'+dyVal.toFixed(2)+'%</span>' : '--';
          fsTT.innerHTML = '<div style="font-weight:600;margin-bottom:4px;color:#fbbf24">'+date+'</div><div>股息率(TTM推算): '+dyStr+'</div>';
        }

        fsTT.style.display = 'block';
        var bw = fsTT.offsetWidth || 150, bh = fsTT.offsetHeight || 100;
        var left = mx + 16, top = my - bh / 2;
        if (left + bw > rect.width - 4) left = mx - bw - 16;
        if (left < 4) left = 4; if (top < 4) top = 4;
        if (top + bh > rect.height - 4) top = rect.height - bh - 4;
        fsTT.style.left = left + 'px'; fsTT.style.top = top + 'px';
        fsChart.draw();
      };
      canvas.onmouseleave = function() { fsTT.style.display = 'none'; fsCrossX = null; if (fsChart) fsChart.draw(); };

      // Zoom/pan
      var totalBars = cfg.labels.length;
      var _kv = { start: 0, end: totalBars };
      canvas.onwheel = function(e) {
        e.preventDefault();
        var range = _kv.end - _kv.start;
        if (e.ctrlKey || e.metaKey) {
          var zf = e.deltaY > 0 ? 1.25 : 0.8;
          var center = (_kv.start + _kv.end) / 2;
          var nr = Math.max(15, Math.min(totalBars, Math.round(range * zf)));
          _kv.start = Math.max(0, Math.round(center - nr / 2));
          _kv.end = Math.min(totalBars, _kv.start + nr);
          if (_kv.end - _kv.start < 15) _kv.end = Math.min(totalBars, _kv.start + 15);
        } else {
          var shift = Math.max(1, Math.round(range * 0.12));
          if (e.deltaY > 0) { _kv.start = Math.min(totalBars - 15, _kv.start + shift); _kv.end = Math.min(totalBars, _kv.end + shift); }
          else { _kv.start = Math.max(0, _kv.start - shift); _kv.end = Math.max(15, _kv.end - shift); }
        }
        fsChart.options.scales.x.min = _kv.start;
        fsChart.options.scales.x.max = _kv.end - 1;
        fsChart.update('none');
        return false;
      };
    }
  }, 50);
}


function closeKlineFullscreen(animate) {
  if (animate === undefined) animate = true;
  var overlay = document.getElementById('kline-fs-overlay');
  if (!overlay) return;
  if (window._fsChart) { window._fsChart.destroy(); window._fsChart = null; }
  if (animate) {
    overlay.style.opacity = '0';
    setTimeout(function(){ if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 300);
  } else {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }
}
window.closeKlineFullscreen = closeKlineFullscreen;


// ESC key handler
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && document.getElementById('kline-fs-overlay')) {
    closeKlineFullscreen(true);
  }
});

// Click overlay background or close button to close
document.addEventListener('click', function(e) {
  if (e.target.id === 'kline-fs-overlay' || e.target.id === 'kline-fs-close') {
    closeKlineFullscreen(true);
  }
});

// 月度涨跌：红涨绿跌（按时间升序，从旧到新）
if(monthlyChartInst)monthlyChartInst.destroy();
const mcSorted=mc.slice().reverse(); // 反转DESC→ASC（旧到新）
const mcLabels=mcSorted.map(m=>m[0]);
const mcData=mcSorted.map(m=>m[1]);
const mcColors=mcData.map(v=>v>=0?'#dc2626':'#16a34a');
monthlyChartInst=new Chart(document.getElementById('monthlyChart'),{
type:'bar',
data:{labels:mcLabels,datasets:[{label:'涨跌幅%',data:mcData,backgroundColor:mcColors}]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},y:{ticks:{callback:v=>v+'%',font:{size:10}}}}}
});

// 季节性：红涨绿跌
if(seasonalChartInst)seasonalChartInst.destroy();
const seaData=DATA.seasonal[code]||[];
const seaLabels=['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
const seaColors=seaData.map(v=>v>=0?'#dc2626':'#16a34a');
seasonalChartInst=new Chart(document.getElementById('seasonalChart'),{
type:'bar',
data:{labels:seaLabels,datasets:[{label:'月均涨跌幅%',data:seaData,backgroundColor:seaColors}]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{ticks:{callback:v=>v+'%'}}}}
});


// ===== 股息率走势图 (TTM Daily Dividend Yield · 公式计算值) — 后端统一计算 =====
document.getElementById('dy-title').textContent=name+' 股息率走势 (TTM · 公式计算值)';

var dyCanvas=document.getElementById('dividendYieldChart');
var dyHint=document.getElementById('dy-hint');
if(dividendYieldChartInst){dividendYieldChartInst.destroy();dividendYieldChartInst=null;}

// Show loading state
dyHint.textContent='正在加载股息率数据...';
dyHint.style.color='#6b7280';

// Fetch dividend yield series from backend (same logic as position page dy)
if(hasAPI()){
 apiCall('GET','/api/v2/dividend-yield-series?code='+encodeURIComponent(code)).then(function(resp){
  if(!resp||!resp.success){
   dyHint.textContent='股息率数据加载失败: '+(resp&&resp.error||'请重启服务器');
   dyHint.style.color='#dc2626';
   setupKlineZoomPan(labels, klineCanvas, dyCanvas, klineChartInst, null);
   return;
  }
  var ds=resp.data;
  var dyLabels=ds.labels||[];
  var dySeries=ds.dy_series||[];
  var dyCloses=ds.close_prices||[];
  var dyEvents=ds.dividend_events||[];
  var hasDivs=dyEvents.length>0;

  // Fallback: ONLY if no events, use quotes.dy
  if(!hasDivs){
   var quotesDy=(DATA.quotes[code]&&DATA.quotes[code].dy)||0;
   dySeries=dyLabels.map(function(){return quotesDy;});
  }

  // Build dividend event lookup for date-based matching
  var dyDivLookup={};
  dyEvents.forEach(function(e){dyDivLookup[e.date]=e;});

  // Dividend event marker points
  var dyEventPts=dyLabels.map(function(d,i){return dyDivLookup[d]&&dySeries[i]!=null?dySeries[i]:null;});

  // Create chart — unified TTM推算 style (solid red line)
  if(dividendYieldChartInst)dividendYieldChartInst.destroy();
  var dyBorderClr='#dc2626';
  var dyDash=[];
  var dyLabel='股息率(TTM推算)';
  var dyLabelFull=dyLabel+' · 公式计算值';
  // Compute dynamic Y-axis range: start from 0 or slightly below data min
  var dyValidVals=dySeries.filter(function(v){return v!=null&&!isNaN(v);});
  var dyMin=dyValidVals.length?Math.min.apply(null,dyValidVals):0;
  var dyMax=dyValidVals.length?Math.max.apply(null,dyValidVals):10;
  // Add 10% padding above max, floor min at 0 or 10% below actual min
  var dyYMin=Math.max(0,Math.floor(dyMin*0.9));
  var dyYMax=Math.ceil(dyMax*1.1);

  dividendYieldChartInst=new Chart(dyCanvas,{
   type:'line',
   data:{labels:dyLabels,datasets:[
    {label:dyLabelFull,data:dySeries,borderColor:dyBorderClr,
     backgroundColor:'transparent',fill:false,borderWidth:hasDivs?2:1.5,
     pointRadius:0,tension:0,spanGaps:false,borderDash:dyDash,
     stepped:false},
    hasDivs?{label:'分红除权日 ▼',data:dyEventPts,borderColor:'#dc2626',
     backgroundColor:'#dc2626',pointRadius:7,pointStyle:'triangle',
     showLine:false,pointBorderWidth:0}:null
   ].filter(Boolean)},
   options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:11}}},tooltip:{enabled:false}},
    scales:{
     x:{ticks:{maxTicksLimit:12,font:{size:10}}},
     y:{min:dyYMin,max:dyYMax,
      ticks:{callback:function(v){return v.toFixed(1)+'%';},font:{size:10}},
      title:{display:true,text:'股息率 %',font:{size:10}}}
    }
   }
  });

  // Crosshair plugin
  var dyCrossPlugin={id:'dyCross',afterDraw:function(chart){
   if(!window._klineCrossX)return;
   var ctx=chart.ctx,ra=chart.scales.y;
   ctx.save();ctx.setLineDash([4,3]);
   ctx.strokeStyle='rgba(220,38,38,.25)';ctx.lineWidth=1;
   ctx.beginPath();ctx.moveTo(window._klineCrossX,ra.top);
   ctx.lineTo(window._klineCrossX,ra.bottom);ctx.stroke();ctx.restore();
  }};
  dividendYieldChartInst.config.plugins=[dyCrossPlugin];

  // Custom tooltip
  var dyTT=document.getElementById('dy-tooltip');
  if(!dyTT){
   dyTT=document.createElement('div');dyTT.id='dy-tooltip';
   dyTT.style.cssText='position:absolute;pointer-events:none;background:rgba(0,0,0,.88);color:#fff;padding:10px 14px;border-radius:8px;font-size:12px;line-height:1.8;z-index:200;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.3);display:none;font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif';
   dyCanvas.parentElement.appendChild(dyTT);
  }
  var onDyMove=function(e){
   var chart=dividendYieldChartInst;if(!chart||!chart.scales)return;
   var rect=dyCanvas.getBoundingClientRect();
   var mx=e.clientX-rect.left,my=e.clientY-rect.top;
   var xs=chart.scales.x,ys=chart.scales.y;
   if(mx<xs.left||mx>xs.right||my<ys.top||my>ys.bottom){dyTT.style.display='none';return;}
   var idx=Math.round(xs.getValueForPixel(mx));
   if(idx<0||idx>=dyLabels.length){dyTT.style.display='none';return;}
   var date=dyLabels[idx];
   var dyVal=dySeries[idx];
   var closePr=dyCloses[idx];
   var dv=dyDivLookup[date];

   // Sync crosshair to K-line
   if(klineChartInst&&klineChartInst.scales){
    var kxs=klineChartInst.scales.x;
    var klineLabels=klineChartInst.data.labels;
    var ki=klineLabels.indexOf(date);
    if(ki>=0){window._klineCrossX=kxs.getPixelForValue(ki);klineChartInst.draw();dividendYieldChartInst.draw();}
   }
   var dyStr=dyVal!=null?'<span style="color:#f87171;font-weight:700">'+dyVal.toFixed(2)+'%</span>':'--';
   var html='<div style="font-weight:600;margin-bottom:4px;color:#fbbf24">'+date+'</div>';
   html+='<div>股息率(TTM推算): '+dyStr+'</div>';
   html+='<div>收盘价: <span style="color:#93c5fd">'+fmt(closePr)+'</span></div>';
   html+='<div style="font-size:10px;color:#9ca3af;margin-top:2px">公式计算值 · 可能与实际公布值存在差异</div>';
   if(dv){
    var srcLabel=dv.source==='web'?'网络公开数据（TTM推算）':dv.source==='ttm_calculated'?'TTM公式推算':'对账单实际到账';
    var srcColor=dv.source==='web'?'#60a5fa':dv.source==='ttm_calculated'?'#f59e0b':'#34d399';
    html+='<div style="margin-top:5px;border-top:2px solid #dc2626;padding-top:5px;font-size:13px;line-height:1.8">';
    html+='<span style="color:#f87171">▼ 分红除权日</span>';
    html+='<div>来源: <span style="color:'+srcColor+'">'+srcLabel+'</span></div>';
    html+='<div>每股: <span style="color:#60a5fa;font-weight:700">'+fmt(dv.per_share||0)+'</span> 元</div>';
    if(dv.amount>0&&dv.source!=='web'){html+='<div>到账: <span style="color:#34d399;font-weight:700">'+fmt(dv.amount)+'</span> 元</div>';}
    html+='</div>';
   }
   dyTT.innerHTML=html;dyTT.style.display='block';
   var bw=dyTT.offsetWidth||150,bh=dyTT.offsetHeight||100;
   var left=mx+16,top=my-bh/2;
   if(left+bw>rect.width-4)left=mx-bw-16;if(left<4)left=4;
   if(top<4)top=4;if(top+bh>rect.height-4)top=rect.height-bh-4;
   dyTT.style.left=left+'px';dyTT.style.top=top+'px';
  };
  var onDyLeave=function(){dyTT.style.display='none';};
  if(window._dyMoveFn)dyCanvas.removeEventListener('mousemove',window._dyMoveFn);
  if(window._dyLeaveFn)dyCanvas.removeEventListener('mouseleave',window._dyLeaveFn);
  window._dyMoveFn=onDyMove;
  window._dyLeaveFn=onDyLeave;
  dyCanvas.addEventListener('mousemove',onDyMove);
  dyCanvas.addEventListener('mouseleave',onDyLeave);

  // Verify chart-vs-table data consistency
  var latestChartDy=null;
  for(var i=dySeries.length-1;i>=0;i--){if(dySeries[i]!=null){latestChartDy=dySeries[i];break;}}
  var tableDy=(DATA.quotes[code]&&DATA.quotes[code].dy)||0;
  // Also check server-returned latest_dy for cross-validation
  var serverLatestDy=resp.latest_dy;
  function dyDiff(a,b){return Math.abs((a||0)-(b||0));}
  if(latestChartDy!=null&&tableDy>0&&dyDiff(latestChartDy,tableDy)>0.5){
   console.warn('股息率数据不一致: 图表最新='+latestChartDy.toFixed(2)+'% vs 持仓表='+tableDy.toFixed(2)+'%');
  }

  dyHint.textContent='滚轮平移 ｜ Ctrl+滚轮缩放 ｜ 公式计算值(TTM推算)'+(hasDivs?' ｜ ▼ = 分红除权日':'')+(latestChartDy!=null?' ｜ 当前: '+latestChartDy.toFixed(2)+'%':'');
  dyHint.style.color='#9ca3af';

  // Setup zoom/pan with the dy chart now available
  setupKlineZoomPan(labels, klineCanvas, dyCanvas, klineChartInst, dividendYieldChartInst);

  // Store dy config for fullscreen + add enlarge button
  window._klineCharts.dy = {
    code: code, name: name, type: 'dy',
    labels: dyLabels, dySeries: dySeries,
    dyEventPts: dyEventPts, hasDivs: hasDivs
  };
  _addEnlargeButton(dyCanvas, 'dy-enlarge-btn', '放大股息率走势', 'dy');

}).catch(function(e){
  console.error('Dividend yield series error:',e);
  dyHint.textContent='股息率数据加载失败';
  dyHint.style.color='#dc2626';
  setupKlineZoomPan(labels, klineCanvas, dyCanvas, klineChartInst, null);
});
} else {
 dyHint.textContent='离线模式，无法获取股息率数据';
 dyHint.style.color='#9ca3af';
 setupKlineZoomPan(labels, klineCanvas, dyCanvas, klineChartInst, null);
}

// ===== Synchronized Zoom/Pan (extracted to reusable function) =====
function setupKlineZoomPan(labels, kCanvas, dyCanvas, chart1, chart2){
 var totalBars=labels.length;
 if(totalBars===0)return;
 var _kv={start:Math.max(0,totalBars-120),end:totalBars};

 // Store state globally for slider sync
 window._klineZoomState = { kv: _kv, totalBars: totalBars, chart1: chart1, chart2: chart2, labels: labels };

 function applyView(){
  [chart1,chart2].forEach(function(ch){
   if(!ch)return;
   ch.options.scales.x.min=_kv.start;
   ch.options.scales.x.max=_kv.end-1;
   ch.update('none');
  });
  updateKlineSlider();
 }
 function onWheel(e){
  e.preventDefault();
  var range=_kv.end-_kv.start;
  if(e.ctrlKey||e.metaKey){
   var zf=e.deltaY>0?1.25:0.8;
   var center=(_kv.start+_kv.end)/2;
   var nr=Math.max(15,Math.min(totalBars,Math.round(range*zf)));
   _kv.start=Math.max(0,Math.round(center-nr/2));
   _kv.end=Math.min(totalBars,_kv.start+nr);
   if(_kv.end-_kv.start<15)_kv.end=Math.min(totalBars,_kv.start+15);
  }else{
   var shift=Math.max(1,Math.round(range*0.12));
   if(e.deltaY>0){_kv.start=Math.min(totalBars-15,_kv.start+shift);_kv.end=Math.min(totalBars,_kv.end+shift);}
   else{_kv.start=Math.max(0,_kv.start-shift);_kv.end=Math.max(15,_kv.end-shift);}
  }
  applyView();
 }
 if(window._kwFn)kCanvas.removeEventListener('wheel',window._kwFn);
 window._kwFn=onWheel;
 kCanvas.addEventListener('wheel',onWheel,{passive:false});
 if(dyCanvas){
  if(window._dywFn)dyCanvas.removeEventListener('wheel',window._dywFn);
  window._dywFn=onWheel;
  dyCanvas.addEventListener('wheel',onWheel,{passive:false});
 }
 applyView();

 // Build slider
 buildKlineSlider(kCanvas);
}

} // end renderKline

// ── K-line Slider (draggable timeline navigator) ──

function buildKlineSlider(kCanvas) {
  var st = window._klineZoomState;
  if (!st || !st.kv) return;

  // Remove old slider
  var old = document.getElementById('kline-slider-wrap');
  if (old) old.parentNode.removeChild(old);

  var wrap = document.createElement('div');
  wrap.id = 'kline-slider-wrap';
  wrap.style.cssText = 'position:relative;height:32px;margin:6px 0 0;background:#f3f4f6;border-radius:4px;cursor:pointer;user-select:none;overflow:hidden';
  kCanvas.parentElement.appendChild(wrap);

  // Background bar (full range mini view)
  var bar = document.createElement('div');
  bar.id = 'kline-slider-bar';
  bar.style.cssText = 'position:absolute;inset:0';

  // Viewport indicator
  var handle = document.createElement('div');
  handle.id = 'kline-slider-handle';
  handle.style.cssText = 'position:absolute;top:0;bottom:0;background:rgba(37,99,235,.25);border:2px solid #2563eb;border-radius:4px;pointer-events:none;transition:none';
  wrap.appendChild(bar);
  wrap.appendChild(handle);

  // Left resize handle
  var leftKnob = document.createElement('div');
  leftKnob.id = 'kline-slider-lknob';
  leftKnob.style.cssText = 'position:absolute;top:0;bottom:0;width:6px;background:#2563eb;border-radius:3px 0 0 3px;cursor:ew-resize;z-index:2';
  wrap.appendChild(leftKnob);

  // Right resize handle
  var rightKnob = document.createElement('div');
  rightKnob.id = 'kline-slider-rknob';
  rightKnob.style.cssText = 'position:absolute;top:0;bottom:0;width:6px;background:#2563eb;border-radius:0 3px 3px 0;cursor:ew-resize;z-index:2';
  wrap.appendChild(rightKnob);

  // Date labels
  var dateHint = document.createElement('div');
  dateHint.id = 'kline-slider-hint';
  dateHint.style.cssText = 'position:absolute;bottom:-16px;left:0;right:0;display:flex;justify-content:space-between;font-size:10px;color:#9ca3af;padding:0 2px';
  // Show first and last dates
  var labels = st.labels || [];
  if (labels.length) {
    dateHint.innerHTML = '<span>'+labels[0]+'</span><span>'+labels[labels.length-1]+'</span>';
  }
  wrap.appendChild(dateHint);

  updateKlineSlider();

  // ── Drag handling ──
  var dragMode = null; // 'pan' | 'left' | 'right'
  var dragStartX = 0;
  var dragStartKv = null;

  function getX(e) { return e.touches ? e.touches[0].clientX : e.clientX; }

  function updateFromHandle(x) {
    st = window._klineZoomState;
    if (!st) return;
    var rect = wrap.getBoundingClientRect();
    var w = rect.width;
    var pct = Math.max(0, Math.min(1, (x - rect.left) / w));
    var totalBars = st.totalBars;
    var range = st.kv.end - st.kv.start;

    if (dragMode === 'pan') {
      var center = Math.round(pct * totalBars);
      st.kv.start = Math.max(0, Math.min(totalBars - range, center - Math.round(range / 2)));
      st.kv.end = st.kv.start + range;
    } else if (dragMode === 'left') {
      var newStart = Math.round(pct * totalBars);
      if (newStart >= st.kv.end - 5) newStart = st.kv.end - 5;
      st.kv.start = Math.max(0, newStart);
    } else if (dragMode === 'right') {
      var newEnd = Math.round(pct * totalBars);
      if (newEnd <= st.kv.start + 5) newEnd = st.kv.start + 5;
      st.kv.end = Math.min(totalBars, newEnd);
    }

    // Apply view
    [st.chart1, st.chart2].forEach(function(ch) {
      if (!ch) return;
      ch.options.scales.x.min = st.kv.start;
      ch.options.scales.x.max = st.kv.end - 1;
      ch.update('none');
    });
    updateKlineSlider();
  }

  // Pan: click and drag on background
  wrap.addEventListener('mousedown', function(e) {
    dragMode = 'pan';
    dragStartX = getX(e);
    dragStartKv = { start: st.kv.start, end: st.kv.end };
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  // Left knob resize
  leftKnob.addEventListener('mousedown', function(e) {
    dragMode = 'left';
    dragStartX = getX(e);
    e.stopPropagation();
    e.preventDefault();
  });

  // Right knob resize
  rightKnob.addEventListener('mousedown', function(e) {
    dragMode = 'right';
    dragStartX = getX(e);
    e.stopPropagation();
    e.preventDefault();
  });

  document.addEventListener('mousemove', function(e) {
    if (!dragMode) return;
    var x = getX(e);
    updateFromHandle(x);
  });

  document.addEventListener('mouseup', function() {
    dragMode = null;
    document.body.style.userSelect = '';
  });

  // Touch support
  wrap.addEventListener('touchstart', function(e) {
    dragMode = 'pan';
    dragStartX = getX(e);
    dragStartKv = { start: st.kv.start, end: st.kv.end };
  }, { passive: false });
  document.addEventListener('touchmove', function(e) {
    if (!dragMode) return;
    updateFromHandle(getX(e));
  });
  document.addEventListener('touchend', function() { dragMode = null; });
}

function updateKlineSlider() {
  var st = window._klineZoomState;
  var handle = document.getElementById('kline-slider-handle');
  var lknob = document.getElementById('kline-slider-lknob');
  var rknob = document.getElementById('kline-slider-rknob');
  if (!st || !handle) return;

  var totalBars = st.totalBars;
  if (totalBars <= 0) return;
  var pStart = st.kv.start / totalBars * 100;
  var pEnd = st.kv.end / totalBars * 100;

  handle.style.left = pStart + '%';
  handle.style.width = (pEnd - pStart) + '%';
  if (lknob) lknob.style.left = pStart + '%';
  if (rknob) rknob.style.left = pEnd + '%';
}

// ── Global helpers ──

function switchKline(code, btn){currentKlineCode=code;document.querySelectorAll('#page-kline .tab-btn').forEach(b=>b.classList.remove('active'));if(btn)btn.classList.add('active');renderKline(code);}

function calcSMA(data,period){
const result=[];
for(let i=0;i<data.length;i++){
if(i<period-1){result.push(null);continue;}
let sum=0;for(let j=i-period+1;j<=i;j++)sum+=data[j];
result.push(+(sum/period).toFixed(2));
}
return result;
}

