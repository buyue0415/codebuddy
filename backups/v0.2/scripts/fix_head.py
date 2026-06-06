import re

with open("deliverables/bank-stock-system.html", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find and modify
new_lines = []
skip_next = 0
for i, line in enumerate(lines):
    if '<script src="https://cdnjs.cloudflare.com' in line:
        continue  # skip CDN line
    if '<script src="https://unpkg.com' in line:
        continue  # skip unpkg line
    if '// 确保init()无论如何都会执行' in line:
        # Skip the whole _safeInit block
        skip_next = 23  # lines to skip
        continue
    if skip_next > 0:
        skip_next -= 1
        continue
    new_lines.append(line)

# Add CDN right before </body>
body_lines = []
for line in new_lines:
    if '</body>' in line:
        body_lines.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n')
        body_lines.append('<script src="https://unpkg.com/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n')
    body_lines.append(line)

with open("deliverables/bank-stock-system.html", "w", encoding="utf-8") as f:
    f.writelines(body_lines)

print("Done. Checking...")
with open("deliverables/bank-stock-system.html", "r", encoding="utf-8") as f:
    text = f.read()
print(f"  CDN in file: {'cdnjs.cloudflare.com' in text}")
print(f"  init() calls: {text.count('init();')}")
print(f"  _safeInit in file: {'_safeInit' in text}")
