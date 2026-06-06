import shutil, os, glob
import re, json

ROOT = r"c:\Users\28312\WorkBuddy\2026-05-18-task-15"
BKP = os.path.join(ROOT, "backups", "v0.4")

# Step 1: Backup V0.4
if os.path.exists(BKP):
    shutil.rmtree(BKP)
os.makedirs(BKP)

for folder in ["deliverables", "scripts", "data", "docs"]:
    src = os.path.join(ROOT, folder)
    if os.path.exists(src):
        shutil.copytree(src, os.path.join(BKP, folder), ignore=shutil.ignore_patterns('*.pyc','__pycache__','*.fix_backup*','*.opt_*'))

for f in os.listdir(ROOT):
    fp = os.path.join(ROOT, f)
    if os.path.isfile(fp) and (f.endswith(('.py','.md','.bat','.xlsx','.xls'))):
        shutil.copy2(fp, os.path.join(BKP, f))

if os.path.exists(os.path.join(ROOT, "miaoxiang")):
    shutil.copytree(os.path.join(ROOT, "miaoxiang"), os.path.join(BKP, "miaoxiang"))

print("V0.4 backup: OK")

# Step 2: Delete dead files
deleted = []

# 2a. Fix_backup and opt_ files
for pat in ["*.fix_backup*", "*.opt_*"]:
    for f in glob.glob(os.path.join(ROOT, "deliverables", pat)):
        os.remove(f)
        deleted.append("deliverables/" + os.path.basename(f))

# 2b. .bak files in data/
for f in glob.glob(os.path.join(ROOT, "data", "*.bak")):
    os.remove(f)
    deleted.append("data/" + os.path.basename(f))

# 2c. Root .bak
rb = os.path.join(ROOT, "广发易淘金PC版-普通对账单结果查询.xlsx.bak")
if os.path.exists(rb):
    os.remove(rb)
    deleted.append("root/" + os.path.basename(rb))

# 2d. build_log.txt
bl = os.path.join(ROOT, "data", "build_log.txt")
if os.path.exists(bl):
    os.remove(bl)
    deleted.append("data/build_log.txt")

# 2e. sh_list.xls (duplicate, data in a_stocks.json)
sl = os.path.join(ROOT, "sh_list.xls")
if os.path.exists(sl):
    os.remove(sl)
    deleted.append("sh_list.xls")

# 2f. One-off scripts
for s in ["fix_frontend_bugs.py", "optimize_frontend.py"]:
    fp = os.path.join(ROOT, "scripts", s)
    if os.path.exists(fp):
        os.remove(fp)
        deleted.append("scripts/" + s)

print("Deleted %d files:" % len(deleted))
for d in deleted:
    print("  [OK] " + d)

# Step 3: Deduplicate HTML
html_path = os.path.join(ROOT, "deliverables", "bank-stock-system.html")
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

before = len(html)

# Remove duplicate 2nd Triggers block
# Find 2nd occurrence of "// ===== Triggers ====="
first = html.find("// ===== Triggers =====")
second = html.find("// ===== Triggers =====", first + 1)

if second > 0:
    # Find the end of the compat wrappers after this block
    tfs = html.find("async function triggerFullSync(){ return triggerSync(); }", second)
    if tfs > 0:
        end_marker = tfs + len("async function triggerFullSync(){ return triggerSync(); }")
        # Find next newline
        nl = html.find("\n", end_marker)
        if nl > 0:
            html = html[:second] + html[nl+1:]
            removed = before - len(html)
            print("HTML deduplication: removed %d chars (duplicate Triggers block)" % removed)
        else:
            print("WARNING: could not find end of Triggers block")
    else:
        print("WARNING: could not find triggerFullSync compat wrapper")
else:
    print("No duplicate Triggers block found (already cleaned?)")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

after = len(html)
print("HTML size: %d -> %d bytes" % (before, after))
print("\nCleanup complete!")
