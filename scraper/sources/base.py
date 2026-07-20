"""源适配基类 + Article 数据结构。

每个源继承 Source，实现：
  - list_articles(limit) -> list[Article]  从列表页拿候选文章
  - extract_article(url)  -> Article        深入详情页填充正文+元数据

side 字段决定栏位：
  - "left"  外媒嘲讽国内（被嘲讽对象是中国）
  - "right" 中媒嘲讽海外（被嘲讽对象是外国）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod


@dataclass
class Article:
    """候选文章。

    list_articles 阶段只需填 url+title+published+source 字段，
    extract_article 阶段填充 body 和 body_lang。
    """
    url: str
    title: str                                    # 原文标题（英文/中文）
    source: str                                   # 媒体名
    source_country: str                           # ISO 国家代码
    side: str                                     # "left" or "right"
    published: str = ""                           # YYYY-MM-DD
    body: str = ""                                # 正文
    body_lang: str = "zh"                         # "zh" / "en"
    # LLM 处理后填充
    title_cn: str = ""                            # 中文标题（可由 LLM 翻译，或直接用 title）
    summary_cn: str = ""
    topic: str = ""
    absurdity: int = 0
    quote_cn: str = ""
    # 镜像议题（可选）：左右互搏用，如同属「学术造假」
    mirror_issue: str = ""
    # 状态
    classify_pass: Optional[bool] = None
    validate_pass: Optional[bool] = None
    reject_reason: str = ""


class Source(ABC):
    """所有源的抽象基类。

    子类需要设置：
      name: 源名（中文展示用，如"观察者网"）
      side: "left" 或 "right"
      source_country: ISO 国家代码
    并实现：
      list_articles(limit) -> list[Article]
      extract_article(article) -> Article  就地填充 body/published/body_lang
    """

    name: str = ""
    side: str = ""              # "left" or "right"
    source_country: str = ""

    def __init__(self):
        assert self.name, f"{type(self).__name__} 必须设置 name"
        assert self.side in ("left", "right"), f"{type(self).__name__}.side 必须是 left/right"
        assert self.source_country, f"{type(self).__name__} 必须设置 source_country"

    @abstractmethod
    def list_articles(self, limit: int = 20) -> list[Article]:
        """从列表页抓取候选文章列表（仅元数据，无正文）。"""
        ...

    @abstractmethod
    def extract_article(self, article: Article) -> Article:
        """深入详情页，填充 body / published / body_lang。失败可返回原 article（body 为空）。"""
        ...

    def make_article(self, url: str, title: str, published: str = "") -> Article:
        """工厂方法：用源的元数据创建 Article。"""
        return Article(
            url=url,
            title=title,
            source=self.name,
            source_country=self.source_country,
            side=self.side,
            published=published,
        )
