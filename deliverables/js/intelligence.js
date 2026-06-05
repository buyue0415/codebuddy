
// ===== 智能预测模块 V1.0 (30日预测走势图 + 次日预测 + 信号详情 + 操作建议) =====
var intelCode=_firstWatchCode(), intelDate=null;
var _intlViewYear=0, _intlViewMonth=0;
var _intlAvailDates=new Set();
var _intel30DayChart=null;

function switchIntelStock(code){intelCode=code;_intlViewYear=0;_intlViewMonth=0;intelCloseDatePicker();renderIntelligence(code);}
function selectIntelDate(date){intelDate=date;renderIntelligence(intelCode);}

// ===== Dropdown 日历组件（ndp 风格，参考 news.js） =====

function intelToggleDatePicker(e){
 if(e) e.stopPropagation();
 var panel=document.getElementById('intel-date-panel');
 var trigger=document.getElementById('intel-date-trigger');
 if(!panel) return;
 var isOpen=panel.classList.contains('open');
 if(isOpen){ intelCloseDatePicker(); }
 else{
  buildIntlCalendar();
  panel.classList.add('open');
  if(trigger) trigger.classList.add('active');
 }
}

function intelCloseDatePicker(){
 var panel=document.getElementById('intel-date-panel');
 var trigger=document.getElementById('intel-date-trigger');
 if(panel) panel.classList.remove('open');
 if(trigger) trigger.classList.remove('active');
}

function intelDatePrevMonth(){
 _intlViewMonth--;
 if(_intlViewMonth<1){_intlViewMonth=12;_intlViewYear--;}
 buildIntlCalendar();
}

function intelDateNextMonth(){
 _intlViewMonth++;
 if(_intlViewMonth>12){_intlViewMonth=1;_intlViewYear++;}
 buildIntlCalendar();
}

function intelDateSelect(dateStr){
 intelDate=dateStr;
 intelCloseDatePicker();
 var textEl=document.getElementById('intel-date-text');
 if(textEl) textEl.textContent=dateStr;
 renderIntelligence(intelCode);
}

function intelDateClear(){
 intelDate=null;
 intelCloseDatePicker();
 var textEl=document.getElementById('intel-date-text');
 if(textEl) textEl.textContent='选择日期';
 renderIntelligence(intelCode);
}

function buildIntlCalendar(){
 var titleEl=document.getElementById('intel-nav-title');
 var daysEl=document.getElementById('intel-days');
 if(!titleEl||!daysEl) return;

 // Init view to selected date or today
 if(!_intlViewYear){
  if(intelDate){
   _intlViewYear=parseInt(intelDate.substring(0,4));
   _intlViewMonth=parseInt(intelDate.substring(5,7));
  }else{
   var now=new Date();
   _intlViewYear=now.getFullYear();
   _intlViewMonth=now.getMonth()+1;
  }
 }

 titleEl.textContent=_intlViewYear+'年'+_intlViewMonth+'月';

 var first=new Date(_intlViewYear,_intlViewMonth-1,1);
 var last=new Date(_intlViewYear,_intlViewMonth,0);
 var startDay=first.getDay();
 var offset=(startDay===0)?6:startDay-1;

 var today=new Date();
 var todayStr=today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');

 var cells='';
 for(var e=0;e<offset;e++) cells+='<div class="ndp-day other"></div>';

 for(var d=1;d<=last.getDate();d++){
  var dateStr=_intlViewYear+'-'+String(_intlViewMonth).padStart(2,'0')+'-'+String(d).padStart(2,'0');
  var cls='ndp-day';
  if(dateStr===todayStr) cls+=' today';
  if(_intlAvailDates.has(dateStr)) cls+=' has-news';
  if(intelDate===dateStr) cls+=' selected';
  cells+='<div class="'+cls+'" onclick="intelDateSelect(\''+dateStr+'\')">'+d+'</div>';
 }

 var total=offset+last.getDate();
 var remainder=total%7;
 if(remainder>0){for(var r=0;r<7-remainder;r++) cells+='<div class="ndp-day other"></div>';}

 daysEl.innerHTML=cells;
}

// Click outside to close
document.addEventListener('click',function(e){
 var drop=document.getElementById('intel-date-drop');
 if(!drop) return;
 if(!drop.contains(e.target)) intelCloseDatePicker();
});

// ===== 主渲染 =====

function renderIntelligence(code){
var D=DATA, name=getStockName(code);
genStockTabs('intel-tabs','switchIntelStock',code);

var preds=(D.daily_predictions||[]).filter(function(p){return p.code===code;}).sort(function(a,b){return b.date.localeCompare(a.date);});

// Use prediction dates for calendar highlighting
var predDates=preds.map(function(p){return p.date;});
_intlAvailDates=new Set(predDates);

// Load K-line dates for status display only
var klineDates=[];
var kd=D.kline_daily&&D.kline_daily[code]||D.kline&&D.kline[code]||[];
if(kd.length){klineDates=kd.map(function(k){return k[0];});}
else{var km=D.kline_monthly&&D.kline_monthly[code]||[];klineDates=km.map(function(k){return k[0];});}

// Update dropdown trigger text & status
var todayStr=new Date().toISOString().substring(0,10);
var textEl=document.getElementById('intel-date-text');
if(textEl) textEl.textContent=intelDate||'选择日期';
var statusEl=document.getElementById('intel-date-status');
if(statusEl) statusEl.textContent=predDates.length+'条预测 | '+klineDates.length+'天行情';
var dropEl=document.getElementById('intel-date-drop');
if(dropEl) dropEl.classList.add('show');

// Default to today
if(!intelDate){
 intelDate=todayStr;
}
var pred=preds.filter(function(p){return p.date===intelDate;})[0];

// ===== Next day card =====
var ndEl=document.getElementById('intel-next-content');
if(pred){
 var nd=pred.next_day||{};
 var cfdLevel=nd.confidence>=0.7?'high':nd.confidence>=0.5?'mid':'low';
 var act=pred.actual||{};
 var hitBadge='';
 if(act.next_day_direction_hit===true) hitBadge=' <span style="font-size:12px;color:#16a34a">✓ 命中</span>';
 else if(act.next_day_direction_hit===false) hitBadge=' <span style="font-size:12px;color:#dc2626">✗ 未命中</span>';
 ndEl.innerHTML='<div style="font-size:13px;color:#6b7280">预测 '+pred.date+' 次日'+hitBadge+'</div>'+
  '<div class="dp-next-dir '+nd.direction+'">'+dirIcon(nd.direction)+' '+dirText(nd.direction)+'</div>'+
  '<div class="dp-next-range">'+fmt(nd.low)+' ~ '+fmt(nd.high)+'</div>'+
  '<div class="dp-confidence '+cfdLevel+'">信心 '+(nd.confidence*100).toFixed(0)+'%</div>'+
  '<div style="font-size:12px;color:#6b7280;margin-top:10px;line-height:1.6;text-align:left">'+(nd.advice||'')+'</div>'+
  (act.close!=null?'<div class="dp-next-actual" style="margin-top:8px;padding:6px 10px;background:#f0fdf4;border-radius:6px;font-size:12px"><b>实际:</b> 开 '+fmt(act.open)+' 高 '+fmt(act.high)+' 低 '+fmt(act.low)+' 收 '+fmt(act.close)+'</div>':'');
}else{ndEl.innerHTML='<div class="dp-empty" style="text-align:center;color:#9ca3af;padding:20px">暂无预测</div>';}

var sea=D.seasonal[code]||[], q=D.quotes[code], currentPrice=q?.price||0;
var now=new Date(), nowMonth=now.getMonth()+1;

// ===== Key levels =====
var dy=q?.dy||0;
var _ps=CONFIG.price_strategy||{buy_multiplier:0.95,sell_multiplier:1.10};
document.getElementById('intel-price-content').innerHTML=
 '<div style="font-size:13px;line-height:2.2">'+
 '<div>现价: <b style="color:'+(q?.change>=0?'#dc2626':'#16a34a')+'">'+fmt(currentPrice)+'</b></div>'+
 '<div>加仓 &le; <span class="down">'+fmt(currentPrice*_ps.buy_multiplier)+'</span></div>'+
 '<div>减仓 &ge; <span class="up">'+fmt(currentPrice*_ps.sell_multiplier)+'</span></div>'+
 '<div>股息率 <span class="up">'+fmt(dy)+'%</span></div></div>';

// ===== Advice =====
var ndDir=pred?pred.next_day.direction:'neutral';
var curMonthSea=sea[nowMonth-1]||0;
var adviceH='';
if(ndDir==='bearish'&&curMonthSea<0){
 adviceH='<b style="color:#dc2626">短期看跌</b> + 当前月季节性偏弱('+fmt(curMonthSea)+'%) → <b>等待下月加仓窗口</b>';
}else if(ndDir==='bullish'){adviceH='<b style="color:#16a34a">短期看涨</b> → <b>耐心持有，选择最佳月份高位兑现</b>';}
else{adviceH='<b style="color:#f59e0b">信号中性</b> → 股息率'+fmt(dy)+'%提供安全垫，<b>持有收息为主</b>';}
document.getElementById('intel-advice').innerHTML='<p>'+adviceH+'</p><p style="font-size:12px;color:#6b7280;margin-top:4px">高股息策略：稳拿分红 | 每日15:35自动更新</p>';

// ===== Signal detail =====
var sigH='';
if(pred){
 var sig=pred.signals||{}, snames={macd:'MACD',rsi:'RSI',bollinger:'布林带',kdj:'KDJ',seasonal:'季节',atr:'ATR',money_flow:'资金',adx_trend:'ADX',obv_divergence:'OBV',vol_convergence:'波动率'};
 sigH='<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:12px">';
 Object.keys(snames).forEach(function(k){
  var s=sig[k]||{}, dir=s.direction||'neutral', raw=s.raw||s.value||'--';
  var val=typeof raw==='number'?raw.toFixed(2):raw;
  if(val==='--' || val==='0') return;
  sigH+='<div style="padding:8px;background:#f8fafc;border-radius:6px;font-size:12px;text-align:center">'+
   '<div style="font-weight:600">'+snames[k]+'</div>'+
   '<div style="font-size:16px;font-weight:700;color:'+(dir==='bullish'?'#dc2626':dir==='bearish'?'#16a34a':'#6b7280')+'">'+val+'</div></div>';
 });
 sigH+='</div>';
 var astats=D.accuracy_stats?.[code]||{}, last20=astats.last_20||{};
 sigH+='<div><b>准确率(近20):</b> 方向 '+Number((last20.direction||{}).rate*100).toFixed(0)+'% | 区间 '+Number((last20.range||{}).rate*100).toFixed(0)+'%</div>';
 // Backtest comparison
 var backtest=astats.backtest_60||{}, hourly=backtest.hourly||{};
 var improvement=hourly.improvement||0;
 var blRate=hourly.baseline_rate||0;
 if(improvement!==0 || blRate>0){
  var impIcon=improvement>0?'📈':improvement<0?'📉':'➡';
  var impColor=improvement>0?'#16a34a':improvement<0?'#dc2626':'#6b7280';
  sigH+='<div style="margin-top:6px;font-size:12px">';
  sigH+='<b>🧪 学习效果(近60):</b> ';
  sigH+='学习后 <b style="color:#2563eb">'+Number(backtest.direction.rate).toFixed(0)+'%</b> vs ';
  sigH+='基线 <b style="color:#9ca3af">'+blRate+'%</b> ';
  sigH+='<b style="color:'+impColor+'">'+impIcon+' '+(improvement>0?'+':'')+improvement.toFixed(1)+'%</b>';
  sigH+='</div>';
 }
}else{sigH='<div style="color:#9ca3af;font-size:13px">暂无信号数据，等待每日自动生成</div>';}
document.getElementById('intel-signal-detail').innerHTML=sigH;

// ===== History timeline =====
// Show last 10 verified + today + next 10 future predictions
// todayStr already defined above at line ~134
var allPredsSorted=(D.daily_predictions||[]).filter(function(p){return p.code===code;}).sort(function(a,b){return a.date.localeCompare(b.date);});

// Split into past/verified and future/unverified
var pastPreds=[], futurePreds=[];
for(var pi=0;pi<allPredsSorted.length;pi++){
 var pp=allPredsSorted[pi];
 var pa=pp.actual||{};
 if(pa.next_day_direction_hit!=null && pp.date<todayStr){
  pastPreds.push(pp);
 }else if(pp.date>=todayStr){
  futurePreds.push(pp);
 }
}
pastPreds=pastPreds.slice(-10);         // last 10 verified
futurePreds=futurePreds.slice(0,11);    // today + next 10
var timelineItems=pastPreds.concat(futurePreds);

// Fallback: if split produced empty, show ALL predictions
if(!timelineItems.length){
 timelineItems=allPredsSorted.slice(-21);
}

var grid=document.getElementById('intel-hist-grid');
if(!grid) return;
if(!timelineItems.length){
 grid.innerHTML='<span style="font-size:12px;color:#9ca3af">暂无预测数据</span>';
}else{
 var dotsH='<div class="dp-timeline">';
 for(var i=0;i<timelineItems.length;i++){
  var p=timelineItems[i];
  if(!p||!p.date) continue;
  var act=p.actual||{};
  var nd=p.next_day||{};
  var isToday=p.date===todayStr;
  var isFuture=p.date>=todayStr;

  // Status: backfilled data always takes priority over today/future flags
  var statusCls='pending', statusText='待验证';
  if(act.next_day_direction_hit!=null){
   if(act.next_day_direction_hit){
    statusCls='hit'; statusText='命中';
   }else{
    statusCls='miss'; statusText='未命中';
   }
  }else if(isToday){
   statusText='预测中';
  }else if(!isFuture){
   // Past date without verification: stale, needs backfill
   statusCls='stale'; statusText='待回填';
  }

  // Direction
  var dIcon='➡', dCls='neutral';
  if(nd.direction==='bullish'){dIcon='↑'; dCls='bullish';}
  else if(nd.direction==='bearish'){dIcon='↓'; dCls='bearish';}

  // Range
  var lo=nd.low, hi=nd.high;
  var rangeTxt=(lo!=null&&hi!=null)?fmt(lo)+'~'+fmt(hi):'--';

  dotsH+='<div class="dp-tl-item '+statusCls+(isToday?' today':'')+'">'+
   '<div class="dp-tl-date">'+p.date.substring(5)+'</div>'+
   '<div class="dp-tl-dir '+dCls+'">'+dIcon+'</div>'+
   '<div class="dp-tl-range">'+rangeTxt+'</div>'+
   '<div class="dp-tl-status '+statusCls+'">'+statusText+'</div>'+
   '</div>';
 }
 dotsH+='</div>';
 grid.innerHTML=dotsH;
}


// ===== 30-Day Prediction Chart =====
render30DayChart(code, preds);
}

function render30DayChart(code, allPreds){
    var canvas = document.getElementById('intel30DayChart');
    if(!canvas) return;
    if(typeof Chart === 'undefined') return;

    if(_intel30DayChart){ _intel30DayChart.destroy(); _intel30DayChart = null; }

    // ---- Load 180 days of historical K-line ----
    var kl = DATA.kline_daily && DATA.kline_daily[code] || DATA.kline && DATA.kline[code] || [];
    var klSorted = kl.slice().reverse(); // oldest → newest
    var histDays = Math.min(180, klSorted.length);
    var histSlice = klSorted.slice(-histDays);

    var histLabels = [];
    var histClose = [];
    for(var i = 0; i < histSlice.length; i++){
        histLabels.push(histSlice[i][0]);
        histClose.push(histSlice[i][2]); // close price
    }

    // ---- Load 30 days of future predictions ----
    var today = new Date().toISOString().substring(0, 10);
    var futurePreds = allPreds
        .filter(function(p){ return p.date >= today; })
        .sort(function(a,b){ return a.date.localeCompare(b.date); })
        .slice(0, 30);

    var predLabels = [];
    var predClose = [];
    var predHigh = [];
    var predLow = [];
    var predConf = [];

    for(var i = 0; i < futurePreds.length; i++){
        var nd = futurePreds[i].next_day || {};
        predLabels.push(futurePreds[i].date);
        var pc = futurePreds[i].prev_close || (histClose.length ? histClose[histClose.length-1] : 0);
        // Estimated predicted close from high/low midpoint + direction bias
        var estClose = pc;
        if(nd.direction === 'bullish') estClose = nd.low + (nd.high - nd.low) * 0.55;
        else if(nd.direction === 'bearish') estClose = nd.high - (nd.high - nd.low) * 0.55;
        else estClose = (nd.high + nd.low) / 2;
        predClose.push(estClose);
        predHigh.push(nd.high || estClose);
        predLow.push(nd.low || estClose);
        predConf.push(nd.confidence || 0);
    }

    // Bridge: connect last historical close to first prediction
    var allLabels = histLabels.concat(predLabels);

    // Build datasets
    var datasets = [
        {
            label: '历史收盘',
            data: histClose.concat(new Array(predLabels.length).fill(null)),
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37,99,235,0.05)',
            borderWidth: 2,
            pointRadius: 0,
            fill: false,
            order: 0
        }
    ];

    if(predClose.length > 0){
        // Connect the bridge point
        var predDataArr = new Array(histClose.length).fill(null);
        predDataArr[histClose.length - 1] = histClose[histClose.length - 1]; // bridge
        for(var i = 0; i < predClose.length; i++){
            predDataArr.push(predClose[i]);
        }

        datasets.push({
            label: '预测收盘',
            data: predDataArr,
            borderColor: '#f59e0b',
            borderWidth: 2.5,
            borderDash: [6, 3],
            pointRadius: predLabels.length <= 10 ? 3 : 0,
            pointBackgroundColor: '#f59e0b',
            fill: false,
            order: 0
        });

        // Range band (high-low)
        var bandHigh = new Array(histClose.length).fill(null);
        var bandLow = new Array(histClose.length).fill(null);
        var lastClose = histClose[histClose.length - 1];
        bandHigh[histClose.length - 1] = lastClose;
        bandLow[histClose.length - 1] = lastClose;
        for(var i = 0; i < predHigh.length; i++){
            bandHigh.push(predHigh[i]);
            bandLow.push(predLow[i]);
        }

        datasets.push({
            label: '预测上限',
            data: bandHigh,
            borderColor: 'rgba(245,158,11,0.3)',
            borderWidth: 1,
            borderDash: [2, 4],
            pointRadius: 0,
            fill: false,
            order: 1
        });
        datasets.push({
            label: '预测下限',
            data: bandLow,
            borderColor: 'rgba(245,158,11,0.3)',
            borderWidth: 1,
            borderDash: [2, 4],
            pointRadius: 0,
            fill: '-1', // Fill to previous dataset (upper band)
            backgroundColor: 'rgba(245,158,11,0.08)',
            order: 1
        });
    }

    // ---- Plugin: vertical divider ----
    var dividerPlugin = {
        id: 'pred30Divider',
        afterDraw: function(chart){
            if(predLabels.length === 0) return;
            var xs = chart.scales.x, ys = chart.scales.y;
            if(!xs || !ys) return;
            var divX = xs.getPixelForValue(histClose.length - 0.5);
            if(divX == null || divX < xs.left || divX > xs.right) return;
            chart.ctx.save();
            chart.ctx.setLineDash([6, 4]);
            chart.ctx.strokeStyle = 'rgba(249,115,22,0.5)';
            chart.ctx.lineWidth = 2;
            chart.ctx.beginPath();
            chart.ctx.moveTo(divX, ys.top);
            chart.ctx.lineTo(divX, ys.bottom);
            chart.ctx.stroke();
            // Label
            chart.ctx.fillStyle = '#f97316';
            chart.ctx.font = 'bold 11px -apple-system,PingFang SC,sans-serif';
            chart.ctx.textAlign = 'left';
            var labelX = Math.min(divX + 8, xs.right - 60);
            chart.ctx.fillText('← 历史  |  预测 →', labelX, ys.top + 16);
            chart.ctx.restore();
        }
    };

    try{
        _intel30DayChart = new Chart(canvas, {
            type: 'line',
            data: { labels: allLabels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 500 },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { font: {size: 11}, usePointStyle: true, padding: 14, filter: function(item){ return item.datasetIndex < 2; } } },
                    tooltip: {
                        callbacks: {
                            label: function(ctx){
                                if(ctx.raw == null) return '';
                                return ctx.dataset.label + ': ¥' + ctx.raw.toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { font: {size: 9}, maxTicksLimit: 20, autoSkip: true },
                        title: { display: true, text: '日期', font: {size: 11} }
                    },
                    y: {
                        ticks: { font: {size: 10}, callback: function(v){ return '¥'+v.toFixed(2); } },
                        title: { display: true, text: '价格', font: {size: 11} }
                    }
                }
            },
            plugins: [dividerPlugin]
        });
    }catch(e){
        console.warn('30-day chart init failed:', e);
    }
}
