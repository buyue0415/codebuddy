

function filterNews(filter,btn){
currentNewsFilter=filter;
closeDatePicker();
// Keep today's date for default date picker; only reset when switching to major
currentNewsSelDate = (filter==='major') ? '' : getTodayStr();
_ndpViewYear=0;_ndpViewMonth=0;
document.querySelectorAll('#page-news .tab-btn').forEach(b=>b.classList.remove('active'));
if(btn) btn.classList.add('active');
renderNews(filter);
}

function getTodayStr(){var d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
function getCurMonthStr(){var d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');}

var currentNewsFiltered = []; // Store filtered news for detail view
var currentNewsSelDate = getTodayStr(); // Default to today (YYYY-MM-DD)
var _ndpViewYear = 0, _ndpViewMonth = 0; // Calendar view state
var _ndpDateSet = {}; // Set of dates that have news (for markers)

function openNewsDetail(idx){
if(!currentNewsFiltered.length || idx<0 || idx>=currentNewsFiltered.length) return;
var n = currentNewsFiltered[idx];
var el = document.getElementById('nd-content');
var stockName = getStockName(n.code);
var summary = n.summary || '';
var hasUrl = n.url && n.url.indexOf('http')===0;

el.innerHTML = ''
  + '<div class="nd-card">'
  + '  <div class="nd-card-header">'
  + '    <div class="nd-title">' + escapeHtml(n.title) + '</div>'
  + '  </div>'
  + '  <div class="nd-badge-row">'
  + '    <span class="nd-badge stock">' + escapeHtml(stockName) + '(' + n.code + ')' + '</span>'
  + '    <span class="nd-badge date">📅 ' + n.date + '</span>'
  + '    <span class="nd-badge source">📰 ' + escapeHtml(n.source||'综合') + '</span>'
  + '    <span class="nd-badge ' + (n.sentiment==='positive'?'pos':n.sentiment==='negative'?'neg':'neu') + '">'
  +       ({positive:'📈 利好',negative:'📉 利空',neutral:'➖ 中性'}[n.sentiment]||'中性') + '</span>'
  + (n.major ? '<span class="nd-badge major">⚠️ 重大事件</span>' : '')
  + '  </div>'
  + '  <div class="nd-divider"></div>'
  + '  <div class="nd-body-wrap">'
  + (summary
      ? '<div class="nd-body"><div class="nd-summary-label">📋 摘要</div>' + escapeHtml(summary) + '</div>'
      : '')
  + '  </div>'
  + (hasUrl
      ? '<div class="nd-actions"><a class="nd-link-btn primary" href="' + n.url + '" target="_blank" rel="noopener">🔗 查看原文</a></div>'
      : '')
  + '</div>'
  + renderRelatedNews(n.code, n.id, currentNewsFiltered.indexOf(n));
showPage('newsdetail');
document.getElementById('nd-loading').classList.remove('show');
}

function renderRelatedNews(code, excludeId, excludeIdx){
if(!code) return '';
var related = [];
try{
  related = currentNewsFiltered.filter(function(x,i){
    return i !== excludeIdx && x.code === code && x.id !== excludeId;
  }).slice(0,5);
}catch(e){}
if(!related.length) return '';
var stockName = getStockName(code);
return '<div class="nd-related"><h3>📌 ' + escapeHtml(stockName) + ' 更多新闻</h3>'
+ related.map(function(x){
var idx = (typeof currentNewsFiltered !== 'undefined') ? currentNewsFiltered.indexOf(x) : -1;
if(idx < 0) return '';
return '<div class="nd-rel-item" onclick="openNewsDetail('+idx+')">'
+ '<div class="nd-rel-date">'+x.date+'</div>'
+ '<div>'
+ '<div class="nd-rel-title">'+escapeHtml(x.title)+'</div>'
+ '<div class="nd-rel-source">'+(x.source||'综合')+'</div>'
+ '</div></div>';
}).join('') + '</div>';
}

function switchNews(code){
currentNewsFilter=code;
currentNewsSelDate=getTodayStr();
closeDatePicker();
_ndpViewYear=0;_ndpViewMonth=0;
document.querySelectorAll('#page-news .tab-btn').forEach(b=>b.classList.remove('active'));
var tabs=document.querySelectorAll('#news-stock-tabs .tab-btn');
tabs.forEach(function(b){
var o=b.getAttribute('onclick')||'';
b.classList.toggle('active', o.indexOf(code)!==-1);
});
renderNews(code);
}

function renderNews(filter){
var news=DATA.news||[];
var filtered=filter==='all'?news:filter==='major'?news.filter(function(n){return n.major;}):news.filter(function(n){return n.code===filter;});
filtered.sort(function(a,b){return b.date.localeCompare(a.date);});

// Save all unique dates for calendar markers + chart data (independent of date filter)
_ndpDateSet = {};
_sentimentChartData = filtered;
_sentimentChartData.forEach(function(n){if(n.date) _ndpDateSet[n.date]=true;});

// Apply date sub-filter if active (exact match YYYY-MM-DD) — for timeline only
if(currentNewsSelDate){
  var dFiltered = filtered.filter(function(n){return n.date===currentNewsSelDate;});
  if(dFiltered.length) filtered = dFiltered;
  else filtered = [];
}
currentNewsFiltered = filtered; // Store for detail page (date-filtered)

// Render date picker
renderDatePickerControl(filter);

var container=document.getElementById('news-timeline');
if(!filtered.length){
  var msg = currentNewsSelDate ? ('该日期暂无新闻数据') : '暂无新闻数据，等待每日自动更新';
  container.innerHTML='<div class="news-empty">'+msg+'</div>';
}else{
container.innerHTML=filtered.map(function(n,i){
var stockName=getStockName(n.code);
return '<div class="news-item'+(n.major?' major':'')+'" data-news-idx="'+i+'" style="animation-delay:'+(i*0.04)+'s">'
+'<div class="news-date">'+n.date+'</div>'
+'<div class="news-body">'
+'<div class="news-title"><span class="stock-tag tag-'+n.code+'">'+stockName+'</span><a href="javascript:openNewsDetail('+i+')" style="color:inherit;text-decoration:none">'+n.title+'</a></div>'
+(n.summary?'<div class="news-summary">'+n.summary+'</div>':'')
+'<div class="news-source">'+(n.source||'综合')+' '+(n.major?'<span style="color:#dc2626;font-weight:600">⚠ 重大事件</span>':'')+'</div>'
+'</div></div>';
}).join('');
}
// Chart uses stock-filtered data (not date-filtered), independent filtering
renderNewsSentiment(_sentimentChartData);
}

// ——— Date Picker ———
var preDateFiltered = [];

function renderDatePickerControl(filter){
var dropEl=document.getElementById('news-date-drop');
if(!dropEl) return;
if(filter==='all' || filter==='major'){
dropEl.classList.remove('show');
return;
}
// Only show if there are dates in the data
var hasDates = Object.keys(_ndpDateSet).length > 0;
if(!hasDates){ dropEl.classList.remove('show'); return; }
dropEl.classList.add('show');

// Update trigger text — always show selected date (defaults to today)
var textEl=document.getElementById('ndp-text');
if(textEl) textEl.textContent = currentNewsSelDate || '选择日期';
// Trigger date filter on initial load
if(currentNewsSelDate && filter!=='all'){/* filter already applied by renderNews */}
// Init calendar view to the selected date or the latest available date
var latestDate = Object.keys(_ndpDateSet).sort().pop() || '';
if(!_ndpViewYear){
  if(currentNewsSelDate){
    _ndpViewYear = parseInt(currentNewsSelDate.substring(0,4));
    _ndpViewMonth = parseInt(currentNewsSelDate.substring(5,7));
  } else if(latestDate){
    _ndpViewYear = parseInt(latestDate.substring(0,4));
    _ndpViewMonth = parseInt(latestDate.substring(5,7));
  } else {
    var d=new Date();
    _ndpViewYear = d.getFullYear();
    _ndpViewMonth = d.getMonth() + 1;
  }
}
// Build the calendar for the current view month
buildDatePickerCalendar();
}

function buildDatePickerCalendar(){
var titleEl=document.getElementById('ndp-nav-title');
var daysEl=document.getElementById('ndp-days');
if(!titleEl||!daysEl) return;
titleEl.textContent=_ndpViewYear+'年'+_ndpViewMonth+'月';

var first=new Date(_ndpViewYear,_ndpViewMonth-1,1);
var last=new Date(_ndpViewYear,_ndpViewMonth,0);
var startDay=first.getDay(); // 0=Sun
// Convert to Mon=0 ... Sun=6
var offset=(startDay===0)?6:startDay-1;

var today=new Date();
var todayStr=today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');

var cells='';
// Empty cells before first day
for(var e=0;e<offset;e++) cells+='<div class="ndp-day other"></div>';

// Days of current month
for(var d=1;d<=last.getDate();d++){
  var dateStr=_ndpViewYear+'-'+String(_ndpViewMonth).padStart(2,'0')+'-'+String(d).padStart(2,'0');
  var cls='ndp-day';
  if(dateStr===todayStr) cls+=' today';
  if(_ndpDateSet[dateStr]) cls+=' has-news';
  if(currentNewsSelDate===dateStr) cls+=' selected';
  cells+='<div class="'+cls+'" onclick="datePickerSelect(\''+dateStr+'\','+d+')">'+d+'</div>';
}

// Fill remaining cells to complete grid (optional - 6 rows max)
var total=offset+last.getDate();
var remainder=total%7;
if(remainder>0){for(var r=0;r<7-remainder;r++) cells+='<div class="ndp-day other"></div>';}

daysEl.innerHTML=cells;
}

function toggleDatePicker(e){
if(e) e.stopPropagation();
var panel=document.getElementById('ndp-panel');
var trigger=document.querySelector('.ndp-trigger');
if(!panel) return;
var isOpen=panel.classList.contains('open');
if(isOpen){ closeDatePicker(); }
else{
  // Build calendar if needed
  if(!_ndpViewYear) buildDatePickerCalendar();
  panel.classList.add('open');
  trigger.classList.add('active');
}
}

function closeDatePicker(){
var panel=document.getElementById('ndp-panel');
var trigger=document.querySelector('.ndp-trigger');
if(panel) panel.classList.remove('open');
if(trigger) trigger.classList.remove('active');
}

function datePickerPrevMonth(){
_ndpViewMonth--;
if(_ndpViewMonth<1){_ndpViewMonth=12;_ndpViewYear--;}
buildDatePickerCalendar();
}

function datePickerNextMonth(){
_ndpViewMonth++;
if(_ndpViewMonth>12){_ndpViewMonth=1;_ndpViewYear++;}
buildDatePickerCalendar();
}

function datePickerSelect(dateStr,day){
currentNewsSelDate=dateStr;
closeDatePicker();
// Update trigger text
var textEl=document.getElementById('ndp-text');
if(textEl) textEl.textContent=dateStr;
renderNews(currentNewsFilter);
}

// Click outside to close calendar
document.addEventListener('click',function(e){
var drop=document.getElementById('news-date-drop');
if(!drop) return;
if(!drop.contains(e.target)) closeDatePicker();
});

function filterNewsByDate(date){
currentNewsSelDate=date||'';
renderNews(currentNewsFilter);
}

function escapeHtml(s){
if(!s) return '';
return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let newsSentimentChartInst;
var _sentimentMonth = getCurMonthStr(); // Default to current month
var _sentimentChartData = []; // Stock-filtered data for chart (independent of date filter)

function changeSentimentMonth(val){
_sentimentMonth = val || getCurMonthStr();
renderNewsSentiment(_sentimentChartData);
}

function renderNewsSentiment(news){
var selEl = document.getElementById('sentiment-month-select');
// Build month options from stock-filtered data
if(selEl && news && news.length){
  var months = [], seen = {};
  news.forEach(function(n){
    if(n.date && n.date.length>=7){
      var m = n.date.substring(0,7);
      if(!seen[m]){ seen[m]=true; months.push(m); }
    }
  });
  months.sort().reverse();
  // Ensure current month is always in list
  var curMonth = getCurMonthStr();
  if(months.indexOf(curMonth)===-1) months.unshift(curMonth);
  var html = '';
  months.forEach(function(m){
    var label = parseInt(m.substring(0,4))+'年'+parseInt(m.substring(5,7))+'月';
    var sel = (m===_sentimentMonth)?' selected':'';
    html += '<option value="'+m+'"'+sel+'>'+label+'</option>';
  });
  if(selEl.innerHTML !== html) selEl.innerHTML = html;
  selEl.value = _sentimentMonth;
}

if(newsSentimentChartInst) newsSentimentChartInst.destroy();

if(!news || !news.length){
  var emptyChart = document.getElementById('newsSentimentChart');
  if(emptyChart){
    var ctx = emptyChart.getContext('2d');
    ctx.clearRect(0,0,emptyChart.width,emptyChart.height);
  }
  return;
}

// Always show day-by-day breakdown for the selected month
var byDay = {};
news.forEach(function(n){
  if(!n.date || n.date.indexOf(_sentimentMonth)!==0) return;
  if(!byDay[n.date]) byDay[n.date] = {positive:0,negative:0,neutral:0};
  if(n.sentiment==='positive') byDay[n.date].positive++;
  else if(n.sentiment==='negative') byDay[n.date].negative++;
  else byDay[n.date].neutral++;
});
var labels = Object.keys(byDay).sort();
if(!labels.length){
  var emptyChart = document.getElementById('newsSentimentChart');
  if(emptyChart){
    var ctx = emptyChart.getContext('2d');
    ctx.clearRect(0,0,emptyChart.width,emptyChart.height);
  }
  return;
}
newsSentimentChartInst = new Chart(document.getElementById('newsSentimentChart'),{
  type:'bar',
  data:{
    labels: labels.map(function(d){ return parseInt(d.substring(8,10))+'日'; }),
    datasets:[
      {label:'利好',data:labels.map(function(l){return byDay[l].positive;}),backgroundColor:'#dc2626'},
      {label:'利空',data:labels.map(function(l){return byDay[l].negative;}),backgroundColor:'#16a34a'},
      {label:'中性',data:labels.map(function(l){return byDay[l].neutral;}),backgroundColor:'#6b7280'}
    ]
  },
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{
      legend:{position:'top'},
      title:{display:true,text:labels.length+'天·'+parseInt(_sentimentMonth.substring(0,4))+'年'+parseInt(_sentimentMonth.substring(5,7))+'月情绪分布',font:{size:13}}
    },
    scales:{
      x:{stacked:true,title:{display:true,text:'日期'}},
      y:{stacked:true,beginAtZero:true,ticks:{callback:function(v){return v+'条';}}}
    }
  }
});
}
