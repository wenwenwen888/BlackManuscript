"""分类 prompt：判断一篇文章是否在嘲讽对方。

输入：标题、正文、来源栏位（left=外媒看国内 / right=中媒看海外）
输出：JSON {pass, target, reason}
"""

SYSTEM = """你是新闻内容分类助手。你的任务是判断一篇文章是否构成"对另一方的嘲讽/批评"。

判定标准：
- "嘲讽"包括：负面评价、讽刺修辞、批评立场、揭露问题、质疑动机、扣帽子。
- 不算嘲讽的：纯中性事实报道、单纯赞美己方（不涉及对方）、纯科普/技术介绍。
- 边界案例：报道对方负面新闻但立场中立（如 Reuters 客观报道中国某政策受挫）——这种**算**，因为它呈现了对方的负面。
- 明确不算：天气预报、纯经济数据、体育赛果、文化活动通报。

栏位说明：
- side="left"：来源是外媒，应嘲讽/批评的对象是中国（含港澳台、华人、中国政策/企业/社会）
- side="right"：来源是中国官媒，应嘲讽/批评的对象是海外（外国政府/社会/政策/企业）

输出严格的 JSON，不要 markdown 代码块：
{
  "pass": true/false,                  // 是否构成对另一方的嘲讽/批评
  "target": "中国|美国|欧洲|日本|...",  // 被嘲讽/批评的具体对象（国家或地区，无法判断填"未知"）
  "reason": "一句话说明判定理由"        // 不超过 30 字
}
"""

USER_TEMPLATE = """来源栏位：{side_label}
来源媒体：{source}
文章标题：{title}

正文（{body_lang}）：
{body}

请按系统指令返回 JSON。"""


def build(side: str, source: str, title: str, body: str, body_lang: str) -> list[dict]:
    """构造 OpenAI 风格的 messages 数组。

    side: "left" 或 "right"
    body_lang: "zh" 或 "en"
    """
    side_label = "外媒嘲讽国内（被嘲讽对象：中国）" if side == "left" else "中媒嘲讽海外（被嘲讽对象：外国）"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER_TEMPLATE.format(
            side_label=side_label,
            source=source,
            title=title,
            body_lang="中文" if body_lang == "zh" else "英文",
            body=body[:4000],  # 截断，分类不需要全文
        )},
    ]


# 期望的 JSON 输出格式（给解析器参考）
OUTPUT_SCHEMA = {
    "pass": bool,
    "target": str,
    "reason": str,
}
