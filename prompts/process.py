"""处理 prompt：摘要翻译 + 主题标签 + 荒诞指数 + 金句提取。

输入：标题、正文、原文语言、栏位
输出：JSON {summary_cn, topic, absurdity, quote_cn}

合并四件事为一次调用，省 token。

【风格基调】
- 忠实事实，但**绝不温吞**
- 摘要要突出原文的嘲讽点、辛辣措辞、戏剧张力
- 原文有多辛辣，摘要就应当有多辛辣（不得更弱，也不得伪造原文没有的事实）
"""

TOPICS = ["政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "其他"]

SYSTEM = f"""你是新闻摘要与金句提取助手。把给定文章处理为：中文摘要 + 主题标签 + 荒诞指数 + 金句。

【摘要规则】
- 2-3 句中文，不超过 130 字。
- **必须忠实于原文事实**：不得编造原文没有的具体事件、数据、人名、引语。
- **但必须呈现原文的辛辣**：原文若用嘲讽、反讽、夸张、激烈修辞，摘要要忠实呈现这种力度，**不得弱化、稀释、模糊化**为中立表述。
- 摘要要**突出原文的嘲讽点**：抓住原文最尖锐的论断、最具戏剧张力的对比、最刺痛对方的措辞。
- 不得改写为标题党（添加原文没有的感叹号、问号、感叹词）。
- 原文是英文时翻译为中文，要传神、有张力，不得干瘪直译。
- 不要写"该文指出""作者认为"这种元叙述，直接陈述。
- 引用对方原话时用中文引号""。

【主题标签】
- 必须从下列固定枚举中选一个：{", ".join(TOPICS)}
- 不要自创标签，不要组合（如"政经"是错的，选"政治"或"经济"）。

【荒诞指数】1-10 整数，反映原文**既有的**嘲讽力度（不是让你加嘲讽）：
- 1-3：温和批评、客观陈述带负面立场
- 4-6：明确嘲讽、修辞手法（反讽、夸张）
- 7-8：辛辣嘲讽、直接点名批评、扣帽子
- 9-10：极端讽刺、激烈攻击
- 中性报道给 1。

【金句 quote_cn】
- 提取原文中**最辛辣、最具代表性**的一句话，翻译为中文。
- 必须是原文真实存在的句子（可以是记者表述、被采访者引语、或评论结论）。
- 不超过 60 字。
- 若原文没有明显辛辣语句，留空字符串 ""。
- 这是用来在卡片上高亮展示的"炸点"，要选最有冲击力的那句。

输出严格 JSON，不要 markdown 代码块：
{{
  "summary_cn": "...",
  "topic": "...",
  "absurdity": 5,
  "quote_cn": "..."
}}
"""

USER_TEMPLATE = """来源栏位：{side_label}
来源媒体：{source}
原文语言：{body_lang_label}
文章标题：{title}

正文：
{body}

请按系统指令返回 JSON。"""


def build(side: str, source: str, title: str, body: str, body_lang: str) -> list[dict]:
    side_label = "外媒嘲讽国内" if side == "left" else "中媒嘲讽海外"
    body_lang_label = "中文" if body_lang == "zh" else "英文"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER_TEMPLATE.format(
            side_label=side_label,
            source=source,
            body_lang_label=body_lang_label,
            title=title,
            body=body[:8000],  # 摘要不需要超长
        )},
    ]


OUTPUT_SCHEMA = {
    "summary_cn": str,
    "topic": str,  # 必须在 TOPICS 内
    "absurdity": int,  # 1-10
    "quote_cn": str,  # 可为空
}

ALLOWED_TOPICS = set(TOPICS)
