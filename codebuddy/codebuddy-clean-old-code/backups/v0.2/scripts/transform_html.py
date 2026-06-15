"""
HTML watchlist transformation: replace all hardcoded 601166/600036 with watchlist-driven code.
"""
import re, json

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
watchlist = d.get('watchlist', [])
codes = [s['code'] for s in watchlist]
names = {s['code']: s['name'] for s in watchlist}
first_code = codes[0] if codes else '601166'

print(f"Watchlist: {codes} -> {[names[c] for c in codes]}")

with open('deliverables/bank-stock-system.html', 'r', encoding='utf-8') as f:
    html = f.read()

changes = 0

# 1. Replace all hardcoded names maps with a unified function
old_names_patterns = [
    r"const names=\{.*?\};",
    r"const dpNames=\{.*?\};",
]

for pat in old_names_patterns:
    if re.search(pat, html):
        html = re.sub(pat, '', html)
        changes += 1

# 2. Inject global getName function right after <script>
getNameFunc = """
function getStockName(code){
const wl=DATA.watchlist||[];
const s=wl.find(function(x){return x.code===code});
return s?s.name:code;
}
function getWatchlist(){return DATA.watchlist||[];}
"""
html = html.replace('<script>', '<script>\n' + getNameFunc)

# 3. Replace all names lookups: names[code] or names['601166'] → getStockName(code)
html = re.sub(r'names\[(\w+)\]', r'getStockName(\1)', html)
html = re.sub(r"names\['(\d+)'\]", r"getStockName('\1')", html)
html = re.sub(r'dpNames\[(\w+)\]', r'getStockName(\1)', html)
changes += 1

# 4. Replace hardcoded switch buttons — K线, 预测, 新闻, 专家, 日预测
# Pattern: <button...onclick="switchKline('601166')">兴业银行</button>
# Replace with dynamic generation in each showPage/idle init

# For K线 page
html = re.sub(
    r'<button class="tab-btn active" onclick="switchKline\(\'601166\'\)">兴业银行</button>\s*<button class="tab-btn" onclick="switchKline\(\'600036\'\)">招商银行</button>',
    '<div id="kline-tabs" class="tab-bar" style="margin-bottom:12px"></div>',
    html
)
changes += 1

# For 预测 page
html = re.sub(
    r'<button class="tab-btn active" onclick="switchPred\(\'601166\'\)">兴业银行</button>\s*<button class="tab-btn" onclick="switchPred\(\'600036\'\)">招商银行</button>',
    '<div id="pred-tabs" class="tab-bar" style="margin-bottom:12px"></div>',
    html
)
changes += 1

# For 新闻 page
html = re.sub(
    r'<button class="tab-btn active" onclick="filterNews\(\'all\'\)">全部</button>\s*<button class="tab-btn" onclick="filterNews\(\'601166\'\)">兴业银行</button>\s*<button class="tab-btn" onclick="filterNews\(\'600036\'\)">招商银行</button>\s*<button class="tab-btn" onclick="filterNews\(\'major\'\)">⚠️ 重大事件</button>',
    '<button class="tab-btn active" onclick="filterNews(\'all\')">全部</button>\n<div id="news-tabs-inline" style="display:inline"></div>\n<button class="tab-btn" onclick="filterNews(\'major\')">⚠️ 重大事件</button>',
    html
)
changes += 1

# For 专家分析 page
html = re.sub(
    r'<button class="tab-btn active" onclick="switchExpertStock\(\'601166\'\)">兴业银行</button>\s*<button class="tab-btn" onclick="switchExpertStock\(\'600036\'\)">招商银行</button>',
    '<div id="expert-tabs" class="tab-bar" style="margin-bottom:16px"></div>',
    html
)
changes += 1

# For 日预测 page
html = re.sub(
    r'<button class="tab-btn active" onclick="switchDpStock\(\'601166\'\)">兴业银行</button>\s*<button class="tab-btn" onclick="switchDpStock\(\'600036\'\)">招商银行</button>',
    '<div id="dailypred-tabs" class="tab-bar" style="margin-bottom:16px"></div>',
    html
)
changes += 1

# 5. Replace default code selections
html = re.sub(r"let currentKlineCode = '\d+'", f"let currentKlineCode = '{first_code}'", html)
html = re.sub(r"let currentPredCode = '\d+'", f"let currentPredCode = '{first_code}'", html)
html = re.sub(r"currentExpertStock='\d+'", f"currentExpertStock='{first_code}'", html)
html = re.sub(r"let dpCode='\d+'", f"let dpCode='{first_code}'", html)

# 6. Replace hardcoded init render calls
html = re.sub(r"renderKline\('\d+'\)", f"renderKline('{first_code}')", html)
html = re.sub(r"renderPred\('\d+'\)", f"renderPred('{first_code}')", html)

# 7. Replace hardcoded CSS tag classes with generic ones
# .tag-601166 → .tag-stock-0, .tag-600036 → .tag-stock-1
# Actually leave these as-is and make them work via data attributes
# The CSS can stay for now since it only affects visual appearance

# 8. Add dynamic tab generation on init
tabGenCode = """
// Generate dynamic stock tabs
function genStockTabs(containerId, switchFn, activeCode){
var el=document.getElementById(containerId);
if(!el)return;
var wl=getWatchlist();
var html='';
wl.forEach(function(s,i){
html+='<button class=\"tab-btn'+(s.code===activeCode?' active':'')+'\" onclick=\"'+switchFn+'(\\''+s.code+'\\')\">'+s.name+'</button>';
});
el.innerHTML=html;
}
"""
html = html.replace('function init(){', tabGenCode + '\nfunction init(){')

# 9. Add tab generation to init and showPage
# In init(), after setting up data:
init_gen_tabs = """
genStockTabs('kline-tabs','switchKline',currentKlineCode);
genStockTabs('pred-tabs','switchPred',currentPredCode);
genStockTabs('expert-tabs','switchExpertStock',currentExpertStock);
genStockTabs('dailypred-tabs','switchDpStock',dpCode);
// News inline tabs
var nel=document.getElementById('news-tabs-inline');
if(nel){var wl=getWatchlist();var nh='';wl.forEach(function(s){nh+='<button class=\"tab-btn\" onclick=\"filterNews(\\''+s.code+'\\')\">'+s.name+'</button>';});nel.innerHTML=nh;}
"""

html = html.replace('genStockTabs(\'kline-tabs\'', init_gen_tabs + '\ngenStockTabs(\'kline-tabs\'', 1)

# 10. Update showPage to regenerate tabs
html = html.replace(
    "if(id==='kline')renderKline();",
    "if(id==='kline'){renderKline();genStockTabs('kline-tabs','switchKline',currentKlineCode);}"
)
html = html.replace(
    "if(id==='dailypred')renderDpPage();",
    "if(id==='dailypred'){renderDpPage();genStockTabs('dailypred-tabs','switchDpStock',dpCode);}"
)

# 11. Replace remaining hardcoded names in JS strings (e.g., in news/render functions)
# The getStockName function handles this via the names→getStockName replacement already done

with open('deliverables/bank-stock-system.html', 'w', encoding='utf-8') as f:
    f.write(html)

remaining = len(re.findall(r"'601166'|'600036'", html))
print(f"HTML transformation complete. {changes} changes applied.")
print(f"Remaining hardcoded refs: {remaining}")
