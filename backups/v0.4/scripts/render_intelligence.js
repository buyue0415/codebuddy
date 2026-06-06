// ===== 智能预测 (合并预测与方案+日预测) =====
var intelCode=getWatchlist()[0]?.code||'601166', intelDate=null, intelDailyInst=null, intelMonthlyInst=null;
var intelTab='daily';

function switchIntelStock(code){intelCode=code;renderIntelligence(code);}
function selectIntelDate(date){intelDate=date;renderIntelligence(intelCode);}
function switchIntelTab(tab){
 intelTab=tab;
 var dBox=document.getElementById('intel-chart-daily'), mBox=document.getElementById('intel-chart-monthly');
 dBox.style.display=tab==='daily'?'block':'none'; mBox.style.display=tab==='monthly'?'block':'none';
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
  '<div style="font-size:12px;color:#6b7280;margin-top:10px;line-height:1.6;text-align:left">'+(nd.advice||'')+'</div>';
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
 '<div>股息率 <span class="up">'+fmt(dy)+'%</span></div></div>';

// Chart
document.getElementById('intel-chart-title').textContent=name+' 走势图';
if(intelDailyInst)intelDailyInst.destroy();
if(pred){
 var hourly=pred.hourly||[], prevClose=pred.prev_close||0;
 var dlbls=['09:30','10:30','11:30','13:00','14:00','15:00'];
 var dLine=[prevClose], dHigh=[], dLow=[], lastV=prevClose;
 hourly.forEach(function(h){lastV=h.pred_close||lastV; dLine.push(lastV); dHigh.push(h.pred_high); dLow.push(h.pred_low);});
 dLine.push(lastV);
 intelDailyInst=new Chart(document.getElementById('intelDailyChart'),{
  type:'line', data:{labels:dlbls, datasets:[
   {label:'预测上限',data:[null,dHigh[0],dHigh[1],dHigh[2],dHigh[3],null],borderColor:'rgba(239,68,68,.3)',borderWidth:1,pointRadius:0,fill:false},
   {label:'预测下限',data:[null,dLow[0],dLow[1],dLow[2],dLow[3],null],borderColor:'rgba(34,197,94,.3)',borderWidth:1,pointRadius:0,fill:false},
   {label:'预测价',data:dLine,borderColor:'#2563eb',borderWidth:2,pointRadius:3,fill:false}
  ]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{font:{size:11}}}},scales:{y:{ticks:{font:{size:10}}}}}
 });
}
if(intelMonthlyInst)intelMonthlyInst.destroy();
var klineMK=D.kline[code]||[], histC=klineMK.slice(-12).map(function(k){return k[4];});
var histL=klineMK.slice(-12).map(function(k){return k[0].substring(0,7);});
var predL=months.slice(nowMonth-1).concat(months.slice(0,nowMonth-1)).slice(0,6);
var predV=[];
for(var i=0;i<6;i++){var mi=(nowMonth-1+i)%12; predV.push(Number(fmt(currentPrice*(1+(sea[mi]||0)/100))));}
var allL=histL.concat(predL);
var histD=histC.concat(new Array(6).fill(null));
var predD=(new Array(histC.length).fill(null)).concat(predV);
if(histD.length>0&&predD.length>histC.length) predD[histC.length-1]=histC[histC.length-1];
intelMonthlyInst=new Chart(document.getElementById('intelMonthlyChart'),{
 type:'line', data:{labels:allL, datasets:[
  {label:'历史收盘',data:histD,borderColor:'#2563eb',borderWidth:2,pointRadius:2,fill:false},
  {label:'6月预测',data:predD,borderColor:'#f59e0b',borderWidth:2,borderDash:[4,2],pointRadius:3,fill:false}
 ]},
 options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{font:{size:11}}}}}
});
document.getElementById('intel-chart-daily').style.display=intelTab==='daily'?'block':'none';
document.getElementById('intel-chart-monthly').style.display=intelTab==='monthly'?'block':'none';

// Combined advice
var ndDir=pred?pred.next_day.direction:'neutral';
var curMonthSea=sea[nowMonth-1]||0;
var adviceH='';
if(ndDir==='bearish'&&curMonthSea<0){adviceH='<b style="color:#dc2626">短期看跌</b> + 当前月季节性偏弱('+fmt(curMonthSea)+'%) &rarr; <b>等待下月加仓窗口</b>';}
else if(ndDir==='bullish'){adviceH='<b style="color:#16a34a">短期看涨</b> &rarr; <b>耐心持有，选择最佳月份高位兑现</b>';}
else{adviceH='<b style="color:#f59e0b">信号中性</b> &rarr; 股息率'+fmt(dy)+'%提供安全垫，<b>持有收息为主</b>';}
document.getElementById('intel-advice').innerHTML='<p>'+adviceH+'</p><p style="font-size:12px;color:#6b7280;margin-top:4px">高股息策略：稳拿分红 | 每日15:35自动更新</p>';

// Signal detail
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
 var astats=D.accuracy_stats?.[code]||{}, last20=astats.last_20||{};
 sigH+='<div><b>准确率(近20):</b> 方向 '+Number((last20.direction||{}).rate*100).toFixed(0)+'% | 区间 '+Number((last20.range||{}).rate*100).toFixed(0)+'%</div>';
}else{sigH='<div style="color:#9ca3af;font-size:13px">暂无信号数据，等待每日自动生成</div>';}
document.getElementById('intel-signal-detail').innerHTML=sigH;

// History grid
var allPreds=(D.daily_predictions||[]).filter(function(p){return p.code===code;}).sort(function(a,b){return b.date.localeCompare(a.date);}).slice(0,20).reverse();
var grid=document.getElementById('intel-hist-grid');
if(!allPreds.length){grid.innerHTML='<span style="font-size:12px;color:#9ca3af">暂无历史数据</span>';}
else{grid.innerHTML='<div class="dp-hist-grid">'+allPreds.map(function(p){var act=p.actual||{};var cls='pending';if(act.next_day_direction_hit!=null)cls=act.next_day_direction_hit?'hit':'miss';return '<div class="dp-hist-dot '+cls+'" title="'+p.date+'"></div>';}).join('')+'</div>';}
}
