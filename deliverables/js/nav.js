
var pageGroups={overview:'trade',trades:'trade',fees:'trade',manage:'trade',intelligence:'analysis',expert:'analysis',news:'info',newsdetail:'info',kline:'info'};

function showPage(id){
document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
document.getElementById('page-'+id).classList.add('active');
// Highlight sub-item
document.querySelectorAll('.nav-sub').forEach(function(s){
var o=s.getAttribute('onclick')||'';
s.classList.toggle('active', o.includes("showPage('"+id+"')"));
});
// Highlight parent group
document.querySelectorAll('.nav-parent').forEach(function(p){
var g=p.parentElement.getAttribute('data-group');
p.classList.toggle('active', g===pageGroups[id]);
});
if(id==='kline'){renderKline(currentKlineCode);genStockTabs('kline-tabs','switchKline',currentKlineCode);}
if(id==='intelligence'){renderIntelligence(intelCode);genStockTabs('intel-tabs','switchIntelStock',intelCode);}
if(id==='expert'){renderExpertList();genStockTabs('expert-tabs','switchExpertStock',currentExpertStock);
// Patch codes from loaded watchlist
var wl = getWatchlist();
if(wl.length){ currentKlineCode=wl[0].code; currentPredCode=wl[0].code; currentExpertStock=wl[0].code; }}
if(id==='news'){genStockTabs('news-stock-tabs','switchNews',currentNewsFilter||'all');renderNews(currentNewsFilter||'all');}
if(id==='manage')refreshWatchlistUI();
}

// ===== 导航菜单交互 =====
var navOpenTimer=null,navCloseTimers={};

function openNavGroup(group){
clearTimeout(navOpenTimer);
clearTimeout(navCloseTimers&&navCloseTimers[group]);
var d=document.getElementById('drop-'+group);
var p=document.querySelector('.nav-group[data-group="'+group+'"] .nav-parent');
if(d)d.classList.add('show');
if(p)p.classList.add('open');
}

function closeNavGroup(group){
clearTimeout(navCloseTimers[group]);
navCloseTimers[group]=setTimeout(function(){
var d=document.getElementById('drop-'+group);
var p=document.querySelector('.nav-group[data-group="'+group+'"] .nav-parent');
if(d)d.classList.remove('show');
if(p)p.classList.remove('open');
},150);
}

function toggleNavGroup(group,event){
event.stopPropagation();
var d=document.getElementById('drop-'+group);
var p=document.querySelector('.nav-group[data-group="'+group+'"] .nav-parent');
if(d.classList.contains('show')){
d.classList.remove('show'); p.classList.remove('open');
}else{
// Close others first
document.querySelectorAll('.nav-dropdown').forEach(function(dd){dd.classList.remove('show');});
document.querySelectorAll('.nav-parent').forEach(function(pp){pp.classList.remove('open');});
d.classList.add('show'); p.classList.add('open');
}
}

function toggleNavMenu(){
document.getElementById('nav-menu').classList.toggle('open');
}


// Generate dynamic stock tabs
function genStockTabs(containerId, switchFn, activeCode){
var el=document.getElementById(containerId);
if(!el)return;
var wl=getWatchlist();
var html='';
wl.forEach(function(s,i){
html+='<button class="tab-btn'+(s.code===activeCode?' active':'')+'" onclick="'+switchFn+'(\''+s.code+'\', this)">'+s.name+'</button>';
});
el.innerHTML=html;
}
