
// ===== 持仓股价刷新 =====
async function refreshQuotes(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var btn = document.getElementById('btn-pos-refresh');
 var timeEl = document.getElementById('pos-refresh-time');
 if(btn.disabled) return; // 防重复触发
 btn.disabled = true;
 btn.textContent = '⏳ 刷新中...';
 timeEl.textContent = '';
 try{
  var r = await apiCall('POST','/api/v2/quotes/refresh',{});
  if(r && r.success){
   // Update quotes in DATA
   if(r.data && Object.keys(r.data).length > 0){
    var q = DATA.quotes || {};
    for(var code in r.data){
     q[code] = r.data[code];
    }
    DATA.quotes = q;
   }
   // Clear dividends cache so K-line trend chart uses fresh data
   delete _cache['dividends'];
   // Re-render current holdings table & summary stats
   renderHoldingsOverview();
   // Show refresh time
   var now = new Date();
   var hh = String(now.getHours()).padStart(2,'0');
   var mm = String(now.getMinutes()).padStart(2,'0');
   var ss = String(now.getSeconds()).padStart(2,'0');
   timeEl.textContent = '刷新于 ' + hh + ':' + mm + ':' + ss;
   timeEl.style.color = '#16a34a';
  } else {
   timeEl.textContent = '刷新失败: ' + (r && (r.error||r.message) || '未知');
   timeEl.style.color = '#dc2626';
  }
 }catch(e){
  timeEl.textContent = '错误: ' + e.message;
  timeEl.style.color = '#dc2626';
 }finally{
  btn.disabled = false;
  btn.textContent = '🔄 刷新股价';
 }
}

// 仅重新渲染持仓总览模块（不触发全局 init）
function renderHoldingsOverview(){
 var D = DATA, q = D.quotes || {};
 var cp = (D.positions||D).current_positions || {};
 var cl = (D.positions||D).closed_positions || {};

 var totalAsset = 0, totalCost = 0, totalRealized = 0, totalDiv = 0, totalFees = 0;
 var posHtml = '', divHtml = '';

 for(var code in cp){
  var p = cp[code];
  var price = (q[code] && q[code].price) || 0;
  var mv = price * p.qty;
  var pnl = mv - p.total_cost;
  var pnlPct = (pnl / p.total_cost * 100);
  totalAsset += mv;
  totalCost += p.total_cost;
  posHtml += '<tr><td><b>' + p.name + '</b>(' + code + ')</td>' +
   '<td>' + p.qty.toLocaleString() + '</td>' +
   '<td>' + fmt(p.avg_cost, 3) + '</td>' +
   '<td class="' + pnlClass(price - p.avg_cost) + '">' + fmt(price) + '</td>' +
   '<td>' + fmtMoney(mv) + '</td>' +
   '<td class="' + pnlClass(pnl) + '">' + pnlSign(pnl) + fmtMoney(Math.abs(pnl)) + '</td>' +
   '<td class="' + pnlClass(pnl) + '">' + pnlSign(pnlPct) + fmt(pnlPct) + '%</td>' +
   '<td class="up">' + ((q[code] && q[code].dy) || '--') + '%</td></tr>';
  for(var di = 0; di < (p.dividends || []).length; di++){
   var d = p.dividends[di];
   divHtml += '<tr><td>' + d.date + '</td><td>' + p.name + '</td><td>' + fmt(d.per_share || 0) + '</td><td>' + p.qty + '</td><td style="color:#dc2626;font-weight:600">+' + fmt(d.amount) + '</td></tr>';
   totalDiv += d.amount;
  }
  totalFees += (p.total_commission || 0) + (p.total_stamp_tax || 0) + (p.total_other_fees || 0);
 }

 document.getElementById('pos-table').innerHTML = posHtml;
 document.getElementById('div-table').innerHTML = divHtml;

 // Closed positions
 var closedHtml = '';
 for(var code in cl){
  var p = cl[code];
  var total = p.realized_pnl + p.dividends_total;
  totalRealized += total;
  closedHtml += '<tr><td>' + p.name + '(' + code + ')</td>' +
   '<td class="' + pnlClass(p.realized_pnl) + '">' + pnlSign(p.realized_pnl) + fmt(p.realized_pnl) + '</td>' +
   '<td style="color:#dc2626">+' + fmt(p.dividends_total) + '</td>' +
   '<td class="' + pnlClass(total) + '" style="font-weight:700">' + pnlSign(total) + fmt(total) + '</td></tr>';
  totalFees += (p.total_commission || 0) + (p.total_stamp_tax || 0) + (p.total_other_fees || 0);
 }
 document.getElementById('closed-table').innerHTML = closedHtml;

 // Summary cards
 var floatPnl = totalAsset - totalCost;
 document.getElementById('total-asset').textContent = fmtMoney(totalAsset);
 document.getElementById('total-cost-sub').textContent = '总成本 ' + fmtMoney(totalCost);
 document.getElementById('total-pnl').textContent = (floatPnl >= 0 ? '+' : '') + fmtMoney(Math.abs(floatPnl));
 document.getElementById('pnl-card').className = 'stat-item ' + (floatPnl >= 0 ? 'profit' : 'loss');
 document.getElementById('total-pnl-pct').textContent = (floatPnl >= 0 ? '+' : '') + fmt(floatPnl / totalCost * 100) + '%';
 document.getElementById('total-realized').textContent = '+' + fmtMoney(totalRealized + totalDiv);
 document.getElementById('total-fees').textContent = fmtMoney(totalFees);
}

// ===== Triggers =====
async function triggerNews(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('news-status');
 st.textContent='⏳ 刷新新闻中...';
 var r=await apiCall('POST','/api/trigger/news',{});
 st.textContent=r.success ? '✅ 新闻已刷新，正在重新加载...' : '❌ 失败: '+(r.error||r.message||'');
 if(r.success) setTimeout(function(){ init(); }, 1000);
}

async function triggerPredict(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('intel-status')||document.getElementById('sys-status');
 if(st) st.textContent='⏳ 正在刷新 (K线+新闻+预测)...';
 // Also show on sys-status if visible
 var st2=document.getElementById('sys-status');
 if(st2&&st2!==st) st2.textContent='⏳ 智能预测刷新中...';
 document.getElementById('btn-intel-trigger').disabled=true;
 try{
  var r=await apiCall('POST','/api/trigger/predict',{});
  if(r&&r.success){
   if(st) st.innerHTML='✅ 数据已刷新 ('+new Date().toLocaleTimeString()+')';
   // Re-initialize from API for full consistency
   setTimeout(function(){ init(); }, 500);
   // Clear status after 8s
   setTimeout(function(){if(st)st.textContent='';if(st2)st2.textContent='';},8000);
  }else{
   if(st) st.innerHTML='❌ 失败: '+(r&&(r.error||r.message)||'未知错误');
  }
 }catch(e){
  if(st) st.innerHTML='❌ 错误: '+e.message;
 }finally{
  document.getElementById('btn-intel-trigger').disabled=false;
 }
}

async function triggerExpert(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('expert-status');
 st.textContent='专家分析运行中，可能需要几分钟...';
 var r=await apiCall('POST','/api/trigger/expert',{code:currentExpertStock});
 st.textContent=r.success ? '分析完成' : '失败: '+(r.error||'');
}

async function triggerAudit(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('sys-status');
 st.textContent='审计中...';
 var r=await apiCall('GET','/api/audit');
 st.textContent=r.success ? '审计完成:\n'+r.output : '失败';
}

function handleFileSelect(){
 var file=document.getElementById('statement-file').files[0];
 if(!file) return;
 document.getElementById('upload-filename').textContent=file.name;
 uploadStatement(file);
}

async function uploadStatement(file){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('upload-status');
 st.style.color='#6b7280'; st.textContent='正在上传并解析...';
 var fd=new FormData(); fd.append('file',file);
 try{
  var r=await fetch(API_BASE+'/api/upload/statement',{method:'POST',body:fd});
  var d=await r.json();
  if(d.success){ st.style.color='#16a34a'; st.textContent=d.message||'更新完成'; setTimeout(function(){location.reload(true);},1500); }
  else{ st.style.color='#dc2626'; st.textContent='失败: '+(d.error||'未知'); }
 }catch(e){ st.style.color='#dc2626'; st.textContent='错误: '+e.message; }
}

// Server status check
(function(){
 setTimeout(function(){
  var el=document.getElementById('server-status');
  if(!el) return;
  if(hasAPI()&&DATA){
   var wl=DATA.watchlist||[];
   el.innerHTML='<span style="color:#16a34a">已连接</span> - 端口8765，监控'+wl.length+'只股票';
  }else if(hasAPI()){
   el.innerHTML='<span style="color:#f59e0b">加载中...</span>';
  }else{
   el.innerHTML='<span style="color:#f59e0b">离线模式</span>（通过 file:// 打开，API不可用）';
  }
 }, 800);
})();
