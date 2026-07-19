"""各 prompt 的示例输入/输出，用于回归测试和向协作者演示。

这些示例都基于真实抓取到的文章结构构造，可作为 LLM 调用的"金标准"对照。
"""

from classify import build as build_classify
from process import build as build_process
from validate import build as build_validate


# ===== 示例 1：观察者网（右栏，中文）=====
# 来源：观察者网专栏
EXAMPLE_1 = {
    "side": "right",
    "source": "观察者网",
    "source_url": "https://www.guancha.cn/internation/2026_07_19_824295.shtml",
    "source_country": "cn",
    "title": "俄罗斯警告日本：与乌克兰合作造无人机，等同于“帮助杀害俄罗斯公民”",
    "body": (
        "俄罗斯塔斯社7月19日报道称，俄罗斯外交部副部长安德烈·鲁登科在采访中表示，"
        "日本与乌克兰在无人机方面的合作等同于“帮助杀害俄罗斯公民”。"
        "“我们正在密切关注日本无人机制造商与乌克兰作战无人机开发商之间合作的发展情况。”"
        "鲁登科直言，“鉴于乌克兰频繁使用无人机对俄罗斯民用目标进行恐怖主义袭击，"
        "我们将与基辅政权的这种合作视为一种公开的敌对行为……”"
        "7月初，日本外相与乌克兰外长在东京举行会谈，将无人机合作列为核心议程。"
    ),
    "body_lang": "zh",
    "expected_classify": {"pass": False, "target": "日本", "reason": "主语是俄罗斯批评日本，非中国媒体嘲讽海外"},
    # 注：这条实际是俄方声明被中国媒体转引。是否符合右栏定位存疑——
    # 它属于"中国媒体嘲讽/批评海外的报道"，但实际原文出自俄罗斯官方。
    # 这种"借嘴"型内容也是 PLAN.md 想要的，应通过；reason 反映模型判断的合理性。
}


# ===== 示例 2：CGTN（右栏，英文）=====
# 来源：CGTN opinions
EXAMPLE_2 = {
    "side": "right",
    "source": "CGTN",
    "source_url": "https://news.cgtn.com/news/2026-07-03/China-s-air-conditioners-cool-Europe-s-hotheads-1OtJnEpLK80/p.html",
    "source_country": "cn",
    "title": "China's air conditioners cool Europe's hotheads",
    "body": (
        "Editor's note: CGTN's First Voice provides instant commentary on breaking stories. "
        "Heatwaves are baking Europe, and China-made air conditioners have become a lifeline. "
        "The European politicians should face the reality, that China is indispensable for the "
        "lifestyle that the Europeans want to keep, or if they aspire for an even better life."
    ),
    "body_lang": "en",
    "expected_classify": {"pass": True, "target": "欧洲", "reason": "CGTN 讽刺欧洲政客一边反华一边离不开中国产品"},
    "expected_process": {
        "summary_cn": "热浪席卷欧洲，中国产空调成救命神器；CGTN 评论嘲讽欧洲政客一边反华一边离不开中国产品。",
        "topic": "社会",
        "absurdity": 7,
        "quote_cn": "离开中国空调，欧洲政客连夏天都过不去。",
    },
    "expected_validate": {"distorted": False, "reason": "忠实"},
}


# ===== 示例 3：环球时报（右栏，中文，转引新华网来源）=====
EXAMPLE_3 = {
    "side": "right",
    "source": "环球时报（转引新华网）",
    "source_url": "https://world.huanqiu.com/article/4SRRiSqejA5",
    "source_country": "cn",
    "title": "美伊互袭，伊朗最高领袖：美总统签字“毫无价值”",
    "body": "美军中央司令部18日在社交媒体发文证实……伊朗最高领袖穆杰塔巴·哈梅内伊18日发表声明称，美方屡次违背其与伊朗总统达成的谅解备忘录。",
    "body_lang": "zh",
    "expected_classify": {"pass": True, "target": "美国", "reason": "报道美方失信、被伊朗反击，呈现美国负面形象"},
}


# ===== 示例 4：负面案例 - 中性报道（应被拒绝）=====
# 模拟 Reuters 客观报道中国 GDP（这类应被 classify 拦截）
EXAMPLE_4_NEUTRAL = {
    "side": "left",
    "source": "Reuters",
    "source_url": "https://www.reuters.com/article/mock-example",
    "source_country": "uk",
    "title": "China's Q2 GDP grows 5.1% year-on-year, in line with forecasts",
    "body": "China's economy expanded 5.1% in the second quarter from a year earlier, matching analysts' expectations, official data showed on Monday.",
    "body_lang": "en",
    "expected_classify": {"pass": False, "target": "中国", "reason": "纯数据报道，无嘲讽/批评立场"},
}


def render_example(name: str, ex: dict, kind: str) -> dict:
    """把示例渲染成实际可调用的 messages 数组。"""
    if kind == "classify":
        return build_classify(
            side=ex["side"], source=ex["source"],
            title=ex["title"], body=ex["body"], body_lang=ex["body_lang"],
        )
    if kind == "process":
        return build_process(
            side=ex["side"], source=ex["source"],
            title=ex["title"], body=ex["body"], body_lang=ex["body_lang"],
        )
    if kind == "validate":
        return build_validate(
            body=ex["body"], summary_cn=ex["expected_process"]["summary_cn"],
            body_lang=ex["body_lang"],
        )
    raise ValueError(kind)


if __name__ == "__main__":
    import json
    print("=" * 60)
    print("示例 2 - classify 调用（CGTN 嘲讽欧洲）")
    print("=" * 60)
    msgs = render_example("ex2", EXAMPLE_2, "classify")
    print(json.dumps(msgs, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("示例 2 - process 调用")
    print("=" * 60)
    msgs = render_example("ex2", EXAMPLE_2, "process")
    print(json.dumps(msgs, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("示例 4 - classify 调用（中性报道，应被拒）")
    print("=" * 60)
    msgs = render_example("ex4", EXAMPLE_4_NEUTRAL, "classify")
    print(json.dumps(msgs, ensure_ascii=False, indent=2))
