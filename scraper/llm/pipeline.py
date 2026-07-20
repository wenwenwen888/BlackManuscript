"""LLM 流水线：classify -> process -> validate 串联。

对单篇文章跑完整流水线，返回处理后的 Article（含 summary_cn / topic / absurdity / quote_cn）。
任何阶段失败都会标记 reject_reason 并（可选）写入 drafts 池。
"""
from __future__ import annotations

import logging
from typing import Optional

from sources.base import Article
from llm.client import LLMClient, LLMError, get_client
from llm.safety import hit_blacklist, save_to_drafts

# 直接 import prompt 模板
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "prompts"))
import classify as classify_prompt
import process as process_prompt
import validate as validate_prompt

logger = logging.getLogger(__name__)


def process_article(
    article: Article,
    *,
    client: Optional[LLMClient] = None,
    save_drafts_on_fail: bool = True,
) -> Article:
    """对一篇文章跑完整流水线，就地更新 article 字段。

    流程：
      1. 黑名单关键词扫描 -> 命中即拒
      2. classify（用便宜模型快筛）
      3. process（摘要+标签+荒诞指数+金句，用强模型）
      4. 黑名单二次扫描（摘要+金句）
      5. validate（摘要是否歪曲原意）

    任何阶段失败会设 article.reject_reason，且 classify_pass/validate_pass 反映状态。
    """
    client = client or get_client()
    process_model = _get_strong_model()

    # 0. 预检：body 必须非空
    if not article.body or len(article.body) < 50:
        article.classify_pass = False
        article.reject_reason = "body 太短或为空"
        if save_drafts_on_fail:
            save_to_drafts(article, "body_too_short")
        return article

    # 1. 黑名单预扫描
    hit = hit_blacklist(article.title + " " + article.body[:2000])
    if hit:
        article.classify_pass = False
        article.reject_reason = f"blacklist: {hit}"
        if save_drafts_on_fail:
            save_to_drafts(article, f"blacklist:{hit}")
        return article

    # 2. classify
    try:
        msgs = classify_prompt.build(
            side=article.side, source=article.source,
            title=article.title, body=article.body, body_lang=article.body_lang,
        )
        result = client.chat_json(msgs)  # 用默认（便宜）模型
        article.classify_pass = bool(result.get("pass", False))
        if not article.classify_pass:
            article.reject_reason = f"classify: {result.get('reason', 'no reason')}"
            if save_drafts_on_fail:
                save_to_drafts(article, f"classify_reject:{result.get('reason','')}")
            return article
    except LLMError as e:
        article.classify_pass = False
        article.reject_reason = f"classify_error: {e}"
        logger.error("classify LLM error for %s: %s", article.url, e)
        return article

    # 3. process（摘要+标签+荒诞指数+金句）
    try:
        msgs = process_prompt.build(
            side=article.side, source=article.source,
            title=article.title, body=article.body, body_lang=article.body_lang,
        )
        result = client.chat_json(msgs, model=process_model)
        article.summary_cn = result.get("summary_cn", "").strip()
        article.topic = result.get("topic", "其他")
        if article.topic not in process_prompt.ALLOWED_TOPICS:
            article.topic = "其他"
        try:
            article.absurdity = int(result.get("absurdity", 5))
            if not (1 <= article.absurdity <= 10):
                article.absurdity = 5
        except (TypeError, ValueError):
            article.absurdity = 5
        article.quote_cn = result.get("quote_cn", "").strip()
        # 标题：中文源直接用原标题，英文源用 og:title（extract 阶段已设置）
        article.title_cn = article.title if article.body_lang == "zh" else _translate_title(client, article.title)
    except LLMError as e:
        article.reject_reason = f"process_error: {e}"
        logger.error("process LLM error for %s: %s", article.url, e)
        if save_drafts_on_fail:
            save_to_drafts(article, f"process_error:{e}")
        return article

    # 4. 黑名单二次扫描（针对生成内容）
    combined = article.summary_cn + " " + article.quote_cn
    hit = hit_blacklist(combined)
    if hit:
        article.validate_pass = False
        article.reject_reason = f"blacklist_in_output: {hit}"
        if save_drafts_on_fail:
            save_to_drafts(article, f"output_blacklist:{hit}")
        return article

    # 5. validate
    try:
        msgs = validate_prompt.build(
            body=article.body, summary_cn=article.summary_cn, body_lang=article.body_lang,
        )
        result = client.chat_json(msgs)
        distorted = bool(result.get("distorted", False))
        if distorted:
            article.validate_pass = False
            article.reject_reason = f"validate_distorted: {result.get('reason','')}"
            if save_drafts_on_fail:
                save_to_drafts(article, f"validate_distorted:{result.get('reason','')}")
            return article
        article.validate_pass = True
    except LLMError as e:
        # validate 调用失败视为硬拦截：宁可不发，避免未校验内容上线
        article.validate_pass = False
        article.reject_reason = f"validate_error: {e}"
        logger.error("validate LLM error for %s: %s", article.url, e)
        if save_drafts_on_fail:
            save_to_drafts(article, f"validate_error:{e}")
        return article

    return article


def _get_strong_model() -> Optional[str]:
    """读环境变量 LLM_MODEL_STRONG，未设返回 None（用默认模型）。"""
    import os
    return os.environ.get("LLM_MODEL_STRONG") or None


def _translate_title(client: LLMClient, title: str) -> str:
    """英文标题翻译为中文。简单调用，不复杂。"""
    if not title:
        return ""
    # 多数英文源 og:title 已是 slug 形式，简单翻译即可
    try:
        msgs = [
            {"role": "system", "content": "把给定英文新闻标题翻译为中文，要求简洁有力、保留原文的嘲讽或戏剧张力，不超过 30 字。只输出中文标题，不要任何解释。"},
            {"role": "user", "content": title},
        ]
        out = client.chat(msgs, max_tokens=80).strip()
        # 去掉可能的引号
        out = out.strip("\"'""''")
        return out or title
    except LLMError:
        return title
