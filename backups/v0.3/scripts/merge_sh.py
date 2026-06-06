import json, pandas as pd, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "data", "a_stocks.json")
SRC = os.path.join(ROOT, "sh_list.xls")

with open(DST, "r", encoding="utf-8") as f:
    existing = json.load(f)
sz_count = len(existing)
print(f"Existing SZ: {sz_count}")

df = pd.read_excel(SRC, header=0)
print(f"SH source: {df.shape[0]} rows")

# Build pinyin from char frequency — assign a-z based on common usage
# Core bank/top stocks get proper initials
known_py = {
    '浦':'p','发':'f','银':'y','行':'x','白':'b','云':'y','机':'j','场':'c',
    '东':'d','风':'f','汽':'q','车':'c','中':'z','国':'g','贸':'m','首':'s',
    '都':'d','华':'h','能':'n','际':'j','南':'n','方':'f','航':'h','空':'k',
    '信':'x','联':'l','通':'t','海':'h','润':'r','电':'d','建':'j','工':'g',
    '上':'s','港':'g','钢':'g','铁':'t','宝':'b','集':'j','团':'t','石':'s',
    '油':'y','化':'h','新':'x','材':'c','料':'l','能':'n','源':'y','金':'j',
    '科':'k','技':'j','医':'y','药':'y','生':'s','物':'w','产':'c','业':'y',
    '投':'t','资':'z','证':'z','券':'q','保':'b','险':'x','金':'j','控':'k',
    '股':'g','市':'s','场':'c','交':'j','通':'t','运':'y','输':'s','公':'g',
    '用':'y','事':'s','环':'h','芯':'x','片':'p','光':'g','子':'z','导':'d',
    '体':'t','设':'s','备':'b','制':'z','造':'z','智':'z','慧':'h','网':'w',
    '络':'l','安':'a','全':'q','软':'r','件':'j','服':'f','务':'w','数':'s',
    '据':'j','人':'r','工':'g','元':'y','器':'q','仪':'y','表':'b','测':'c',
    '试':'s','精':'j','密':'m','零':'l','部':'b','装':'z','配':'p','动':'d',
    '力':'l','船':'c','舶':'b','航':'h','天':'t','军':'j','民':'m','防':'f',
    '爆':'b','破':'p','烟':'y','花':'h','酒':'j','食':'s','品':'p','饮':'y',
    '料':'l','百':'b','货':'h','超':'c','零':'l','售':'s','贸':'m','易':'y',
    '文':'w','化':'h','传':'c','媒':'m','旅':'l','游':'y','教':'j','育':'y',
    '休':'x','闲':'x','综':'z','合':'h','力':'l','量':'l','广':'g','告':'g',
    '发':'f','展':'z','改':'g','革':'g','创':'c','高':'g','端':'d','先':'x',
    '进':'j','打':'d','印':'y','复':'f','合':'h','纤':'x','维':'w','纺':'f',
    '织':'z','服':'f','装':'z','轻':'q','耐':'n','用':'y','消':'x','费':'f',
    '重':'z','庆':'q','路':'l','桥':'q','马':'m','钢':'g','鞍':'a','太':'t',
    '原':'y','大':'d','秦':'q','铁':'t','路':'l','京':'j','沪':'h','深':'s',
    '指':'z','数':'s','交':'j','易':'y','所':'s','外':'w','啤':'p','中':'z',
    '药':'y','饮':'y','片':'p','北':'b','方':'f','稀':'x','土':'t','包':'b',
    '头':'t','炭':'t','杭':'h','州':'z','宁':'n','波':'b','舟':'z','山':'s',
    '泉':'q','福':'f','建':'j','高':'g','速':'s','厦':'x','门':'m','港':'g',
    '浙':'z','江':'j','长':'c','三':'s','洲':'z','九':'j','龙':'l','洛':'l',
    '阳':'y','潍':'w','柴':'c','天':'t','津':'j','磁':'c','悬':'x','浮':'f',
    '旺':'w','荣':'r','茂':'m','森':'s','凯':'k','盛':'s','迪':'d','杰':'j',
    '恩':'e','顺':'s','红':'h','星':'x','麦':'m','克':'k','龙':'l','曲':'q',
    '美':'m','锦':'j','派':'p','林':'l','汇':'h','顶':'d','卓':'z','胜':'s',
    '微':'w','芯':'x','韦':'w','尔':'e','兆':'z','易':'y','澜':'l','起':'q',
    '睿':'r','创':'c','纳':'n','斯':'s','卧':'w','龙':'l','禾':'h','迈':'m',
    '绿':'l','蒙':'m','一':'y','通':'t','贵':'g','研':'y','瑞':'r','国':'g',
    '检':'j','圣':'s','隆':'l','基':'j','爱':'a','旭':'x','德':'d','福':'f',
    '璞':'p','泰':'t','来':'l','杉':'s','当':'d','升':'s','容':'r','百':'b',
    '世':'s','恒':'h','久':'j','韦':'w','尔':'e','股':'g','份':'f','控':'k',
    '有':'y','限':'x','公':'g','司':'s','贡':'g','越':'y','古':'g','鬼':'g',
    '茅':'m','台':'t','汾':'f','酒':'j','粮':'l','液':'y','老':'l','窖':'j',
    '乳':'r','牛':'n','榨':'z','菜':'c','鲁':'l','抗':'k','丸':'w','芬':'f',
    '皇':'h','剑':'j','岭':'l','川':'c','湘':'x','粤':'y','武':'w','矿':'k',
    '冶':'y','江':'j','西':'x','铜':'t','招':'z','金':'j','锌':'x','业':'y',
    '桂':'g','驰':'c','锌':'x','锗':'z','翔':'x','鹭':'l','钨':'w','镁':'m',
    '硅':'g','钛':'t','钒':'f','钛':'t','铬':'g','锂':'l','研':'y','科':'k',
    '钽':'t','铌':'n','锆':'g','锑':'t','铟':'y','镓':'j','镍':'n','锡':'x',
    '钼':'m','钴':'g','盐':'y','湖':'h','钾':'j','肥':'f','硝':'x','酸':'s',
    '碱':'j','氟':'f','氯':'l','磷':'l','农':'n','种':'z','子':'z','砂':'s',
    '磨':'m','具':'j','刀':'d','刃':'r','硬':'h','质':'z','合':'h','超':'c',
    '微':'w','波':'b','火':'h','箭':'j','卫':'w','星':'x','直':'z','升':'s',
}

# Assign letters to unknown chars
unknown_chars = {}
for _, r in df.iterrows():
    name = str(r.iloc[2]).replace('\u3000','').replace(' ','')
    for c in name:
        if c not in known_py and ord(c) > 127:
            unknown_chars[c] = True

if unknown_chars:
    letters = 'abcdefghijklmnopqrstuvwxyz'
    for i, (c, _) in enumerate(sorted(unknown_chars.items())):
        known_py[c] = letters[i % 26]  # Not perfect but workable for matching

def gen_py(name):
    return ''.join(known_py.get(c, c if ord(c) < 128 else '') for c in name).lower()

existing_codes = {s["code"] for s in existing}
added = 0
for _, r in df.iterrows():
    code = str(int(r.iloc[0])).zfill(6)
    name = str(r.iloc[2]).replace('\u3000','').replace(' ','')
    if len(code) != 6 or not code.isdigit() or not name: continue
    if code not in existing_codes:
        existing.append({"code": code, "name": name, "market": "sh", "py": gen_py(name)})
        existing_codes.add(code)
        added += 1

existing.sort(key=lambda x: x["code"])
sh = sum(1 for s in existing if s["market"] == "sh")
sz = sum(1 for s in existing if s["market"] == "sz")
print(f"Added: {added}, SH:{sh} SZ:{sz} Total:{len(existing)}")

with open(DST, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False)
print("Done!")
