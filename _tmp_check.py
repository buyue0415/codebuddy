import re
f=open(r'c:\Users\28312\WorkBuddy\2026-05-18-task-15\deliverables\bank-stock-system.html', encoding='utf-8')
c=f.read()
scripts=re.findall(r'<script>(.*?)</script>', c, re.DOTALL)
for i,s in enumerate(scripts):
    if len(s) > 100:
        try:
            compile(s, f'script_{i}.js', 'exec')
            lines = s.count('\n')
            print(f'Main script ({lines} lines): SYNTAX OK')
        except SyntaxError as e:
            print(f'MAIN SCRIPT SYNTAX ERROR at line {e.lineno}: {e.msg}')
            print(f'  Context: {e.text[:100] if e.text else "N/A"}')
