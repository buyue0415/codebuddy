// ===== 智能预测 (合并预测与方案+日预测) =====
var intelCode=getWatchlist()[0]?.code||'601166', intelDate=null, intelDailyInst=null, intelMonthlyInst=null;
var intelTab='daily';

function switchIntelStock(code){intelCode=code;renderIntelligence(code);}
function selectIntelDate(date){intelDate=date;renderIntelligence(intelCode);}
function switchIntelTab(tab){
 intelTab=tab;
 // Update button active state
 document.querySelectorAll('#intel-chart-tabs .tab-btn').forEach(function(b){
  b.classList.toggle('active',b.getAttribute('onclick').includes("'"+tab+"'"));
 });
 renderIntelligence(intelCode);
}

function renderIntelligence(code){
var D=DATA, name=getStockName(code);
genStockTabs('intel-tabs','switchIntelStock',code);

var preds=(D.daily_predictions||[]).filter(function(p){return p.code===code;}).sort(function(a,b){return b.date.localeCompare(a.date);});
var sel=document.getElementById('intel-date-select');
sel.innerHTML=preds.length?preds.map(function(p){return '<option value="'+p.date+'"'+(p.date===intelDate?' selected':'')+'>'+p.date+'</option>';}).join(''):'<option>--</option>';
if(!intelDate&&preds.length) intelDate=preds[0].date;
var pred=preds.filter(function(p){return p.date===intelDate;})[0];

// Next day card
var ndEl=document.getElementById('intel-next-content');
if(pred){
 var nd=pred.next_day||{};
 var cfdLevel=nd.confidence>=0.7?'high':nd.confidence>=0.5?'mid':'low';
 ndEl.innerHTML='<div style="font-size:13px;color:#6b7280">预测 '+pred.date+' 次日</div>'+
  '<div class="dp-next-dir '+nd.direction+'">'+dirIcon(nd.direction)+' '+dirText(nd.direction)+'</div>'+
  '<div class="dp-next-range">'+fmt(nd.low)+' ~ '+fmt(nd.high)+'</div>'+
  '<div class="dp-confidence '+cfdLevel+'">信心 '+(nd.confidence*100).toFixed(0)+'%</div>'+
  (nd.advice?'<div style="font-size:12px;color:#6b7280;margin-top:10px;line-height:1.6;text-align:left">'+nd.advice+'</div>':'');
}else{ndEl.innerHTML='<div class="dp-empty" style="text-align:center;color:#9ca3af;padding:20px">暂无预测</div>';}

// 6-month seasonal
var sea=D.seasonal[code]||[], q=D.quotes[code], currentPrice=q?.price||0;
var months=['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
var now=new Date(), nowMonth=now.getMonth()+1;
var seasH='';
for(var i=0;i<6;i++){
 var mIdx=(nowMonth-1+i)%12, chg=sea[mIdx]||0;
 var pp=currentPrice*(1+chg/100);
 seasH+='<div class="intel-seas-item"><div class="seas-m">'+months[mIdx]+'</div><div class="seas-p" style="color:'+(chg>=0?'#ef4444':'#16a34a')+'">'+fmt(pp)+'</div><div class="seas-chg" style="color:'+(chg>=0?'#ef4444':'#16a34a')+'">'+(chg>=0?'+':'')+fmt(chg)+'%</div></div>';
}
document.getElementById('intel-seasonal-cards').innerHTML=seasH||'<div style="color:#9ca3af;font-size:12px">暂无季节数据</div>';

// Key levels
var dy=q?.dy||0;
document.getElementById('intel-price-content').innerHTML=
 '<div style="font-size:13px;line-height:2.2">'+
 '<div>现价: <b style="color:'+(q?.change>=0?'#dc2626':'#16a34a')+'">'+fmt(currentPrice)+'</b></div>'+
 '<div>加仓 &le; <span class="down">'+fmt(currentPrice*0.95)+'</span></div>'+
 '<div>减仓 &ge; <span class="up">'+fmt(currentPrice*1.10)+'</span></div>'+
 '<div>股息率 <span class="up">'+fmt(dy)+'%</span><sup style="font-size:10px;color:#f59e0b" title="公式计算值（TTM推算）&#10;基于最近12个月分红与当前股价推算">TTM</sup></div></div>';

// Chart - only render the visible tab
document.getElementById('intel-chart-title').textContent=name+' 走势图';
// Sync chart tab active state
document.querySelectorAll('#intel-chart-tabs .tab-btn').forEach(function(b){
 b.classList.toggle('active',b.getAttribute('onclick').includes("'"+intelTab+"'"));
});
if(intelTab==='daily'){if(intelMonthlyInst){intelMonthlyInst.destroy();intelMonthlyInst=null;}
 if(pred){
  var hourly=pred.hourly||[], prevClose=pred.prev_close||0;
  var dlbls=['09:30','10:30','11:30','13:00','14:00','15:00'];
  var dLine=[prevClose], dHigh=[], dLow=[], lastV=prevClose;
  hourly.forEach(function(h){
   dHigh.push(h.pred_high||lastV);
   dLow.push(h.pred_low||lastV);
   lastV=h.pred_close||lastV;
   dLine.push(lastV);
  });
  dLine.push(lastV); // final close = last block's close
  var bandData=[prevClose].concat(dHigh).concat([dHigh[dHigh.length-1]]);
  var lowData=[prevClose].concat(dLow).concat([dLow[dLow.length-1]]);
  if(intelDailyInst)intelDailyInst.destroy();
  intelDailyInst=new Chart(document.getElementById('intelDailyChart'),{
   type:'line', data:{labels:dlbls, datasets:[
    {label:'预测上限',data:bandData,borderColor:'rgba(239,68,68,.5)',backgroundColor:'rgba(239,68,68,.08)',borderWidth:1,pointRadius:0,fill:'+2',tension:0.3},
    {label:'预测下限',data:lowData,borderColor:'rgba(34,197,94,.5)',backgroundColor:'rgba(34,197,94,.08)',borderWidth:1,pointRadius:0,fill:false,tension:0.3},
    {label:'预测价',data:dLine,borderColor:'#2563eb',borderWidth:2,pointRadius:4,pointBackgroundColor:'#2563eb',fill:false,tension:0.3}
   ]},
   options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'top',labels:{font:{size:11},usePointStyle:true}},tooltip:{callbacks:{label:function(ctx){return ctx.dataset.label+': '+ctx.parsed.y.toFixed(2);}}}},scales:{y:{ticks:{font:{size:10}}},x:{ticks:{font:{size:10}}}}}
  });
 }else{
  var c=document.getElementById('intelDailyChart');
  if(c){var p=c.parentNode;c.remove();p.innerHTML='<canvas id="intelDailyChart" style="width:100%;height:100%"></canvas><div style="text-align:center;padding:40px;color:#9ca3af;font-size:13px">暂无日内预测数据</div>';}
 }
 document.getElementById('intel-chart-daily').style.display='block';
 document.getElementById('intel-chart-monthly').style.display='none';
}else{ // monthly tab
 if(intelDailyInst){intelDailyInst.destroy();intelDailyInst=null;}
 // Show container FIRST so Chart.js gets correct dimensions
 document.getElementById('intel-chart-daily').style.display='none';
 document.getElementById('intel-chart-monthly').style.display='block';
 var klineMK=D.kline[code]||[], histC=klineMK.slice(0,12).reverse().map(function(k){return k[4];});
 var histL=klineMK.slice(0,12).reverse().map(function(k){return k[0].substring(0,7);});
 var predL=months.slice(nowMonth-1).concat(months.slice(0,nowMonth-1)).slice(0,6);
 var predV=[];
 for(var i=0;i<6;i++){var mi=(nowMonth-1+i)%12; predV.push(Number(fmt(currentPrice*(1+(sea[mi]||0)/100))));}
 var allL=histL.concat(predL);
 var histD=histC.concat(new Array(6).fill(null));
 var predD=(new Array(histC.length).fill(null)).concat(predV);
 if(histD.length>0&&predD.length>histC.length) predD[histC.length-1]=histD[histD.length-1];
 if(intelMonthlyInst)intelMonthlyInst.destroy();
 intelMonthlyInst=new Chart(document.getElementById('intelMonthlyChart'),{
  type:'line', data:{labels:allL, datasets:[
   {label:'历史收盘',data:histD,borderColor:'#2563eb',borderWidth:2,pointRadius:3,pointBackgroundColor:histD.map(function(v,i){return i<histC.length?'#2563eb':'transparent';}),fill:false,tension:0.2},
   {label:'6月预测',data:predD,borderColor:'#f59e0b',borderWidth:2,borderDash:[6,3],pointRadius:4,pointBackgroundColor:'#f59e0b',fill:false,tension:0.2}
  ]},
  options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'top',labels:{font:{size:11},usePointStyle:true}}},scales:{y:{ticks:{font:{size:10}}},x:{ticks:{font:{size:10}}}}}
 });
}

// Combined advice
var ndDir=pred?pred.next_day.direction:'neutral';
var curMonthSea=sea[nowMonth-1]||0;
var adviceH='';
if(ndDir==='bearish'&&curMonthSea<0){adviceH='<b style="color:#dc2626">短期看跌</b> + 当前月季节性偏弱('+fmt(curMonthSea)+'%) &rarr; <b>等待下月加仓窗口</b>';}
else if(ndDir==='bullish'){adviceH='<b style="color:#16a34a">短期看涨</b> &rarr; <b>耐心持有，选择最佳月份高位兑现</b>';}
else{adviceH='<b style="color:#f59e0b">信号中性</b> &rarr; 股息率'+fmt(dy)+'%(TTM推算)提供安全垫，<b>持有收息为主</b>';}
document.getElementById('intel-advice').innerHTML='<p>'+adviceH+'</p><p style="font-size:12px;color:#6b7280;margin-top:4px">高股息策略：稳拿分红 | 每日15:35自动更新</p>';

// Signal detail + learning statistics
var sigH='';
if(pred){
 var sig=pred.signals||{}, snames={macd:'MACD',rsi:'RSI',bollinger:'布林带',kdj:'KDJ',seasonal:'季节',atr:'ATR',money_flow:'资金'};
 sigH='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">';
 Object.keys(snames).forEach(function(k){
  var s=sig[k]||{}, dir=s.direction||'neutral', raw=s.raw||s.value||'--';
  var val=typeof raw==='number'?raw.toFixed(2):raw;
  sigH+='<div style="padding:8px;background:#f8fafc;border-radius:6px;font-size:12px;text-align:center">'+
   '<div style="font-weight:600">'+snames[k]+'</div>'+
   '<div style="font-size:16px;font-weight:700;color:'+(dir==='bullish'?'#dc2626':dir==='bearish'?'#16a34a':'#6b7280')+'">'+val+'</div></div>';
 });
 sigH+='</div>';

 // Accuracy stats from batch-loaded accuracy_stats
 var astats=D.accuracy_stats?.[code]||{}, last20=astats.last_20||{}, last60=astats.last_60||{};
 var dir20=last20.direction||{}, rng20=last20.range||{};
 var dir60=last60.direction||{}, rng60=last60.range||{};
 sigH+='<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:12px">'+
  '<div><b>准确率(近20):</b> 方向 <span class="'+(dir20.rate>=50?'up':'down')+'">'+(dir20.rate||0)+'%</span> ('+(dir20.correct||0)+'/'+(dir20.total||0)+') | 区间 <span class="'+(rng20.rate>=50?'up':'down')+'">'+(rng20.rate||0)+'%</span></div>'+
  '<div><b>准确率(近60):</b> 方向 <span class="'+(dir60.rate>=50?'up':'down')+'">'+(dir60.rate||0)+'%</span> ('+(dir60.correct||0)+'/'+(dir60.total||0)+')</div>'+
 '</div>';

 // Learning params: signal weights
 sigH+='<div class="collapsible"><b>📊 信号权重</b> <span style="color:#9ca3af;font-size:11px">点击展开</span>'+
  '<div class="collapsible-body" style="display:none;margin-top:8px">'+
  '<div style="font-size:11px;display:grid;grid-template-columns:repeat(5,1fr);gap:4px">'+
  '<div style="font-weight:600">信号</div><div style="font-weight:600">开盘段</div><div style="font-weight:600">午前段</div><div style="font-weight:600">午后段</div><div style="font-weight:600">尾盘段</div>';
  var learnAll=D.learning_params?.[code];
  if(learnAll&&learnAll.signal_weights){
   var sw=learnAll.signal_weights;
   var blocks=['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00'];
   Object.keys(snames).forEach(function(k){
    sigH+='<div>'+snames[k]+'</div>';
    blocks.forEach(function(b){
     var w=((sw[k]||{})[b]||1.0);
     sigH+='<div style="color:'+(w>1?'#dc2626':w<1?'#16a34a':'#6b7280')+'">'+w.toFixed(2)+'</div>';
    });
   });
  }else{
   sigH+='<div style="grid-column:span 5;color:#9ca3af">暂无学习参数</div>';
  }
  sigH+='</div>';
  // Confidence beta
  if(learnAll&&learnAll.confidence_beta){
   var cb=learnAll.confidence_beta;
   sigH+='<div style="margin-top:8px;font-size:11px"><b>置信度参数 (Beta-Binomial):</b> '+
    '看涨 α='+((cb.bullish||{}).alpha||1)+' β='+((cb.bullish||{}).beta||1)+' | '+
    '看跌 α='+((cb.bearish||{}).alpha||1)+' β='+((cb.bearish||{}).beta||1)+' | '+
    '更新次数='+(learnAll.update_count||0)+'</div>';
  }
 sigH+='</div>';

 // Detail signal table
 sigH+='<div class="collapsible"><b>📈 信号详情</b> <span style="color:#9ca3af;font-size:11px">点击展开</span>'+
  '<div class="collapsible-body" style="display:none;margin-top:8px">'+
  '<div style="font-size:11px;line-height:1.8">';
 Object.keys(snames).forEach(function(k){
  var s=sig[k]||{};
  sigH+='<div><b>'+snames[k]+'</b>: 方向='+(s.direction||'--')+' | 值='+(s.value||'--')+' | 原始='+(typeof s.raw==='number'?s.raw.toFixed(4):s.raw||'--')+'</div>';
 });
 sigH+='</div></div></div>';

}else{sigH='<div style="color:#9ca3af;font-size:13px">暂无信号数据，等待每日自动生成</div>';}
document.getElementById('intel-signal-detail').innerHTML=sigH;

// Bind collapse toggles (for signal weights and signal detail)
document.querySelectorAll('#intel-signal-detail .collapsible').forEach(function(el){
 el.addEventListener('click', function(){
  var body=this.querySelector('.collapsible-body');
  if(body) body.style.display=body.style.display==='none'?'block':'none';
 });
});

// History grid - 近20日预测 vs 实际
var allPreds=(D.daily_predictions||[]).filter(function(p){return p.code===code;}).sort(function(a,b){return b.date.localeCompare(a.date);});
var grid=document.getElementById('intel-hist-grid');
if(!allPreds.length){grid.innerHTML='<span style="font-size:12px;color:#9ca3af">暂无历史预测数据</span>';}
else{
 // Show last 20 with vs without actual data
 var recent20=allPreds.slice(0,20);
 var histH='<div style="display:flex;flex-direction:column;gap:3px;font-size:11px">';
 histH+='<div style="display:flex;gap:6px;font-weight:600;color:#6b7280;padding:2px 0;border-bottom:1px solid #e5e7eb">'+
  '<span style="width:90px">日期</span><span style="width:50px">预测</span><span style="width:50px">实际</span><span style="width:70px">区间命中</span><span style="width:100px">方向</span></div>';
 recent20.forEach(function(p){
  var act=p.actual||{};
  var predDir=p.next_day?p.next_day.direction:'--';
  var actualDir='--';
  if(act.next_day_direction_hit!=null){
   var prev=p.prev_close, actClose=act.close;
   actualDir=actClose>prev?'↗':actClose<prev?'↘':'→';
  }
  var dirHitSymbol='<span style="color:#d1d5db">⏳</span>'; // pending
  var rangeHitSymbol='<span style="color:#d1d5db">⏳</span>';
  var dirColor='#6b7280';
  if(act.next_day_direction_hit!=null){
   dirHitSymbol=act.next_day_direction_hit?'<span class="up">✓</span>':'<span class="down">✗</span>';
   dirColor=act.next_day_direction_hit?'#16a34a':'#dc2626';
  }
  if(act.daily_range_hit!=null){
   rangeHitSymbol=act.daily_range_hit?'<span class="up">✓</span>':'<span class="down">✗</span>';
  }
  histH+='<div style="display:flex;gap:6px;align-items:center;padding:2px 0;border-bottom:1px solid #f3f4f6">'+
   '<span style="width:90px;color:#6b7280">'+p.date+'</span>'+
   '<span style="width:50px;color:'+(predDir==='bullish'?'#dc2626':predDir==='bearish'?'#16a34a':'#6b7280')+'">'+dirIcon(predDir)+dirText(predDir).slice(0,1)+'</span>'+
   '<span style="width:50px;color:'+dirColor+'">'+actualDir+'</span>'+
   '<span style="width:70px">'+rangeHitSymbol+'</span>'+
   '<span style="width:100px;color:'+dirColor+'">'+dirHitSymbol+' '+(act.next_day_direction_hit!=null?(act.next_day_direction_hit?'命中':'未命中'):'待验证')+'</span></div>';
 });
 histH+='</div>';
 grid.innerHTML=histH;
}

// Dot grid summary below the table
var dotPreds=allPreds.slice(0,20).reverse();
var dotGrid=document.getElementById('intel-hist-dots');
if(!dotGrid){} // optional
}
