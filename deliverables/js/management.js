

// ===== Management =====
function refreshWatchlistUI(){
 var wl=DATA.watchlist||[];
 var el=document.getElementById('mgmt-list');
 if(!el)return;
 el.innerHTML='<table><tr><th>代码</th><th>名称</th><th>市场</th><th>日K线</th><th>操作</th></tr>'+
  wl.map(function(s){
   var hasKline=DATA.kline_daily&&DATA.kline_daily[s.code]&&DATA.kline_daily[s.code].length>0;
   var ks=hasKline?'<span style="color:#16a34a;font-size:11px">'+DATA.kline_daily[s.code].length+'条</span>':'<span style="color:#dc2626;font-size:11px">无</span>';
   return '<tr><td>'+s.code+'</td><td><a href="#" onclick="switchToKline(\''+s.code+'\');return false">'+s.name+'</a></td><td>'+s.market+'</td><td>'+ks+'</td><td><a href="#" onclick="return removeStock(\''+s.code+'\')" style="color:#dc2626;font-size:12px">删除</a></td></tr>';
  }).join('')+'</table>';
}

function switchToKline(code){
 showPage('kline');
 genStockTabs('kline-tabs','switchKline',code);
 renderKline(code);
}

// ===== 股票自动补全 (全A股API搜索) =====
var acIndex=-1, acSelected=null, acTimer=null, acCache={};

function acSearch(q){
 clearTimeout(acTimer);
 acTimer=setTimeout(function(){_acDoSearch(q);},200);
}

async function _acDoSearch(q){
 acIndex=-1; acSelected=null;
 var dd=document.getElementById('ac-dropdown');
 if(!q||q.trim().length<1){ dd.classList.remove('show'); return; }
 q=q.trim();
 var key=q.toLowerCase();
 if(acCache[key]){ _acRender(q,acCache[key]); return; }
 try{
  var r=await fetch(API_BASE+'/api/search/stocks?q='+encodeURIComponent(q));
  var d=await r.json();
  var items=(d&&d.data)||[];
  acCache[key]=items;
  _acRender(q,items);
 }catch(e){ dd.innerHTML='<div class="ac-empty">搜索失败，请重试</div>'; dd.classList.add('show'); }
}

function _acRender(q,items){
 var dd=document.getElementById('ac-dropdown');
 if(!items.length){ dd.innerHTML='<div class="ac-empty">未找到匹配股票</div>'; dd.classList.add('show'); return; }
 var h='';
 for(var i=0;i<Math.min(items.length,12);i++){
  var st=items[i], nm=st.name, cd=st.code, mkt=st.market==='sz'?'深':'沪';
  var rx=new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi');
  var hnm=nm.replace(rx,'<span class="ac-highlight">$1</span>');
  var hcd=cd.replace(rx,'<span class="ac-highlight">$1</span>');
  h+='<div class="ac-item" data-idx="'+i+'" data-code="'+cd+'" data-name="'+nm+'" data-mkt="'+mkt+'" onmousedown="acSelect('+i+')" onmouseenter="acHover('+i+')">';
  h+='<span class="ac-name">'+hnm+'</span>';
  h+='<span><span class="ac-code">'+hcd+'</span><span class="ac-mkt">'+mkt+'</span></span></div>';
 }
 dd.innerHTML=h; dd.classList.add('show');
}

function acKeydown(e){
 var dd=document.getElementById('ac-dropdown');
 if(!dd.classList.contains('show')) return;
 var items=dd.querySelectorAll('.ac-item');
 if(e.key==='ArrowDown'){ e.preventDefault(); acIndex=Math.min(acIndex+1,items.length-1); acUpdateHover(items); }
 else if(e.key==='ArrowUp'){ e.preventDefault(); acIndex=Math.max(acIndex-1,0); acUpdateHover(items); }
 else if(e.key==='Enter'){ e.preventDefault(); if(acIndex>=0&&items[acIndex]) acSelect(acIndex); }
 else if(e.key==='Escape'){ dd.classList.remove('show'); }
}

function acUpdateHover(items){ for(var i=0;i<items.length;i++) items[i].classList.toggle('active',i===acIndex); if(acIndex>=0) items[acIndex].scrollIntoView({block:'nearest'}); }
function acHover(idx){ acIndex=idx; acUpdateHover(document.querySelectorAll('#ac-dropdown .ac-item')); }

function acSelect(idx){
 var items=document.querySelectorAll('#ac-dropdown .ac-item');
 var el=items[idx]; if(!el) return;
 var code=el.getAttribute('data-code'), name=el.getAttribute('data-name');
 var market=el.getAttribute('data-mkt')==='深'?'sz':'sh';
 acSelected={code:code,name:name,market:market};
 document.getElementById('mgmt-code').value=name+' ('+code+')';
 document.getElementById('mgmt-market').value=market;
 document.getElementById('ac-dropdown').classList.remove('show');
 acIndex=-1;
}

function acBlur(){ setTimeout(function(){ document.getElementById('ac-dropdown').classList.remove('show'); },200); }

// ===== 添加/删除股票 =====
async function addStock(){
 var code='', name='', market=document.getElementById('mgmt-market').value;
 if(acSelected){ code=acSelected.code; name=acSelected.name; market=acSelected.market; }
 else{
  var v=document.getElementById('mgmt-code').value.trim();
  var m=v.match(/^(\d{6})$/);
  if(m){ code=m[1]; } else{ alert('请输入股票代码，或从下拉列表中选择'); return; }
 }
 if(!code||!name){ alert('请选择一只股票'); return; }
 var st=document.getElementById('mgmt-status');
 st.textContent='添加中...';
 var r=await apiCall('POST','/api/v2/watchlist',{code:code,name:name,market:market});
 if(r.success){
  location.reload(true);
 }else{
  st.textContent='错误: '+(r.error||'未知');
  alert(r.error||'添加失败');
 }
}

function removeStock(code){
 if(!confirm('确定要移除 '+code+' ?')) return false;
 var st=document.getElementById('mgmt-status');
 st.textContent='移除中...';
 apiCall('POST','/api/watchlist/remove',{code:code}).then(function(r){
  if(r&&r.success){ location.reload(true); }
  else{ st.textContent='错误: '+((r&&r.error)||'未知'); }
 });
 return false;
}
