"""一致性检查脚本 — 检测 Specs / Tests / 代码 三者是否同步。

用法:
    python scripts/check_sync.py               # 普通检查模式
    python scripts/check_sync.py --precommit   # Git 预提交检查模式

检查逻辑:
    - Specs vs Tests：有 spec 无 test / 有 test 无 spec？
    - 代码 vs Specs：改代码忘记改文档？
    - API 路由 vs 附录B：改了路由忘了更新清单？
"""

import os, sys, time, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WARNINGS = []


def ts(path):
    """Get file modification timestamp."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def age_str(days, hours, minutes):
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    return "".join(parts) if parts else "较短时间"


def now_ts():
    return time.time()


def check_spec_vs_test():
    """每个 spec 模块是否都有对应测试文件？"""
    specs = sorted(glob.glob(os.path.join(ROOT, "docs/specs/0*-*.md")))
    for sp in specs:
        base = os.path.basename(sp)  # e.g. "07-news-fetcher.md"
        # Map spec to test: e.g. "07-news-fetcher" -> "test_news_fetcher"
        parts = base.split("-", 1)
        if len(parts) < 2:
            continue
        module_key = parts[1].replace(".md", "")  # "news-fetcher"
        test_name = f"test_{module_key.replace('-', '_')}.py"
        test_path = os.path.join(ROOT, "tests", test_name)
        if not os.path.exists(test_path):
            WARNINGS.append(
                f"[MISS] docs/specs/{base} 无对应测试文件 tests/{test_name}"
            )


def check_code_vs_spec_timestamps():
    """改代码超过 1 天未更新 spec 时提醒。"""
    specs = glob.glob(os.path.join(ROOT, "docs/specs/*.md"))
    py_files = glob.glob(os.path.join(ROOT, "scripts/*.py")) + \
               [os.path.join(ROOT, "server.py")]

    # Build mapping: py file -> spec file (by module number)
    for pyf in py_files:
        py_mtime = ts(pyf)
        py_name = os.path.basename(pyf).replace(".py", "")

        # Find matching spec by checking if py_name appears in any spec content
        matching_spec = None
        for sp in specs:
            sp_base = os.path.basename(sp)
            sp_content = open(sp, 'r', encoding='utf-8').read(500)
            if py_name in sp_content or py_name.replace("_", "-") in sp_content:
                matching_spec = sp
                break

        if matching_spec and py_mtime > ts(matching_spec):
            diff = py_mtime - ts(matching_spec)
            if diff > 86400:  # 24 hours
                d = int(diff // 86400)
                h = int((diff % 86400) // 3600)
                WARNINGS.append(
                    f"[WARN] {os.path.basename(pyf)} {age_str(d,h,0)}前修改，"
                    f"但 {os.path.basename(matching_spec)} 未同步更新"
                )


def check_api_vs_appendix():
    """粗略检查 API 路由是否有附录外的遗漏。"""
    appendix_path = os.path.join(ROOT, "docs/specs/appendix-b-api.md")
    if not os.path.exists(appendix_path):
        return
    with open(appendix_path, 'r', encoding='utf-8') as f:
        appendix_content = f.read()

    # Scan server.py for API routes
    server_path = os.path.join(ROOT, "server.py")
    if not os.path.exists(server_path):
        return
    with open(server_path, 'r', encoding='utf-8') as f:
        server_content = f.read()

    routes_found = re.findall(r'"(/api/[^"]+)"', server_content)
    routes_missing = []
    for r in routes_found:
        if r not in appendix_content and '/api/v2/kline/' not in r:
            routes_missing.append(r)

    # K-line wildcard: check that at least one kline pattern is documented
    kline_in_doc = '/api/v2/kline' in appendix_content
    kline_in_code = any('kline' in r for r in routes_found)
    if kline_in_code and not kline_in_doc:
        routes_missing.append('/api/v2/kline/* (wildcard)')

    if routes_missing:
        WARNINGS.append(
            f"[ROUTE] server.py 中有 {len(routes_missing)} 个路由"
            f"未在 appendix-b-api.md 中列出: {routes_missing[:3]}..."
        )


def main():
    check_spec_vs_test()
    check_code_vs_spec_timestamps()
    check_api_vs_appendix()

    if WARNINGS:
        sys.stderr.write("\n=== Consistency Check ===\n")
        for w in WARNINGS:
            sys.stderr.write(f"  {w}\n")
        sys.stderr.write("\n")
    return len(WARNINGS)


if __name__ == '__main__':
    sys.exit(main())
