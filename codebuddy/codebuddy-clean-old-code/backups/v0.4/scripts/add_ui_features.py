"""Add management page + trigger buttons + API helpers to HTML."""
import re

with open("deliverables/bank-stock-system.html", "r", encoding="utf-8") as f:
    html = f.read()

# === 1. Add management nav button ===
html = html.replace(
    '<button class="nav-btn" onclick="showPage(\'expert\')">专家分析</button>\n',
    '<button class="nav-btn" onclick="showPage(\'expert\')">专家分析</button>\n<button class="nav-btn" onclick="showPage(\'manage\')">⚙ 管理</button>\n',
)

# === 2. Add trigger buttons to NEWS page ===
html = html.replace(
    '<!-- 页面6：新闻动态 -->\n<div id="page-news" class="page">\n<div class="tab-bar" style="margin-bottom:20px">\n<button class="tab-btn active" onclick="filterNews(\'all\')">全部</button>\n',
    '<!-- 页面6：新闻动态 -->\n<div id="page-news" class="page">\n<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">\n<div class="tab-bar" style="margin-bottom:0;flex:1">\n<button class="tab-btn active" onclick="filterNews(\'all\')">全部</button>\n',
)

# Find news page closing area and add refresh button
html = html.replace(
    '</div>\n</div>\n\n<!-- 页面7：专家分析 -->',
    '</div>\n<button class="tab-btn" onclick="triggerNews()" id="btn-news-trigger" style="margin-left:auto">🔄 刷新新闻</button>\n</div>\n<span id="news-status" style="font-size:11px;color:#9ca3af"></span>\n</div>\n\n<!-- 页面7：专家分析 -->',
)

# === 3. Add trigger button to PREDICT page ===
html = html.replace(
    '<!-- 页面5：预测与方案 -->\n<div id="page-predict" class="page">',
    '<!-- 页面5：预测与方案 -->\n<div id="page-predict" class="page">\n<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px"><div style="flex:1"></div>\n<button class="tab-btn" onclick="triggerPredict()" id="btn-pred-trigger">🔄 刷新预测</button>\n</div>\n<span id="pred-status" style="font-size:11px;color:#9ca3af"></span>',
)

# === 4. Add trigger button to EXPERT page ===
html = html.replace(
    '<!-- 页面7：专家分析 -->\n<div id="page-expert" class="page">\n<div class="tab-bar" style="margin-bottom:16px">',
    '<!-- 页面7：专家分析 -->\n<div id="page-expert" class="page">\n<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">\n<div id="expert-tabs" class="tab-bar" style="margin-bottom:0"></div>\n<button class="tab-btn" onclick="triggerExpert()" id="btn-expert-trigger">🧠 运行专家分析</button>\n</div>\n<span id="expert-status" style="font-size:11px;color:#9ca3af"></span>',
)

# === 5. Add MANAGEMENT page before disclaimer ===
mgmt_page = """
<!-- 页面9：系统管理 -->
<div id="page-manage" class="page">
<div class="card"><h2>📋 监控股票管理</h2>
<div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:flex-end">
<div>
<div style="font-size:11px;color:#6b7280;margin-bottom:4px">股票代码</div>
<input id="mgmt-code" placeholder="如 601398" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;width:100px">
</div>
<div>
<div style="font-size:11px;color:#6b7280;margin-bottom:4px">股票名称</div>
<input id="mgmt-name" placeholder="如 工商银行" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;width:120px">
</div>
<div>
<div style="font-size:11px;color:#6b7280;margin-bottom:4px">市场</div>
<select id="mgmt-market" style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px">
<option value="sh">沪市(sh)</option>
<option value="sz">深市(sz)</option>
</select>
</div>
<button class="tab-btn" onclick="addStock()" style="background:#2563eb;color:#fff;border-color:#2563eb">➕ 添加</button>
</div>
<div id="mgmt-list"></div>
<div id="mgmt-status" style="font-size:12px;color:#6b7280;margin-top:8px"></div>
</div>

<div class="card"><h2>🛠 系统操作</h2>
<div style="display:flex;gap:10px;flex-wrap:wrap">
<button class="tab-btn" onclick="triggerAudit()">📊 运行审计</button>
<button class="tab-btn" onclick="triggerReinject()">💉 注入数据到HTML</button>
</div>
<div id="sys-status" style="font-size:12px;color:#6b7280;margin-top:8px"></div>
</div>

<div class="card">
<h2>📡 服务器状态</h2>
<div id="server-status">检测中...</div>
</div>
</div>
"""
html = html.replace('<div class="disclaimer">', mgmt_page + '\n<div class="disclaimer">')

# === 6. Add API helper + management JS ===
api_js = """
// ===== API Helpers =====
const API_BASE = (location.hostname==='localhost'||location.hostname==='127.0.0.1') ? 'http://localhost:8765' : '';
function hasAPI(){ return !!API_BASE; }
async function apiCall(method, path, body){
 if(!hasAPI()){ alert('请在本地服务器模式下使用(访问 http://localhost:8765 而非直接打开文件)'); return null; }
 try{
  var opts={method:method,headers:{'Content-Type':'application/json'}};
  if(body) opts.body=JSON.stringify(body);
  var r=await fetch(API_BASE+path,opts);
  return await r.json();
 }catch(e){ console.error('API error:', e); return {success:false,error:e.message}; }
}

// ===== Management =====
function refreshWatchlistUI(){
 var wl=DATA.watchlist||[];
 var el=document.getElementById('mgmt-list');
 if(!el)return;
 el.innerHTML='<table><tr><th>代码</th><th>名称</th><th>市场</th><th>操作</th></tr>'+
  wl.map(function(s){return '<tr><td>'+s.code+'</td><td>'+s.name+'</td><td>'+s.market+'</td><td><a href=\"#\" onclick=\"removeStock(\\''+s.code+'\\')\" style=\"color:#dc2626;font-size:12px\">删除</a></td></tr>';}).join('')+'</table>';
}

async function addStock(){
 var code=document.getElementById('mgmt-code').value.trim();
 var name=document.getElementById('mgmt-name').value.trim();
 var market=document.getElementById('mgmt-market').value;
 if(!code||!name){ alert('请填写代码和名称'); return; }
 var st=document.getElementById('mgmt-status');
 st.textContent='添加中...';
 var r=await apiCall('POST','/api/watchlist/add',{code:code,name:name,market:market});
 if(r.success){
  location.reload();
 }else{
  st.textContent='错误: '+(r.error||'未知');
  alert(r.error||'添加失败');
 }
}

async function removeStock(code){
 if(!confirm('确定要移除 '+code+' ?')) return;
 var st=document.getElementById('mgmt-status');
 st.textContent='移除中...';
 var r=await apiCall('POST','/api/watchlist/remove',{code:code});
 if(r.success){ location.reload(); }
 else{ st.textContent='错误: '+(r.error||'未知'); }
}

// ===== Triggers =====
async function triggerNews(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('news-status');
 st.textContent='刷新中...';
 var r=await apiCall('POST','/api/trigger/news',{});
 st.textContent=r.success ? '刷新完成' : '失败: '+(r.error||'');
 setTimeout(function(){ st.textContent=''; }, 3000);
}

async function triggerPredict(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('pred-status');
 st.textContent='生成中...';
 var r=await apiCall('POST','/api/trigger/predict',{});
 st.textContent=r.success ? '预测已生成，刷新页面查看' : '失败: '+(r.error||'');
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
 st.textContent=r.success ? '审计完成:\\n'+r.output : '失败';
}

async function triggerReinject(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var st=document.getElementById('sys-status');
 st.textContent='注入中...';
 var r=await apiCall('POST','/api/trigger/predict',{});
 if(r.success) location.reload();
 else st.textContent='失败: '+(r.error||'');
}

// Server status check
(function(){
 setTimeout(function(){
  var el=document.getElementById('server-status');
  if(!el) return;
  if(hasAPI()){
   fetch(API_BASE+'/api/watchlist').then(function(r){return r.json();}).then(function(d){
    el.innerHTML='<span style=\"color:#16a34a\">已连接</span> - 端口8765，监控'+d.data.stocks.length+'只股票';
   }).catch(function(){ el.innerHTML='<span style=\"color:#dc2626\">连接失败</span>'; });
  }else{
   el.innerHTML='<span style=\"color:#f59e0b\">离线模式</span>（通过 file:// 打开，API不可用）';
  }
 }, 500);
})();
"""

html = html.replace('// ===== 日预测专题 =====', api_js + '\n// ===== 日预测专题 =====')

# === 7. Fix expert tabs (we replaced the hardcoded one earlier, but the div replacement conflicts) ===
# The expert-tabs div will be generated by genStockTabs via init, which we already set up

# Also set currentExpertStock default
html = html.replace(
    "let currentExpertStock=getWatchlist()[0]?.code||'601166', currentExpertIdx=0;",
    "let currentExpertStock=getWatchlist()[0]?.code||'601166';var currentExpertIdx=0;"
)

with open("deliverables/bank-stock-system.html", "w", encoding="utf-8") as f:
    f.write(html)

print("HTML updates applied: management page + trigger buttons + API helpers")
