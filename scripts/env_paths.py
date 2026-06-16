"""
环境路径配置 — 集中管理所有外部工具和插件路径。

用法:
    from scripts.env_paths import get_node, get_westock, get_neodata, get_python

环境变量（可设置 .env 或在系统环境变量中配置）:
    NODE_PATH       — Node.js 可执行文件路径（默认: "node"，依赖系统 PATH）
    WESTOCK_PATH    — westock-data 插件目录路径（必需）
    NEODATA_PATH    — neodata-financial-search 插件目录路径（可选）
    API_PORT        — API 服务端口（默认: 8766）
"""

import os
import sys
import shutil
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_python() -> str:
    return sys.executable or 'python'


def get_node() -> str:
    env_node = os.environ.get('NODE_PATH')
    if env_node and os.path.isfile(env_node):
        return env_node
    which_node = shutil.which('node')
    if which_node:
        return which_node
    return 'node'


def get_westock() -> str:
    env_path = os.environ.get('WESTOCK_PATH')
    if env_path and os.path.isdir(env_path):
        return env_path
    relative = os.path.join(ROOT, '..', 'westock-data')
    if os.path.isdir(relative):
        return os.path.abspath(relative)
    home = Path.home()
    candidates = [
        home / '.workbuddy' / 'plugins' / 'marketplaces' / 'experts' / 'plugins' / 'stock-partner-team' / 'skills' / 'westock-data',
        home / '.workbuddy' / 'plugins' / 'marketplaces' / 'cb_teams_marketplace' / 'plugins' / 'finance-data' / 'skills' / 'westock-data',
    ]
    for p in candidates:
        if p.is_dir():
            return str(p)
    return ''


def get_neodata() -> str:
    env_path = os.environ.get('NEODATA_PATH')
    if env_path and os.path.isdir(env_path):
        return env_path
    relative = os.path.join(ROOT, '..', 'neodata-financial-search')
    if os.path.isdir(relative):
        return os.path.abspath(relative)
    home = Path.home()
    candidates = [
        home / '.workbuddy' / 'plugins' / 'marketplaces' / 'cb_teams_marketplace' / 'plugins' / 'finance-data' / 'skills' / 'neodata-financial-search',
        home / '.workbuddy' / 'plugins' / 'marketplaces' / 'experts' / 'plugins' / 'stock-partner-team' / 'skills' / 'neodata-financial-search',
    ]
    for p in candidates:
        if p.is_dir():
            return str(p)
    return ''


def get_port(default: int = 8766) -> int:
    try:
        return int(os.environ.get('API_PORT', str(default)))
    except (ValueError, TypeError):
        return default


def get_vite_port(default: int = 5173) -> int:
    try:
        return int(os.environ.get('VITE_PORT', str(default)))
    except (ValueError, TypeError):
        return default


def get_vite_api_target(default: str = 'http://127.0.0.1:8766') -> str:
    return os.environ.get('VITE_API_TARGET', default)
