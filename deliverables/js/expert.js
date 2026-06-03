


let currentExpertStock=_firstWatchCode();var currentExpertIdx=0;
let expertRadarInst,expertBullBearInst,expertRiskInst;

function switchExpertStock(code){
currentExpertStock=code;
document.querySelectorAll('#expert-tabs .tab-btn').forEach(function(b){var o=b.getAttribute('onclick')||'';b.classList.toggle('active',o.indexOf(code)!==-1);});
renderExpertList();
}

function renderExpertList(){
const reports=DATA.expert_reports||[];

const stockReports=reports.filter(r=>r.stocks && r.stocks[currentExpertStock]);
stockReports.sort((a,b)=>b.date.localeCompare(a.date));
const sidebar=document.getElementById('expert-sidebar');

if(!stockReports.length){
sidebar.innerHTML='<div style="color:#9ca3af;font-size:13px;padding:12px">暂无报告</div>';
document.getElementById('expert-empty').style.display='block';
document.getElementById('expert-detail').style.display='none';
return;
}

currentExpertIdx=0;
sidebar.innerHTML=stockReports.map((r,i)=>{
const s=r.stocks[currentExpertStock];
const dec=s?s.decision:'N/A';
const decIcon=dec==='BUY'?'🟢':dec==='SELL'?'🔴':'🟡';
return `<div class="rpt-item ${i===0?'active':''}" onclick="selectExpert(${i},'${currentExpertStock}')">
<div class="rpt-date">${r.date}</div>
<div class="rpt-decision">${decIcon} ${dec} · ${getStockName(currentExpertStock)}</div>
</div>`;
}).join('');

renderExpertDetail(stockReports[0], currentExpertStock);
}

function selectExpert(idx, code){
const reports=(DATA.expert_reports||[]).filter(r=>r.stocks && r.stocks[code]);
reports.sort((a,b)=>b.date.localeCompare(a.date));
document.querySelectorAll('.rpt-item').forEach((el,i)=>el.classList.toggle('active',i===idx));
currentExpertIdx=idx;
renderExpertDetail(reports[idx], code);
}

function renderExpertDetail(report, code){
if(!report||!report.stocks||!report.stocks[code]){
document.getElementById('expert-empty').style.display='block';
document.getElementById('expert-detail').style.display='none';
return;
}
document.getElementById('expert-empty').style.display='none';
document.getElementById('expert-detail').style.display='block';

const s=report.stocks[code];

const dec=s.decision||'HOLD';
const decClass=dec.toLowerCase();

document.getElementById('expert-decision-card').innerHTML=`
<div class="expert-decision-card ${decClass}">
<h1>${dec}</h1>
<div class="sub-info">
<span>信心：${s.confidence||'中'}</span>
<span>风险：${s.risk_level||'中'}</span>
<span>建议仓位：${s.position_pct||0}%</span>
</div>
<div class="price-grid">
<div class="price-item"><div class="plabel">入场价</div><div class="pval">${s.entry_price?'--':fmt(s.entry_price)}</div></div>
<div class="price-item"><div class="plabel">目标价</div><div class="pval">${fmt(s.target_price)}</div></div>
<div class="price-item"><div class="plabel">止损价</div><div class="pval">${fmt(s.stop_loss)}</div></div>
<div class="price-item"><div class="plabel">现价</div><div class="pval">${fmt(DATA.quotes[code]?.price)}</div></div>
</div>
</div>`;

// 雷达图
const scores=s.scores||{};
if(expertRadarInst)expertRadarInst.destroy();
expertRadarInst=new Chart(document.getElementById('expertRadarChart'),{
type:'radar',
data:{labels:['技术面','基本面','新闻面','情绪面','风险面'],datasets:[{label:getStockName(code),data:[scores.technical||0,scores.fundamental||0,scores.news||0,scores.sentiment||0,scores.risk||0],backgroundColor:'rgba(37,99,235,.15)',borderColor:'#2563eb',borderWidth:2,pointBackgroundColor:'#2563eb',pointRadius:4}]},
options:{responsive:true,maintainAspectRatio:false,scales:{r:{min:0,max:10,ticks:{stepSize:2,font:{size:10}},pointLabels:{font:{size:12}}}},plugins:{legend:{display:false}}}
});

// 多空对比
const bull=s.phase2?.bull_args||[];
const bear=s.phase2?.bear_args||[];
const maxLen=Math.max(bull.length,bear.length,1);
const bbLabels=[];
const bullData=[],bearData=[];
for(let i=0;i<maxLen;i++){
bbLabels.push('论点'+(i+1));
bullData.push(bull[i]?.weight||0);
bearData.push(bear[i]?.weight||0);
}
if(expertBullBearInst)expertBullBearInst.destroy();
expertBullBearInst=new Chart(document.getElementById('expertBullBearChart'),{
type:'bar',
data:{labels:bbLabels,datasets:[
{label:'多头(看涨)',data:bullData,backgroundColor:'#dc2626'},
{label:'空头(看跌)',data:bearData,backgroundColor:'#16a34a'}
]},
options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,scales:{x:{max:10,ticks:{font:{size:10}}},y:{ticks:{font:{size:10}}}},plugins:{legend:{position:'top'}}}
});

// 风险三角图
const p4=s.phase4||{};
if(expertRiskInst)expertRiskInst.destroy();
expertRiskInst=new Chart(document.getElementById('expertRiskChart'),{
type:'radar',
data:{labels:['激进','保守','中性'],datasets:[{label:'风险评分',data:[p4.aggressive_score||0,p4.conservative_score||0,p4.neutral_score||0],backgroundColor:'rgba(245,158,11,.15)',borderColor:'#f59e0b',borderWidth:2,pointBackgroundColor:'#f59e0b',pointRadius:5}]},
options:{responsive:true,maintainAspectRatio:false,scales:{r:{min:0,max:10,ticks:{stepSize:2,font:{size:10}},pointLabels:{font:{size:13}}}},plugins:{legend:{display:false}}}
});

// 折叠详情
const p1=s.phase1||{};
const collapses=document.getElementById('expert-collapses');
collapses.innerHTML=`
<div class="collapse-section"><div class="collapse-header" onclick="toggleCollapse(this)"><span>📈 技术面分析</span><span class="arrow">▶</span></div><div class="collapse-body">${p1.technical||'暂无'}</div></div>
<div class="collapse-section"><div class="collapse-header" onclick="toggleCollapse(this)"><span>📊 基本面分析</span><span class="arrow">▶</span></div><div class="collapse-body">${p1.fundamental||'暂无'}</div></div>
<div class="collapse-section"><div class="collapse-header" onclick="toggleCollapse(this)"><span>📰 新闻面分析</span><span class="arrow">▶</span></div><div class="collapse-body">${p1.news||'暂无'}</div></div>
<div class="collapse-section"><div class="collapse-header" onclick="toggleCollapse(this)"><span>💭 情绪面分析</span><span class="arrow">▶</span></div><div class="collapse-body">${p1.sentiment||'暂无'}</div></div>
<div class="collapse-section"><div class="collapse-header" onclick="toggleCollapse(this)"><span>⚖️ 多空辩论结论</span><span class="arrow">▶</span></div><div class="collapse-body"><b>多头论点：</b><ul class="arg-list">${bull.map(a=>`<li><span class="arg-weight bull">${a.weight}</span>${a.point}</li>`).join('')}</ul><b>空头论点：</b><ul class="arg-list">${bear.map(a=>`<li><span class="arg-weight bear">${a.weight}</span>${a.point}</li>`).join('')}</ul><b style="margin-top:8px;display:block">裁决：${s.phase2?.verdict||'暂无'}</b></div></div>
<div class="collapse-section"><div class="collapse-header" onclick="toggleCollapse(this)"><span>🛡️ 风险评估结论</span><span class="arrow">▶</span></div><div class="collapse-body">${p4.final_risk_note||'暂无'}</div></div>
${(s.catalysts?.length||s.risks?.length)?`<div class="card" style="margin-top:12px"><h2>🔑 催化剂 & 风险事件</h2><div style="margin-bottom:8px"><b>催化剂</b><div class="tag-list">${(s.catalysts||[]).map(c=>`<span class="etag catalyst">${c}</span>`).join('')}</div></div><div><b>风险事件</b><div class="tag-list">${(s.risks||[]).map(r=>`<span class="etag risk">${r}</span>`).join('')}</div></div></div>`:''}
`;
}

function toggleCollapse(el){
el.classList.toggle('open');
el.nextElementSibling.classList.toggle('open');
}
