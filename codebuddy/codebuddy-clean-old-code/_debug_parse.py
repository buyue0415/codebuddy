import zipfile, xml.etree.ElementTree as ET

path = r'C:\Users\28312\Desktop\广发易淘金PC版-普通对账单结果查询汇总.xlsx'

with zipfile.ZipFile(path, 'r') as z:
    print('=== ZIP 内部文件列表 ===')
    for name in z.namelist():
        print(f'  {name} (size={z.getinfo(name).file_size})')

    NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

    # 读取共享字符串表
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(f'{NS}si'):
            text = si.findtext(f'{NS}t', '') or ''
            for r in si.findall(f'{NS}r'):
                t = r.findtext(f'{NS}t', '') or ''
                text += t
            sst.append(text)
        print(f'\n=== 共享字符串表 (前30个) ===')
        for i, s in enumerate(sst[:30]):
            print(f'  [{i}] {repr(s)}')
    else:
        print('\n无 sharedStrings.xml')

    # 读取第一个工作表
    root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))

    print('\n=== 工作表前15行 ===')
    for ri, row_elem in enumerate(list(root.findall(f'{NS}sheetData/{NS}row'))[:15]):
        row_num = row_elem.get('r', '?')
        cells = []
        for c in row_elem.findall(f'{NS}c'):
            ref = c.get('r', '')
            cell_type = c.get('t', '')
            v_elem = c.find(f'{NS}v')
            if v_elem is not None and v_elem.text is not None:
                if cell_type == 's':
                    idx = int(v_elem.text)
                    val = sst[idx] if idx < len(sst) else '?'
                else:
                    val = v_elem.text
            else:
                val = ''
            cells.append(f'{ref}={repr(val)}')
        print(f'  Row {row_num}: {" | ".join(cells[:12])}')

    # 检查是否有多余的工作表
    print(f'\n=== 所有工作表 ===')
    wb_root = ET.fromstring(z.read('xl/workbook.xml'))
    for ws in wb_root.findall(f'{NS}sheets/{NS}sheet'):
        name = ws.get('name', '?')
        rid = ws.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', '?')
        print(f'  Sheet: name={repr(name)}, r:id={rid}')
