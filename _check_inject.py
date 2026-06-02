import re, json
with open('deliverables/bank-stock-system.html', 'r', encoding='utf-8') as f:
    html = f.read()
m = re.search(r'(let|const|var)\s+DATA\s*=\s*(\{.*?\});\s*\n', html, re.DOTALL)
print(f"MATCH: {m is not None}")
if m:
    s = m.group(2)
    print(f"LEN: {len(s)}")
    # Check pos 145489
    if len(s) > 145489:
        ch = s[145489]
        print(f"CHAR at 145489: U+{ord(ch):04X} repr={repr(ch)}")
        before = s[145470:145489]
        after = s[145490:145510]
        print(f"BEFORE: {repr(before)}")
        print(f"AFTER: {repr(after)}")
    # Search for \uXXXX with control code
    for m2 in re.finditer(r'\\u000[0-9a-fA-F]|\\u001[0-9a-fA-F]', s):
        print(f"ESCAPED CONTROL: {m2.group()} at {m2.start()}")
