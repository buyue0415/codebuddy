"""重新生成HTML，修正配色（红涨绿跌）并注入修正后数据"""
import json

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    data = json.dumps(json.load(f), ensure_ascii=False)

html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>银行股投资管理系统</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;color:#1f2937}
.nav{background:linear-gradient(135deg,#1a3a5c,#2563eb);padding:0 24px;display:flex;align-items:center;height:56px;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.15)}
.nav .logo{color:#fff;font-size:18px;font-weight:700;margin-right:40px;letter-spacing:1px}
.nav .logo span{color:#60a5fa}
.nav-btn{background:none;border:none;color:rgba(255,255,255,.7);font-size:14px;padding:16px 20px;cursor:pointer;transition:all .2s;border-bottom:3px solid transparent}
.nav-btn:hover{color:#fff;background:rgba(255,255,255,.1)}
.nav-btn.active{color:#fff;border-bottom-color:#60a5fa;background:rgba(255,255,255,.08)}
.page{display:none;max-width:1200px;margin:24px auto;padding:0 24px}
.page.active{display:block}
.card{background:#fff;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card h2{font-size:18px;margin-bottom:16px;color:#1e3a5f;border-left:4px solid #2563eb;padding-left:12px}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px}
.stat-item{color:#fff;border-radius:12px;padding:20px;position:relative;overflow:hidden}
.stat-item::after{content:'';position:absolute;top:-20px;right:-20px;width:80px;height:80px;background:rgba(255,255,255,.08);border-radius:50%}
.stat-item .label{font-size:12px;opacity:.8;margin-bottom:4px}
.stat-item .value{font-size:28px;font-weight:700}
.stat-item .sub{font-size:12px;opacity:.7;margin-top:4px}
.stat-item.blue{background:linear-gradient(135deg,#1e40af,#3b82f6)}
.stat-item.profit{background:linear-gradient(135deg,#991b1b,#dc2626)}
.stat-item.loss{background:linear-gradient(135deg,#047857,#10b981)}
.stat-item.expense{background:linear-gradient(135deg,#047857,#10b981)}
.stat-item.neutral{background:linear-gradient(135deg,#b45309,#f59e0b)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#f8fafc;padding:10px 12px;text-align:left;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0;white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid #f1f5f9}
tr:hover td{background:#f8fafc}
/* 红涨绿跌：涨/收益用红色，跌/亏损/支出用绿色 */
.up{color:#dc2626}.down{color:#16a34a}.flat{color:#6b7280}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.tag-buy{background:#dcfce7;color:#166534}.tag-sell{background:#fee2e2;color:#991b1b}.tag-div{background:#dbeafe;color:#1e40af}
.tab-bar{display:flex;gap:8px;margin-bottom:16px}
.tab-btn{padding:8px 20px;border:1px solid #d1d5db;border-radius:8px;background:#fff;cursor:pointer;font-size:13px;transition:all .2s}
.tab-btn.active{background:#2563eb;color:#fff;border-color:#2563eb}
.pred-card{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.pred-item{background:#f8fafc;border-radius:8px;padding:12px;text-align:center;border:1px solid #e2e8f0}
.pred-item .month{font-size:12px;color:#6b7280;margin-bottom:4px}
.pred-item .price{font-size:20px;font-weight:700;color:#1e40af}
.pred-item .range{font-size:11px;color:#6b7280;margin-top:4px}
.chart-box{position:relative;height:380px}
.fee-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.fee-item{text-align:center;padding:16px;background:#f8fafc;border-radius:8px}
.fee-item .amount{font-size:24px;font-weight:700;color:#16a34a}
.fee-item .name{font-size:12px;color:#6b7280;margin-top:4px}
.disclaimer{color:#9ca3af;font-size:12px;text-align:center;padding:24px;border-top:1px solid #e5e7eb;margin-top:24px}
.summary-row{display:flex;gap:20px;align-items:stretch}
.summary-row .card{flex:1;margin-bottom:0}
@media(max-width:768px){
.stat-grid{grid-template-columns:repeat(2,1fr)}
.pred-card{grid-template-columns:repeat(3,1fr)}
.fee-grid{grid-template-columns:1fr}
.summary-row{flex-direction:column}
}
</style>
</head>
<body>

<nav class="nav">
<div class="logo"><span>📊</span> 银行股投资管理系统</div>
<button class="nav-btn active" onclick="showPage('overview')">持仓总览</button>
<button class="nav-btn" onclick="showPage('kline')">K线走势</button>
<button class="nav-btn" onclick="showPage('trades')">交易记录</button>
<button class="nav-btn" onclick="showPage('fees')">手续费分析</button>
<button class="nav-btn" onclick="showPage('predict')">预测与方案</button>
</nav>

<!-- 页面1：持仓总览 -->
<div id="page-overview" class="page active">
<div class="stat-grid">
<div class="stat-item blue">
<div class="label">总资产（持仓市值）</div>
<div class="value" id="total-asset">--</div>
<div class="sub" id="total-cost-sub"></div>
</div>
<div class="stat-item" id="pnl-card">
<div class="label">浮动盈亏</div>
<div class="value" id="total-pnl">--</div>
<div class="sub" id="total-pnl-pct"></div>
</div>
<div class="stat-item profit">
<div class="label">已实现盈亏+分红</div>
<div class="value" id="total-realized">--</div>
<div class="sub">含已清仓股票</sub>
</div>
<div class="stat-item expense">
<div class="label">累计手续费</div>
<div class="value" id="total-fees">--</div>
<div class="sub">佣金+印花税+其他</sub>
</div>
</div>

<div class="summary-row" style="margin-bottom:20px">
<div class="card">
<h2>当前持仓</h2>
<table>
<thead><tr><th>股票</th><th>持仓</th><th>成本价</th><th>现价</th><th>市值</th><th>浮盈亏</th><th>盈亏%</th><th>股息率</th></tr></thead>
<tbody id="pos-table"></tbody>
</table>
</div>
</div>

<div class="summary-row" style="margin-bottom:20px">
<div class="card">
<h2>已清仓股票</h2>
<table>
<thead><tr><th>股票</th><th>交易盈亏</th><th>分红收入</th><th>合计收益</th></tr></thead>
<tbody id="closed-table"></tbody>
</table>
</div>
</div>

<div class="card">
<h2>分红收入明细</h2>
<table>
<thead><tr><th>日期</th><th>股票</th><th>每股派息</th><th>持仓股数</th><th>分红金额</th></tr></thead>
<tbody id="div-table"></tbody>
</table>
</div>
</div>

<!-- 页面2：K线走势 -->
<div id="page-kline" class="page">
<div class="card">
<div class="tab-bar">
<button class="tab-btn active" onclick="switchKline('601166')">兴业银行</button>
<button class="tab-btn" onclick="switchKline('600036')">招商银行</button>
</div>
<h2 id="kline-title">兴业银行 3年月度走势</h2>
<div class="chart-box"><canvas id="klineChart"></canvas></div>
</div>
<div class="card">
<h2 id="monthly-title">月度涨跌幅</h2>
<div class="chart-box" style="height:300px"><canvas id="monthlyChart"></canvas></div>
</div>
<div class="card">
<h2>季节性规律（月均涨跌幅 %）</h2>
<div class="chart-box" style="height:280px"><canvas id="seasonalChart"></canvas></div>
</div>
</div>

<!-- 页面3：交易记录 -->
<div id="page-trades" class="page">
<div class="card">
<h2>全部交易流水（广发证券 51312640）</h2>
<div style="overflow-x:auto">
<table>
<thead><tr><th>日期</th><th>时间</th><th>股票</th><th>类型</th><th>数量</th><th>价格</th><th>佣金</th><th>印花税</th><th>清算金额</th></tr></thead>
<tbody id="trade-table"></tbody>
</table>
</div>
</div>
<div class="card">
<h2>交易时间线</h2>
<div class="chart-box" style="height:300px"><canvas id="timelineChart"></canvas></div>
</div>
</div>

<!-- 页面4：手续费分析 -->
<div id="page-fees" class="page">
<div class="stat-grid" style="grid-template-columns:repeat(3,1fr)">
<div class="stat-item expense">
<div class="label">总佣金</div>
<div class="value" id="fee-commission">--</div>
<div class="sub">净佣金合计</div>
</div>
<div class="stat-item expense">
<div class="label">总印花税</div>
<div class="value" id="fee-stamp">--</div>
<div class="sub">卖出时收取</div>
</div>
<div class="stat-item expense">
<div class="label">其他费用</div>
<div class="value" id="fee-other">--</div>
<div class="sub">过户费+证管费+经手费</div>
</div>
</div>
<div class="card">
<h2>各股票费用明细</h2>
<table>
<thead><tr><th>股票</th><th>佣金</th><th>印花税</th><th>其他费用</th><th>合计</th><th>费率估算</th></tr></thead>
<tbody id="fee-table"></tbody>
</table>
</div>
<div class="card">
<h2>费用构成图</h2>
<div class="chart-box" style="height:300px"><canvas id="feeChart"></canvas></div>
</div>
<div class="card">
<h2>逐月费用趋势</h2>
<div class="chart-box" style="height:280px"><canvas id="feeTrendChart"></canvas></div>
</div>
</div>

<!-- 页面5：预测与方案 -->
<div id="page-predict" class="page">
<div class="tab-bar">
<button class="tab-btn active" onclick="switchPred('601166')">兴业银行</button>
<button class="tab-btn" onclick="switchPred('600036')">招商银行</button>
</div>
<div class="card">
<h2>未来6个月价格预测</h2>
<div class="pred-card" id="pred-cards"></div>
</div>
<div class="card">
<h2 id="pred-chart-title">兴业银行 预测走势</h2>
<div class="chart-box"><canvas id="predChart"></canvas></div>
</div>
<div class="card">
<h2>📋 操作方案</h2>
<div style="line-height:2;font-size:14px">
<table style="width:100%">
<thead><tr><th>时段</th><th>操作</th><th>逻辑</th></tr></thead>
<tbody>
<tr><td><b>5月底-6月</b></td><td><span class="tag tag-buy">🟢 加仓窗口</span></td><td>当前处于预测最低区间附近，若触及下限（兴业16.4/招行35.5）是极佳低吸机会</td></tr>
<tr><td><b>7月</b></td><td><span class="tag tag-div">🟡 持有观望</span></td><td>全年强势月，预测中枢兴业18.6(+6.3%)、招行39.8(+6.5%)，享受反弹</td></tr>
<tr><td><b>8月</b></td><td><span class="tag tag-div">🟡 持有不动</span></td><td>小幅回落月，7月冲高后正常调整，高股息策略不折腾</td></tr>
<tr><td><b>9月</b></td><td><span class="tag tag-div">🟡 持有</span></td><td>预测回升至兴业19.0、招行40.5</td></tr>
<tr><td><b>10月</b></td><td><span class="tag tag-sell">🔴 减仓窗口</span></td><td>全年最强月，预测峰值兴业19.5(+11.4%)、招行41.2(+10.2%)，可逢高减1/4锁利</td></tr>
<tr><td><b>11月</b></td><td><span class="tag tag-div">🟡 观察</span></td><td>预测开始回落，幅度不大</td></tr>
</tbody>
</table>
</div>
</div>
<div class="card">
<h2>🎯 关键价位监控</h2>
<table>
<thead><tr><th>股票</th><th>现价</th><th>加仓触发价</th><th>减仓触发价</th><th>股息率</th></tr></thead>
<tbody>
<tr><td>兴业银行</td><td class="down">17.33</td><td class="down">≤16.50</td><td class="up">≥19.50</td><td class="up">9.38%</td></tr>
<tr><td>招商银行</td><td class="down">37.17</td><td class="down">≤36.00</td><td class="up">≥41.00</td><td class="up">8.11%</td></tr>
</tbody>
</table>
</div>
<div class="card">
<h2>💡 核心判断</h2>
<div style="line-height:2.2;font-size:14px">
<p><b>1.</b> <span class="up">现在不该卖</span> — 两支股都在回调低位，股息率处历史高位（兴业9.38%接近极值），卖掉等于放弃高息筹码</p>
<p><b>2.</b> <span class="down">6月是最佳加仓月</span> — 预测6月可能还有最后一跌（兴业下限16.4、招行下限35.5）</p>
<p><b>3.</b> <span class="up">10月是全年最佳兑现窗口</span> — 如做波段，10月是全年预测峰值</p>
<p><b>4.</b> 你的策略是高股息，不是短线 — 稳拿分红比折腾波段更符合策略定位</p>
<p style="font-size:16px;font-weight:700;color:#1e40af;margin-top:8px">一句话：6月低吸，7-10月持有吃息，10月可小幅减仓锁利，其余时间躺平收分红。</p>
</div>
</div>
</div>

<div class="disclaimer">
⚠️ 本系统数据来源于广发证券对账单及NeoData金融数据服务（月度K线，非日K）。预测基于历史季节性模型推演，置信区间±8-10%，实际走势可能偏离中枢。以上内容不构成任何投资建议，投资有风险，决策需谨慎。
</div>

<script>
const DATA = {INJECTED_DATA};
let klineChartInst, monthlyChartInst, seasonalChartInst, predChartInst, timelineChartInst, feeChartInst, feeTrendChartInst;
let currentKlineCode = '601166', currentPredCode = '601166';

function fmt(n,d=2){return n==null?'--':Number(n).toFixed(d)}
function fmtMoney(n){return n>=10000?(n/10000).toFixed(2)+'万':fmt(n)}
// 红涨绿跌：盈利=红色(up)，亏损=绿色(down)
function pnlClass(v){return v>0?'up':v<0?'down':'flat'}
function pnlSign(v){return v>0?'+':''}

function showPage(id){
document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
document.getElementById('page-'+id).classList.add('active');
document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
event.target.classList.add('active');
}

function init(){
const D=DATA, q=D.quotes, cp=D.current_positions, cl=D.closed_positions, trades=D.all_trades, pred=D.predictions, sea=D.seasonal;
const names={'601166':'兴业银行','600036':'招商银行','600900':'长江电力','601939':'建设银行','601398':'工商银行','600050':'中国联通'};

// 持仓总览
let totalAsset=0, totalCost=0, totalRealized=0, totalDiv=0, totalFees=0;
let posHtml='', divHtml='';

for(const[code,p] of Object.entries(cp)){
const price=q[code]?.price||0;
const mv=price*p.qty;
const pnl=mv-p.total_cost;
const pnlPct=(pnl/p.total_cost*100);
totalAsset+=mv; totalCost+=p.total_cost;
posHtml+=`<tr><td><b>${p.name}</b>(${code})</td><td>${p.qty.toLocaleString()}</td><td>${fmt(p.avg_cost,3)}</td><td class="${pnlClass(price-p.avg_cost)}">${fmt(price)}</td><td>${fmtMoney(mv)}</td><td class="${pnlClass(pnl)}">${pnlSign(pnl)}${fmtMoney(Math.abs(pnl))}</td><td class="${pnlClass(pnl)}">${pnlSign(pnlPct)}${fmt(pnlPct)}%</td><td class="up">${q[code]?.dy||'--'}%</td></tr>`;
for(const d of p.dividends){
// 分红是收益，用红色
divHtml+=`<tr><td>${d.date}</td><td>${p.name}</td><td>${fmt(d.price)}</td><td>${p.qty}</td><td style="color:#dc2626;font-weight:600">+${fmt(d.amount)}</td></tr>`;
totalDiv+=d.amount;
}
totalFees+=p.total_commission+p.total_stamp_tax+p.total_other_fees;
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
renderKline('601166');

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
const c=p.total_commission,s=p.total_stamp_tax,o=0;
if(!feeByStock[code])feeByStock[code]={name:p.name,commission:c,stamp:s,other:o,total:c+s+o,buyAmount:0,sellAmount:0};
else{feeByStock[code].commission+=c;feeByStock[code].stamp+=s;feeByStock[code].total+=c+s+o;}
allCommission+=c;allStamp+=s;
}
document.getElementById('fee-commission').textContent=fmtMoney(allCommission);
document.getElementById('fee-stamp').textContent=fmtMoney(allStamp);
document.getElementById('fee-other').textContent=fmtMoney(allOther);

let feeHtml='';
for(const[code,f] of Object.entries(feeByStock)){
const estRate=f.buyAmount>0?(f.commission/f.buyAmount*100):0;
feeHtml+=`<tr><td>${f.name}(${code})</td><td>${fmt(f.commission)}</td><td>${fmt(f.stamp)}</td><td>${fmt(f.other)}</td><td style="font-weight:600">${fmt(f.total)}</td><td>佣金率≈${fmt(estRate,4)}%</td></tr>`;
}
document.getElementById('fee-table').innerHTML=feeHtml;

renderFeeChart(feeByStock);
renderFeeTrend(trades);

// 预测
renderPred('601166');
}

function renderKline(code){
const D=DATA, kline=D.kline[code]||[], divs=D['dividends_'+code]||[], mc=D['monthly_changes_'+code]||[];
const names={'601166':'兴业银行','600036':'招商银行'};
const name=names[code];

document.getElementById('kline-title').textContent=name+' 3年月度走势';
document.getElementById('monthly-title').textContent=name+' 月度涨跌幅';

const labels=kline.map(k=>k[0]);
const closes=kline.map(k=>k[4]);
const sma20=calcSMA(closes,7);
const sma60=calcSMA(closes,14);

const divPoints=closes.map((c,i)=>{const d=divs.find(dv=>dv.date&&labels[i].startsWith(dv.date.substring(0,7)));return d?c:null;});

if(klineChartInst)klineChartInst.destroy();
klineChartInst=new Chart(document.getElementById('klineChart'),{
type:'line',
data:{labels,datasets:[
{label:'收盘价',data:closes,borderColor:'#2563eb',borderWidth:2,pointRadius:1,tension:.3,fill:false},
{label:'SMA20',data:sma20,borderColor:'#f59e0b',borderWidth:1,pointRadius:0,borderDash:[4,2],fill:false},
{label:'SMA60',data:sma60,borderColor:'#ef4444',borderWidth:1,pointRadius:0,borderDash:[6,3],fill:false},
{label:'分红',data:divPoints,borderColor:'#dc2626',backgroundColor:'#dc2626',pointRadius:8,pointStyle:'triangle',showLine:false}
]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:11}}}},scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},y:{ticks:{font:{size:10}}}}}
});

// 月度涨跌：红涨绿跌
if(monthlyChartInst)monthlyChartInst.destroy();
const mcLabels=mc.map(m=>m[0]);
const mcData=mc.map(m=>m[1]);
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
}

function switchKline(code){currentKlineCode=code;document.querySelectorAll('#page-kline .tab-btn').forEach(b=>b.classList.remove('active'));event.target.classList.add('active');renderKline(code);}

function calcSMA(data,period){
const result=[];
for(let i=0;i<data.length;i++){
if(i<period-1){result.push(null);continue;}
let sum=0;for(let j=i-period+1;j<=i;j++)sum+=data[j];
result.push(+(sum/period).toFixed(2));
}
return result;
}

function renderTimeline(trades){
const byDate={};
trades.forEach(t=>{
const m=t.date.substring(0,7);
if(!byDate[m])byDate[m]={buy:0,sell:0,div:0};
if(t.type==='证券买入')byDate[m].buy+=Math.abs(t.settlement);
else if(t.type==='证券卖出')byDate[m].sell+=Math.abs(t.settlement);
else if(t.type==='股息入账')byDate[m].div+=Math.abs(t.settlement);
});
const labels=Object.keys(byDate).sort();
if(timelineChartInst)timelineChartInst.destroy();
timelineChartInst=new Chart(document.getElementById('timelineChart'),{
type:'bar',
data:{labels,datasets:[
{label:'买入(万)',data:labels.map(l=>+(byDate[l].buy/10000).toFixed(2)),backgroundColor:'#3b82f6'},
{label:'卖出(万)',data:labels.map(l=>+(byDate[l].sell/10000).toFixed(2)),backgroundColor:'#f59e0b'},
// 分红是收益，用红色
{label:'分红(万)',data:labels.map(l=>+(byDate[l].div/10000).toFixed(2)),backgroundColor:'#dc2626'}
]},
options:{responsive:true,maintainAspectRatio:false,scales:{x:{stacked:false},y:{ticks:{callback:v=>v+'万'}}},plugins:{legend:{position:'top'}}}
});
}

function renderFeeChart(feeByStock){
const labels=[],commission=[],stamp=[],other=[];
for(const[code,f] of Object.entries(feeByStock)){
labels.push(f.name);
commission.push(f.commission);
stamp.push(f.stamp);
other.push(f.other);
}
if(feeChartInst)feeChartInst.destroy();
feeChartInst=new Chart(document.getElementById('feeChart'),{
type:'doughnut',
data:{labels:['佣金','印花税','其他费用'],datasets:[{data:[commission.reduce((a,b)=>a+b,0),stamp.reduce((a,b)=>a+b,0),other.reduce((a,b)=>a+b,0)],backgroundColor:['#16a34a','#f59e0b','#6b7280']}]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'}}}
});
}

function renderFeeTrend(trades){
const byMonth={};
trades.forEach(t=>{
const m=t.date.substring(0,7);
if(!byMonth[m])byMonth[m]={commission:0,stamp:0,other:0};
byMonth[m].commission+=t.commission;
byMonth[m].stamp+=t.stamp;
});
const labels=Object.keys(byMonth).sort();
if(feeTrendChartInst)feeTrendChartInst.destroy();
feeTrendChartInst=new Chart(document.getElementById('feeTrendChart'),{
type:'bar',
data:{labels,datasets:[
// 费用是支出，用绿色系
{label:'佣金',data:labels.map(l=>+byMonth[l].commission.toFixed(2)),backgroundColor:'#16a34a'},
{label:'印花税',data:labels.map(l=>+byMonth[l].stamp.toFixed(2)),backgroundColor:'#f59e0b'}
]},
options:{responsive:true,maintainAspectRatio:false,scales:{x:{stacked:true},y:{stacked:true,ticks:{callback:v=>v+'元'}}},plugins:{legend:{position:'top'}}}
});
}

function renderPred(code){
const pred=DATA.predictions[code]||[];
const kline=DATA.kline[code]||[];
const names={'601166':'兴业银行','600036':'招商银行'};
const name=names[code];
const q=DATA.quotes[code];

let cards='';
pred.forEach(p=>{
const chg=((p.pred-q.price)/q.price*100).toFixed(1);
cards+=`<div class="pred-item"><div class="month">${p.month}</div><div class="price">${fmt(p.pred)}</div><div class="range">${fmt(p.lo)} ~ ${fmt(p.hi)}</div><div style="font-size:11px;color:${chg>=0?'#dc2626':'#16a34a'};margin-top:2px">${chg>=0?'+':''}${chg}%</div></div>`;
});
document.getElementById('pred-cards').innerHTML=cards;
document.getElementById('pred-chart-title').textContent=name+' 预测走势';

const histCloses=kline.slice(-12).map(k=>k[4]);
const histLabels=kline.slice(-12).map(k=>k[0]);
const predLabels=pred.map(p=>p.month);
const allLabels=[...histLabels,...predLabels];
const predData=new Array(histLabels.length).fill(null).concat(pred.map(p=>p.pred));
const hiData=new Array(histLabels.length).fill(null).concat(pred.map(p=>p.hi));
const loData=new Array(histLabels.length).fill(null).concat(pred.map(p=>p.lo));
const bridgeIdx=histLabels.length-1;
predData[bridgeIdx]=histCloses[bridgeIdx];

if(predChartInst)predChartInst.destroy();
predChartInst=new Chart(document.getElementById('predChart'),{
type:'line',
data:{labels:allLabels,datasets:[
{label:'历史收盘',data:[...histCloses,...new Array(predLabels.length).fill(null)],borderColor:'#2563eb',borderWidth:2,pointRadius:2,tension:.3,fill:false},
// 预测中枢用红色
{label:'预测中枢',data:predData,borderColor:'#dc2626',borderWidth:2,borderDash:[6,3],pointRadius:3,tension:.3,fill:false},
// 上限用红色系（高位=收益区）
{label:'上限',data:hiData,borderColor:'rgba(220,38,38,.3)',borderWidth:1,pointRadius:0,fill:false},
// 下限用绿色系（低位=亏损区），填充区间用淡色
{label:'下限',data:loData,borderColor:'rgba(22,163,74,.3)',borderWidth:1,pointRadius:0,fill:'+1',backgroundColor:'rgba(100,116,139,.06)'}
]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{usePointStyle:true}}},scales:{y:{ticks:{font:{size:10}}}}}
});
}

function switchPred(code){currentPredCode=code;document.querySelectorAll('#page-predict .tab-btn').forEach(b=>b.classList.remove('active'));event.target.classList.add('active');renderPred(code);}

init();
</script>
</body>
</html>'''

html = html.replace('{INJECTED_DATA}', data)
with open('deliverables/bank-stock-system.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'HTML生成完成，大小: {len(html)/1024:.0f}KB')
