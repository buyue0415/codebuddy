// ===== Extra Utilities (deduplicated) =====
function dirIcon(d){return d==='bullish'?'↗':d==='bearish'?'↘':'→';}
function dirText(d){return d==='bullish'?'偏多':d==='bearish'?'偏空':'震荡';}

function handleExpertFile(){
 var file=document.getElementById('expert-file').files[0];
 if(!file) return;
 document.getElementById('expert-filename').textContent=file.name;
 var reader=new FileReader();
 reader.onload=function(e){document.getElementById('expert-json-text').value=e.target.result;};
 reader.readAsText(file);
}

async function importExpertReport(){
 if(!hasAPI()){ alert('需要通过本地服务器访问'); return; }
 var text=document.getElementById('expert-json-text').value.trim();
 if(!text){ alert('请先选择JSON文件或粘贴报告内容'); return; }
 var st=document.getElementById('expert-import-status');
 st.style.color='#6b7280'; st.textContent='导入中...';
 try{
  var data=JSON.parse(text);
  // Step 1: pure business — import report to DB
  var r=await apiCall('POST','/api/v2/expert/import',data);
  if(!r||!r.success){ st.style.color='#dc2626'; st.textContent='失败: '+((r&&r.error)||(r&&r.message)||'未知'); return; }
  st.style.color='#16a34a'; st.textContent=r.message||'导入成功';
  if(r.warnings&&r.warnings.length){ st.textContent+=' (警告:'+r.warnings.length+'条)'; }
  // V0.6: Reload to fetch fresh API data
  st.textContent+=' | 刷新页面中...';
  setTimeout(function(){location.reload(true);},600);
 }catch(e){ st.style.color='#dc2626'; st.textContent='错误: '+e.message; }
}

