"""
生成公司关系图谱演示数据（供离线/测试使用）。
当东方财富API不可用时，用此脚本填充示例数据。

用法: python scripts/seed_company_relations.py
"""
import os
import sys
import json
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')

from db_helper import (
    init_company_relations_tables, upsert_company_relation,
    upsert_company_business, clear_company_relations
)

# 自选股基础信息
STOCKS = {
    '601166': {'name': '兴业银行', 'industry': '银行', 'business': '企业金融业务、零售银行业务、金融市场业务、资产管理业务'},
    '600036': {'name': '招商银行', 'industry': '银行', 'business': '零售金融业务、批发金融业务、财富管理业务、资产管理业务'},
    '601398': {'name': '工商银行', 'industry': '银行', 'business': '公司金融业务、个人金融业务、资产管理业务、金融市场业务'},
    '600050': {'name': '中国联通', 'industry': '电信运营', 'business': '移动通信业务、固网通信业务、云计算和大数据服务、物联网'},
    '600941': {'name': '中国移动', 'industry': '电信运营', 'business': '移动话音业务、数据流量业务、政企市场业务、新兴市场业务'},
    '002594': {'name': '比亚迪', 'industry': '汽车制造', 'business': '新能源汽车、动力电池、手机部件及组装、轨道交通'},
    '600900': {'name': '长江电力', 'industry': '电力', 'business': '水力发电、电力销售、配售电业务、海外投资'},
}


def seed():
    init_company_relations_tables()
    clear_company_relations()

    print('[seed] 写入主营业务信息...')
    for code, info in STOCKS.items():
        upsert_company_business({
            'code': code,
            'name': info['name'],
            'industry': info['industry'],
            'business': info['business'],
            'source': 'seed',
        })
        print(f'  {code} {info["name"]}: {info["industry"]}')

    print('[seed] 写入股权关系...')
    # 兴业银行股东
    shareholders_601166 = [
        ('holder_香港中央结算', '香港中央结算', 19.83),
        ('holder_中国烟草', '中国烟草总公司', 5.34),
        ('holder_福建烟草', '福建省烟草公司', 4.56),
    ]
    for holder_id, holder_name, pct in shareholders_601166:
        upsert_company_relation({
            'code': '601166', 'related_code': holder_id, 'related_name': holder_name,
            'relation_type': 'equity', 'relation_subtype': 'shareholder',
            'relation_detail': f'持股{pct}%', 'weight': pct, 'direction': 'in',
            'extra_data': json.dumps({'share_pct': pct}, ensure_ascii=False),
        })

    # 招商银行股东
    shareholders_600036 = [
        ('holder_香港中央结算', '香港中央结算', 17.82),
        ('holder_招商局', '招商局集团有限公司', 6.35),
    ]
    for holder_id, holder_name, pct in shareholders_600036:
        upsert_company_relation({
            'code': '600036', 'related_code': holder_id, 'related_name': holder_name,
            'relation_type': 'equity', 'relation_subtype': 'shareholder',
            'relation_detail': f'持股{pct}%', 'weight': pct, 'direction': 'in',
            'extra_data': json.dumps({'share_pct': pct}, ensure_ascii=False),
        })

    # 工商银行股东
    shareholders_601398 = [
        ('holder_汇金公司', '中央汇金投资有限责任公司', 34.71),
        ('holder_财政部', '中华人民共和国财政部', 31.14),
    ]
    for holder_id, holder_name, pct in shareholders_601398:
        upsert_company_relation({
            'code': '601398', 'related_code': holder_id, 'related_name': holder_name,
            'relation_type': 'equity', 'relation_subtype': 'shareholder',
            'relation_detail': f'持股{pct}%', 'weight': pct, 'direction': 'in',
            'extra_data': json.dumps({'share_pct': pct}, ensure_ascii=False),
        })

    # 香港中央结算同时持有兴业和招商 → 建立间接关联
    upsert_company_relation({
        'code': '600036', 'related_code': 'holder_香港中央结算', 'related_name': '香港中央结算',
        'relation_type': 'equity', 'relation_subtype': 'shareholder',
        'relation_detail': '共同股东:香港中央结算', 'weight': 1.0, 'direction': 'both',
        'extra_data': json.dumps({'note': '共同股东关联'}, ensure_ascii=False),
    })

    print('[seed] 写入高管关联...')
    executives = [
        ('person_王建军', '王建军', '601166', '兴业银行', '监事长'),
        ('person_王建军', '王建军', '600036', '招商银行', '外部监事'),
        ('person_李伟', '李伟', '601166', '兴业银行', '独立董事'),
        ('person_张磊', '张磊', '600036', '招商银行', '副行长'),
        ('person_刘强', '刘强', '601398', '工商银行', '行长'),
    ]
    for person_id, person_name, stock_code, stock_name, position in executives:
        upsert_company_relation({
            'code': person_id, 'related_code': stock_code,
            'related_name': stock_name,
            'relation_type': 'executive', 'relation_subtype': 'executive',
            'relation_detail': position, 'weight': 1.0, 'direction': 'both',
            'extra_data': json.dumps({'position': position, 'person_name': person_name}, ensure_ascii=False),
        })

    print('[seed] 写入供应链关系...')
    # 兴业银行的供应商和客户
    suppliers_601166 = [
        ('恒生电子', '恒生电子', '供应商 采购占比3.5%', 3.5),
        ('用友网络', '用友网络', '供应商 采购占比2.8%', 2.8),
    ]
    for s_id, s_name, detail, pct in suppliers_601166:
        upsert_company_relation({
            'code': s_id, 'related_code': '601166', 'related_name': s_name,
            'relation_type': 'supply', 'relation_subtype': 'supplier',
            'relation_detail': detail, 'weight': pct, 'direction': 'in',
            'extra_data': json.dumps({'ratio': pct}, ensure_ascii=False),
        })

    print('[seed] 写入竞争关系...')
    bank_stocks = [('601166', '兴业银行'), ('600036', '招商银行'), ('601398', '工商银行')]
    for i in range(len(bank_stocks)):
        for j in range(i+1, len(bank_stocks)):
            code_a, name_a = bank_stocks[i]
            code_b, name_b = bank_stocks[j]
            upsert_company_relation({
                'code': code_a, 'related_code': code_b, 'related_name': name_b,
                'relation_type': 'competition', 'relation_subtype': 'competitor',
                'relation_detail': '同行业(银行)', 'weight': 1.0, 'direction': 'both',
                'extra_data': json.dumps({'industry': '银行'}, ensure_ascii=False),
            })

    print('[seed] 完成!')

    # 验证
    from db_helper import get_graph_data
    data = get_graph_data()
    print(f'  节点: {len(data["nodes"])}个, 边: {len(data["edges"])}条')


if __name__ == '__main__':
    seed()
