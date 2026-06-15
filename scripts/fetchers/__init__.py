"""
数据源获取器统一入口，支持自动回退：
  westock-data(local, primary 始终可用)
  → neodata-financial-search (补充，需要有效 token)
  → 东方财富(fallback1) → 新浪财经(fallback2) → 腾讯财经(fallback3)

用法:
    from fetchers import get_available_fetcher
    fetcher = get_available_fetcher()
    if fetcher:
        biz = fetcher.fetch_business('601166')
    else:
        print('所有数据源均不可用')
"""

from .base import BaseFetcher
from .westock import WestockFetcher
from .neodata import NeoDataFetcher
from .eastmoney import EastMoneyFetcher
from .sina import SinaFetcher
from .tencent import TencentFetcher

_FETCHER_PRIORITY = [
    WestockFetcher,    # 本地插件，始终可用（主数据源）
    NeoDataFetcher,    # neodata-financial-search（补充，需要有效 token）
    EastMoneyFetcher,  # 东方财富 (被屏蔽时自动跳过)
    SinaFetcher,       # 新浪财经
    TencentFetcher,    # 腾讯财经
]

_fetcher_cache = None


def get_available_fetcher(force_refresh: bool = False) -> BaseFetcher | None:
    """按优先级尝试每个数据源，返回第一个可用的（带缓存）。

    Args:
        force_refresh: 强制重新检测（跳过缓存）

    Returns:
        BaseFetcher 实例或 None（所有源均不可用）
    """
    global _fetcher_cache
    if _fetcher_cache is not None and not force_refresh:
        return _fetcher_cache

    for cls in _FETCHER_PRIORITY:
        fetcher = cls()
        try:
            if fetcher.is_available():
                print(f'  [Fetcher] 选择数据源: {fetcher.source}')
                _fetcher_cache = fetcher
                return fetcher
        except Exception as e:
            print(f'  [Fetcher] {cls.__name__} 检测失败: {e}')
            continue

    _fetcher_cache = None
    print('  [Fetcher] 所有数据源均不可用')
    return None


def clear_fetcher_cache():
    """清理缓存，下次调用 get_available_fetcher 会重新检测。"""
    global _fetcher_cache
    _fetcher_cache = None


# 方法级回退的可用 fetcher 缓存
_fallback_cache: dict[str, BaseFetcher] | None = None


def _build_fallback_cache():
    """构建并缓存除主 fetcher 外的所有可用备选 fetcher。"""
    global _fallback_cache
    if _fallback_cache is not None:
        return _fallback_cache

    primary = get_available_fetcher()
    primary_source = primary.source if primary else None

    _fallback_cache = {}
    for cls in _FETCHER_PRIORITY:
        fetcher = cls()
        if fetcher.source == primary_source:
            continue
        try:
            if fetcher.is_available():
                _fallback_cache[fetcher.source] = fetcher
        except Exception:
            continue
    return _fallback_cache


def clear_fallback_cache():
    """清理方法级回退缓存。"""
    global _fallback_cache
    _fallback_cache = None


def fetch_with_fallback(method: str, code: str, default=None) -> any:
    """对单个方法尝试多个数据源，优先使用当前主 fetcher，失败则尝试备选。

    Args:
        method: 方法名，如 'fetch_supply_chain'
        code: 股票代码
        default: 全部失败时的默认返回值

    Returns:
        第一个返回非空结果的数据源的返回值
    """
    # 先尝试当前主 fetcher（已在全局缓存中）
    primary = get_available_fetcher()
    if primary is not None:
        try:
            result = getattr(primary, method)(code)
            if result and result != default:
                return result
        except Exception:
            pass

    # 主 fetcher 返回空，逐个尝试备选源
    fallbacks = _build_fallback_cache()
    for source_name, fetcher in fallbacks.items():
        try:
            result = getattr(fetcher, method)(code)
            if result and result != default:
                print(f'  [Fetcher] {method}({code}) 回退到数据源: {source_name}')
                return result
        except Exception:
            continue

    return default
