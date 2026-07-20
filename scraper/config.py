"""配置：源注册表 + 默认开关 + 路径。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict

from sources.base import Source

# 项目根
ROOT = Path(__file__).resolve().parent.parent
SCRAPER_DIR = Path(__file__).resolve().parent
SITE_DIR = ROOT / "site"

# 输出路径
OUTPUT_DAILY_DIR = SCRAPER_DIR / "output" / "daily"
OUTPUT_DRAFTS_DIR = SCRAPER_DIR / "output" / "drafts"

# Astro content collection 目录（拷贝产物到这里）
SITE_DAILY_DIR = SITE_DIR / "src" / "content" / "daily"


# 源注册表：name -> (factory, side, default_enabled)
def _register():
    """延迟 import 避免循环依赖。"""
    from sources.guancha import GuanchaSource
    from sources.huanqiu import HuanqiuSource
    from sources.cgtn import CgtnSource
    from sources.bbc import BbcSource
    from sources.dw import DwSource
    from sources.ap import ApSource
    return {
        "guancha": GuanchaSource,
        "huanqiu": HuanqiuSource,
        "cgtn": CgtnSource,
        "bbc": BbcSource,
        "dw": DwSource,
        "ap": ApSource,
    }


# 默认启用：右栏中媒 + 左栏外媒（BBC/DW/AP 国内可探达）
DEFAULT_SOURCES = ["guancha", "huanqiu", "cgtn", "bbc", "dw", "ap"]


def get_all_sources() -> Dict[str, Source]:
    """返回所有已注册源的实例。"""
    return {name: cls() for name, cls in _register().items()}


def get_enabled_sources(names: list[str] | None = None) -> Dict[str, Source]:
    """返回启用的源。names 为 None 时用 DEFAULT_SOURCES。"""
    all_sources = get_all_sources()
    wanted = names or DEFAULT_SOURCES
    return {n: all_sources[n] for n in wanted if n in all_sources}
