"""安全阀：关键词黑名单 + drafts 池。

被拦截的内容不发布，写入 drafts/ 待人工复核。
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# 关键词黑名单：命中即拦截（不进发布池）
# 政治极端敏感、可能引发法律风险的具体表述
KEYWORD_BLACKLIST = [
    # 具体在任最高领导人姓名（避免直接点名）
    # 这里不写死，运行时从环境变量 BLACKLIST_KEYWORDS 读，逗号分隔
]

# 默认 drafts 路径
DEFAULT_DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "drafts")


def get_blacklist() -> list[str]:
    """读取黑名单关键词。优先用环境变量，否则用内置默认。"""
    env = os.environ.get("BLACKLIST_KEYWORDS", "")
    if env:
        return [k.strip() for k in env.split(",") if k.strip()]
    return KEYWORD_BLACKLIST


def hit_blacklist(text: str) -> str | None:
    """若 text 命中黑名单关键词，返回命中的词；否则 None。"""
    bl = get_blacklist()
    if not bl:
        return None
    for kw in bl:
        if kw in text:
            return kw
    return None


def save_to_drafts(article, reason: str, drafts_dir: str | None = None) -> str:
    """把被拦截的文章写入 drafts 池。返回写入的文件路径。"""
    d = Path(drafts_dir or DEFAULT_DRAFTS_DIR).resolve()
    d.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 用 url 末尾片段作为文件名一部分
    slug = article.url.rstrip("/").split("/")[-1][:40] or "article"
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)
    fname = f"{ts}_{slug}.json"
    path = d / fname

    record = {
        "intercepted_at": datetime.now().isoformat(),
        "reason": reason,
        "article": {
            "url": article.url,
            "title": article.title,
            "source": article.source,
            "source_country": article.source_country,
            "side": article.side,
            "published": article.published,
            "body": article.body[:3000],
            "body_lang": article.body_lang,
            "summary_cn": article.summary_cn,
            "quote_cn": article.quote_cn,
            "topic": article.topic,
            "absurdity": article.absurdity,
            "classify_pass": article.classify_pass,
            "validate_pass": article.validate_pass,
            "reject_reason": article.reject_reason,
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    logger.info("Saved to drafts: %s (reason: %s)", path.name, reason)
    return str(path)
