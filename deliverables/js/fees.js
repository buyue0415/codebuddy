
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
