"""HTTP 抓取器：统一 UA、超时、重试、限速。

只用标准库 urllib，不引入 requests 依赖，部署到 VPS 更轻量。
如需切代理或换 headless 浏览器，只改这个文件。
"""
from __future__ import annotations

import time
import random
import urllib.request
import urllib.error
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 全局请求间隔（秒），避免对源站压力过大
_LAST_REQUEST_TS: dict[str, float] = {}
MIN_INTERVAL_PER_HOST = 1.5  # 同一域名两次请求最少间隔


def fetch(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = 15,
    retries: int = 3,
    backoff_base: float = 1.5,
    encoding: str = "utf-8",
) -> str:
    """抓取 URL 返回解码后的字符串。

    自动重试 3 次（指数退避 + 抖动），失败抛最后一次异常。
    限速：同一 host 两次请求间隔 >= MIN_INTERVAL_PER_HOST 秒。
    """
    _rate_limit(url)

    h = {**DEFAULT_HEADERS, **(headers or {})}
    last_exc: Optional[Exception] = None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                # 优先用响应头里的编码，没有就用默认
                enc = encoding
                if resp.headers.get("Content-Type"):
                    ct = resp.headers.get("Content-Type", "")
                    if "charset=" in ct:
                        enc = ct.split("charset=")[-1].strip().split(";")[0]
                return raw.decode(enc, errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_exc = e
            wait = backoff_base ** attempt + random.uniform(0, 0.5)
            logger.warning(
                "fetch attempt %d/%d failed for %s: %s, retry in %.1fs",
                attempt + 1, retries, url, e, wait,
            )
            time.sleep(wait)

    assert last_exc is not None
    raise last_exc


def _rate_limit(url: str) -> None:
    """对同一 host 做最小间隔限制。"""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
    except Exception:
        host = url

    now = time.time()
    last = _LAST_REQUEST_TS.get(host, 0)
    elapsed = now - last
    if elapsed < MIN_INTERVAL_PER_HOST:
        time.sleep(MIN_INTERVAL_PER_HOST - elapsed)
    _LAST_REQUEST_TS[host] = time.time()
