
// ===== V0.7 DataStore Module (Pure API) =====
var DATA = {}; // populated by init() via API calls


let CONFIG = {}; // System config from /api/v2/config
// Same-origin API: page served by server.py => API at same host:port
const API_BASE = location.protocol.startsWith('http') ? '' : '';
function hasAPI(){ return !!(API_BASE !== undefined); }
async function apiCall(method, path, body){
 if(!hasAPI()){ alert('请在本地服务器模式下使用(访问 http://localhost:8765 而非直接打开文件)'); return null; }
 try{
  var opts={method:method,headers:{'Content-Type':'application/json'}};
  if(body) opts.body=JSON.stringify(body);
  var r=await fetch(API_BASE+path,opts);
  return await r.json();
 }catch(e){ console.error('API error:', e); return {success:false,error:e.message}; }
}

// Cache for API responses
const _cache = {};
async function loadData(key, endpoint){
 if(_cache[key]) return _cache[key];
 try{
  var r=await apiCall('GET', endpoint);
  if(r&&r.success){ _cache[key]=r.data; return r.data; }
  console.warn('loadData['+key+'] failed:', r);
  return null;
 }catch(e){ console.warn('loadData['+key+'] error:', e); return null; }
}


let klineChartInst, monthlyChartInst, seasonalChartInst, predChartInst, timelineChartInst, feeChartInst, feeTrendChartInst, dividendYieldChartInst;

function getStockName(code){
if(!DATA||!DATA.watchlist)return code;
const wl=DATA.watchlist;
const s=wl.find(function(x){return x.code===code});
return s?s.name:code;
}
function getWatchlist(){return (DATA&&DATA.watchlist)||[];}

// Default codes from watchlist first entry, not hardcoded
function _firstWatchCode(){ var wl=getWatchlist(); return wl.length?wl[0].code:null; }
let currentKlineCode = _firstWatchCode(), currentPredCode = _firstWatchCode();

function fmt(n,d=2){return n==null?'--':Number(n).toFixed(d)}
function fmtMoney(n){return n>=10000?(n/10000).toFixed(2)+'万':fmt(n)}
// 红涨绿跌：盈利=红色(up)，亏损=绿色(down)
function pnlClass(v){return v>0?'up':v<0?'down':'flat'}
function pnlSign(v){return v>0?'+':''}

async function init(){
var st=document.getElementById('server-status');
if(hasAPI()){
 if(st)st.innerHTML='<span style="color:#f59e0b">并行加载中 (15路API)...</span>';
 try{
  // V0.6: Parallel independent API loading
  var [cfg, wl, quotes, kd, km, pc, pcl, trades, divs, preds, sea, news, expert, accStats, learn] =
    await Promise.all([
      loadData('config', '/api/v2/config'),
      loadData('watchlist', '/api/v2/watchlist'),
      loadData('quotes', '/api/v2/quotes'),
      loadData('kline_daily', '/api/v2/kline/daily'),
      loadData('kline_monthly', '/api/v2/kline/monthly'),
      loadData('pos_current', '/api/v2/positions/current'),
      loadData('pos_closed', '/api/v2/positions/closed'),
      loadData('trades', '/api/v2/trades'),
      loadData('dividends', '/api/v2/dividends'),
      loadData('predictions', '/api/v2/predictions/daily'),
      loadData('seasonal', '/api/v2/seasonal'),
      loadData('news', '/api/v2/news'),
      loadData('expert', '/api/v2/expert'),
      loadData('accuracy', '/api/v2/accuracy'),
      loadData('learning', '/api/v2/learning'),
    ]);

  // Store config globally
  CONFIG = cfg || {};

  // Build compat DATA object (same shape as old /api/v2/init response)
  DATA = {
    account: CONFIG.account || '51312640',
    broker: CONFIG.broker || '广发证券',
    generated: new Date().toISOString().slice(0,16).replace('T',' '),
    watchlist: wl || [],
    quotes: quotes || {},
    positions: {
      current_positions: pc || {},
      closed_positions: pcl || {},
      all_trades: trades || []
    },
    kline_daily: kd || {},
    kline: km || {},
    seasonal: sea || {},
    daily_predictions: preds || [],
    news: news || [],
    expert_reports: expert || [],
    accuracy_stats: accStats || {},
    learning_params: learn || {}
  };

  // V0.6 fix: Inject dividends_{code} keys for K-line dividend markers
  if(divs && divs.length){
    var divByCode = {};
    divs.forEach(function(d){
      if(!divByCode[d.code]) divByCode[d.code] = [];
      divByCode[d.code].push({date: d.date, amount: d.amount, price: d.price, per_share: d.per_share||0});
    });
    Object.keys(divByCode).forEach(function(code){
      DATA['dividends_'+code] = divByCode[code];
    });
  }

  // V0.6 fix: Inject monthly_changes_{code} from loaded monthly kline
  if(km){
    Object.keys(km).forEach(function(code){
      var bars = km[code] || [];
      // kline_monthly format: [date, open, high, low, close, volume, change_pct]
      DATA['monthly_changes_'+code] = bars
        .filter(function(b){ return b[6] !== 0; })
        .map(function(b){ return [b[0], b[6]]; }); // [date, change_pct]
    });
  }

  // Patch default codes from watchlist
  var firstCode = _firstWatchCode();
  if(firstCode){
    currentKlineCode = firstCode;
    currentPredCode = firstCode;
    if(typeof intelCode !== 'undefined') intelCode = firstCode;
    if(typeof currentExpertStock !== 'undefined') currentExpertStock = firstCode;
    if(typeof dpCode !== 'undefined') dpCode = firstCode;
  }

 }catch(e){ console.error('Init error:', e); if(st)st.innerHTML='<span style="color:#dc2626">加载失败: '+e.message+'</span>'; return; }
// After data loads, re-render the currently visible page with real data
var activePage=document.querySelector('.page.active');
if(activePage){
 var pid=activePage.id.replace('page-','');
 showPage(pid);
}
// Re-run renderAll now that DATA has real API data
if(typeof renderAll==='function'){renderAll();}
}
// Fallback: file:// mode uses whatever DATA was preset
if(DATA&&DATA.watchlist&&!DATA.watchlist.length){
 if(st)st.innerHTML='<span style="color:#f59e0b">离线模式（无数据）</span>';
 // Still try to render empty state
}

if(st&&hasAPI()) st.innerHTML='<span style="color:#16a34a">已连接</span> - 端口8765，监控'+(DATA.watchlist?DATA.watchlist.length:0)+'只股票';

// trades and sea already loaded via var at Promise.all; extract only legacy-compat fields from DATA
const D=DATA, q=D.quotes||{}, cp=(D.positions||D).current_positions||{}, cl=(D.positions||D).closed_positions||{};
// Null-safe fallbacks for API-sourced data
trades = trades || [];
sea = sea || {};
news = news || [];
expert = expert || [];
preds = preds || [];
divs = divs || [];
accStats = accStats || {};
learn = learn || {};


}
// ===== Initial render orchestrator =====
function renderAll(){
if(!DATA||!DATA.watchlist||!DATA.watchlist.length){return;}
try{

const D=DATA, q=D.quotes||{}, cp=(D.positions||D).current_positions||{}, cl=(D.positions||D).closed_positions||{};
var trades=(D.positions||D).all_trades||[], sea=D.seasonal||{}, news=D.news||[], expert=D.expert_reports||[];
var preds=D.daily_predictions||[], divs=D.dividends||[], accStats=D.accuracy_stats||{}, learn=D.learning_params||{};

// 持仓总览
let totalAsset=0, totalCost=0, totalRealized=0, totalDiv=0, totalFees=0;
let posHtml='', divHtml='';

for(const[code,p] of Object.entries(cp)){
const price=q[code]?.price||0;
const mv=price*p.qty;
const pnl=mv-p.total_cost;
const pnlPct=(pnl/p.total_cost*100);
totalAsset+=mv; totalCost+=p.total_cost;
posHtml+=`<tr><td><b>${p.name}</b>(${code})</td><td>${p.qty.toLocaleString()}</td><td>${fmt(p.avg_cost,3)}</td><td class="${pnlClass(price-p.avg_cost)}">${fmt(price)}</td><td>${fmtMoney(mv)}</td><td class="${pnlClass(pnl)}">${pnlSign(pnl)}${fmtMoney(Math.abs(pnl))}</td><td class="${pnlClass(pnl)}">${pnlSign(pnlPct)}${fmt(pnlPct)}%</td><td class="up" title="公式计算值（TTM推算）&#10;基于最近12个月分红与当前股价推算&#10;与公司实际公布股息率可能存在差异">${q[code]?.dy||'--'}%</td></tr>`;
for(const d of p.dividends){
// 分红是收益，用红色
divHtml+=`<tr><td>${d.date}</td><td>${p.name}</td><td>${fmt(d.per_share||0)}</td><td>${p.qty}</td><td style="color:#dc2626;font-weight:600">+${fmt(d.amount)}</td></tr>`;
totalDiv+=d.amount;
}
totalFees+=p.total_commission+p.total_stamp_tax+p.total_other_fees;
}
// 已清仓股票的分红明细也加入"分红收入明细"表格
for(const[code,p] of Object.entries(cl)){
if(p.dividends && p.dividends.length){
for(const d of p.dividends){
divHtml+=`<tr><td>${d.date}</td><td>${p.name} <span style="color:#9ca3af;font-size:11px">已清仓</span></td><td>${fmt(d.per_share||0)}</td><td>--</td><td style="color:#dc2626;font-weight:600">+${fmt(d.amount)}</td></tr>`;
totalDiv+=d.amount;
}
}
}
document.getElementById('pos-table').innerHTML=posHtml;
document.getElementById('div-table').innerHTML=divHtml;

let closedHtml='';
for(const[code,p] of Object.entries(cl)){
const total=p.realized_pnl+p.dividends_total;
totalRealized+=total;
closedHtml+=`<tr><td>${p.name}(${code})</td><td class="${pnlClass(p.realized_pnl)}">${pnlSign(p.realized_pnl)}${fmt(p.realized_pnl)}</td><td style="color:#dc2626">+${fmt(p.dividends_total)}</td><td class="${pnlClass(total)}" style="font-weight:700">${pnlSign(total)}${fmt(total)}</td></tr>`;
}
document.getElementById('closed-table').innerHTML=closedHtml;
// 已清仓的手续费也加入累计
for(const[code,p] of Object.entries(cl)){
totalFees+=p.total_commission+p.total_stamp_tax+(p.total_other_fees||0);
}

const floatPnl=totalAsset-totalCost;
document.getElementById('total-asset').textContent=fmtMoney(totalAsset);
document.getElementById('total-cost-sub').textContent='总成本 '+fmtMoney(totalCost);
document.getElementById('total-pnl').textContent=(floatPnl>=0?'+':'')+fmtMoney(Math.abs(floatPnl));
// 浮盈用红色(profit)，浮亏用绿色(loss)
document.getElementById('pnl-card').className='stat-item '+(floatPnl>=0?'profit':'loss');
document.getElementById('total-pnl-pct').textContent=(floatPnl>=0?'+':'')+fmt(floatPnl/totalCost*100)+'%';
document.getElementById('total-realized').textContent='+'+fmtMoney(totalRealized+totalDiv);
// 手续费是支出，用绿色
document.getElementById('total-fees').textContent=fmtMoney(totalFees);

// K线
var _kc = _firstWatchCode(); if(_kc) renderKline(_kc);

// 交易记录
let tradeHtml='';
trades.forEach(t=>{
const typeClass=t.type==='证券买入'?'tag-buy':t.type==='证券卖出'?'tag-sell':'tag-div';
// 清算金额：正值(收入)=红色(up)，负值(支出)=绿色(down)
tradeHtml+=`<tr><td>${t.date}</td><td>${t.time}</td><td>${t.name}</td><td><span class="tag ${typeClass}">${t.type}</span></td><td>${Math.abs(t.qty).toLocaleString()}</td><td>${fmt(t.price)}</td><td>${fmt(t.commission)}</td><td>${fmt(t.stamp_tax)}</td><td class="${t.settlement>=0?'up':'down'}">${fmt(t.settlement)}</td></tr>`;
});
document.getElementById('trade-table').innerHTML=tradeHtml;

// 交易时间线
renderTimeline(trades);

// 手续费分析
let allCommission=0, allStamp=0, allOther=0;
const feeByStock={};
for(const[code,p] of Object.entries(cp)){
const c=p.total_commission,s=p.total_stamp_tax,o=p.total_other_fees;
if(!feeByStock[code])feeByStock[code]={name:p.name,commission:c,stamp:s,other:o,total:c+s+o,buyAmount:0,sellAmount:0};
allCommission+=c;allStamp+=s;allOther+=o;
let buyAmt=0,sellAmt=0;
p.trades.forEach(t=>{if(t.type==='证券买入')buyAmt+=Math.abs(t.qty)*t.price;else if(t.type==='证券卖出')sellAmt+=Math.abs(t.qty)*t.price;});
feeByStock[code].buyAmount=buyAmt;feeByStock[code].sellAmount=sellAmt;
}
for(const[code,p] of Object.entries(cl)){
const c=p.total_commission,s=p.total_stamp_tax,o=p.total_other_fees||0;
if(!feeByStock[code])feeByStock[code]={name:p.name,commission:c,stamp:s,other:o,total:c+s+o,buyAmount:0,sellAmount:0};
else{feeByStock[code].commission+=c;feeByStock[code].stamp+=s;feeByStock[code].other+=o;feeByStock[code].total+=c+s+o;}
allCommission+=c;allStamp+=s;allOther+=o;
let buyAmt2=0,sellAmt2=0;
(p.trades||[]).forEach(t=>{if(t.type==='证券买入')buyAmt2+=Math.abs(t.qty)*t.price;else if(t.type==='证券卖出')sellAmt2+=Math.abs(t.qty)*t.price;});
feeByStock[code].buyAmount+=buyAmt2;feeByStock[code].sellAmount+=sellAmt2;
}
document.getElementById('fee-commission').textContent=fmtMoney(allCommission);
document.getElementById('fee-stamp').textContent=fmtMoney(allStamp);
document.getElementById('fee-other').textContent=fmtMoney(allOther);
document.getElementById('fee-total').textContent=fmtMoney(allCommission+allStamp+allOther);

let feeHtml='';
for(const[code,f] of Object.entries(feeByStock)){
const estRate=f.buyAmount>0?(f.commission/f.buyAmount*100):0;
feeHtml+=`<tr><td>${f.name}(${code})</td><td>${fmt(f.commission)}</td><td>${fmt(f.stamp)}</td><td>${fmt(f.other)}</td><td style="font-weight:600">${fmt(f.total)}</td><td>佣金率≈${fmt(estRate,4)}%</td></tr>`;
}
document.getElementById('fee-table').innerHTML=feeHtml;

renderFeeChart(feeByStock);
renderFeeTrend(trades);

// 预测
var _pc = _firstWatchCode(); if(_pc) renderIntelligence(_pc);

// 新闻
renderNews('all');

// 专家分析
var _ec = _firstWatchCode(); if(_ec) currentExpertStock = _ec;
renderExpertList();

// 动态生成股票切换标签
genStockTabs('kline-tabs','switchKline',currentKlineCode);
genStockTabs('expert-tabs','switchExpertStock',currentExpertStock);
// Patch codes from loaded watchlist
var wl = getWatchlist();
if(wl.length){ currentKlineCode=wl[0].code; currentPredCode=wl[0].code; currentExpertStock=wl[0].code; }
// 新闻inline标签
genStockTabs('news-stock-tabs','switchNews',currentKlineCode);

// 管理页列表
if(document.getElementById('mgmt-list')) refreshWatchlistUI();

}catch(e){console.warn("renderAll error:",e);}
}
