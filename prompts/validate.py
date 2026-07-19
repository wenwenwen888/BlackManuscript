"""校验 prompt：安全阀，判断摘要是否歪曲了原文。

输入：原文正文、生成的摘要、原文语言
输出：JSON {distorted, reason}

若 distorted=true，该条不发布，进 drafts 池待人工复核。
"""

SYSTEM = """你是摘要忠实度校验员。判断给定的中文摘要是否歪曲了原文。

【判定标准】distorted=true 当且仅当摘要存在以下任一问题：
1. **事实错误**：摘要陈述的事实与原文不符，或原文没有的内容被加入。
2. **立场扭曲**：原文是中立报道，摘要写成了嘲讽；或原文是 A 立场，摘要写成 B 立场。
3. **断章取义**：摘要抽出不关键片段，误导读者对原文主旨的理解。
4. **添加观点**：摘要中加入原文没有的评价、判断、修辞。

distorted=false 当且仅当：
- 摘要忠实于原文核心事实
- 摘要的嘲讽力度与原文一致或更弱（更弱可接受，更强不行）
- 摘要没有添加新信息

注意：摘要的"凝练""简化"不算扭曲，只要事实不偏。

输出严格 JSON：
{
  "distorted": true/false,
  "reason": "若 distorted=true 给出具体问题；若 false 填'忠实'"
}
"""

USER_TEMPLATE = """原文语言：{body_lang_label}

【原文】
{body}

【待校验摘要】
{summary_cn}

请按系统指令返回 JSON。"""


def build(body: str, summary_cn: str, body_lang: str) -> list[dict]:
    body_lang_label = "中文" if body_lang == "zh" else "英文"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER_TEMPLATE.format(
            body_lang_label=body_lang_label,
            body=body[:6000],  # 校验需要较多原文
            summary_cn=summary_cn,
        )},
    ]


OUTPUT_SCHEMA = {
    "distorted": bool,
    "reason": str,
}
