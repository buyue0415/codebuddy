"""分析对账单 Excel 文件结构"""
import zipfile, os, sys

path = r'C:\Users\28312\Desktop\广发易淘金PC版-普通对账单结果查询.xlsx'

print(f"文件大小: {os.path.getsize(path)} bytes")
print()

with zipfile.ZipFile(path, 'r') as z:
    print("=== zip 内部文件列表 ===")
    for n in z.namelist():
        print(f"  {n}")
    print()

    # 尝试读取 sheet1.xml 直接看原始 XML
    sheet_xml = z.read('xl/worksheets/sheet1.xml').decode('utf-8')
    # 只显示前2000字符
    print("=== sheet1.xml (前2000字符) ===")
    print(sheet_xml[:2000])
    print()

    # 检查是否有 sharedStrings
    if 'xl/sharedStrings.xml' in z.namelist():
        print("有 sharedStrings.xml")
    else:
        print("没有 sharedStrings.xml")

    # 检查样式表
    if 'xl/styles.xml' in z.namelist():
        styles = z.read('xl/styles.xml').decode('utf-8')
        print("=== styles.xml (前500字符) ===")
        print(styles[:500])
    else:
        print("没有 styles.xml")
