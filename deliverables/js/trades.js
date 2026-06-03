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
