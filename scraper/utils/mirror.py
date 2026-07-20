"""左右互搏的「镜像议题」：同议题骨架、不同地理对象。

例：左「中国学术造假」↔ 右「海外学术造假」——粗粒度 topic 相同还不够，
议题类型（mirror_issue）也要对齐。
"""
from __future__ import annotations

from typing import Optional

# slug -> (中文展示名, 关键词)
# 关键词用于从标题/摘要推断；左右共用同一套骨架词
MIRROR_ISSUES: dict[str, tuple[str, list[str]]] = {
    "academic_integrity": ("学术诚信", [
        "学术", "论文", "造假", "撤稿", "同行评议", "科研不端", "抄袭", "数据造假",
        "paper mill", "retraction", "plagiarism",
    ]),
    "anti_corruption": ("反腐贪腐", [
        "反腐", "打虎", "贪腐", "落马", "政治献金", "游说", "利益输送", "腐败",
        "lobby", "corruption",
    ]),
    "political_theater": ("政治表演", [
        "两会", "议会", "国会", "两党", "立法停摆", "表忠", "互撕", "否决",
        "议事", "表演", "gridlock", "shutdown",
    ]),
    "security_budget": ("维稳安保", [
        "维稳", "安保", "监控", "军工", "安全预算", "监控体系", "Surveillance",
        "homeland security",
    ]),
    "stock_policy": ("政策市", [
        "政策牛", "护盘", "国家队", "救市", "美联储", "加息", "流动性", "鲍威尔",
        "fed", "bailout", "plunge protection",
    ]),
    "stock_breadth": ("结构性行情", [
        "结构性", "七巨头", "权重", "中小盘", "集中度", "广度", "mag7", "magnificent",
    ]),
    "stock_foreign_flow": ("外资流向", [
        "北向", "外资", "热钱", "资本外流", "跟跌", "华尔街遥控器", "被动跟随",
    ]),
    "ipo_listing": ("IPO上市", [
        "IPO", "注册制", "堰塞湖", "上市", "新股", "SPAC", "排队",
    ]),
    "housing": ("房地产", [
        "楼市", "房价", "去库存", "房企", "按揭", "住房", "housing", "mortgage",
    ]),
    "sovereign_debt": ("政府债务", [
        "地方债", "隐性债务", "国债", "债务上限", "展期", "城投", "debt ceiling",
        "sovereign debt",
    ]),
    "youth_cost": ("青年成本", [
        "躺平", "内卷", "年轻人", "就业", "生育", "房价", "工时", "genz",
    ]),
    "healthcare": ("医保医疗", [
        "医保", "医疗", "药价", "保险", "health", "medicare", "nhs",
    ]),
    "school_safety": ("校园安全", [
        "校园", "霸凌", "欺凌", "校园枪", "校园安全", "school shooting", "bullying",
    ]),
    "gun_violence": ("枪支暴力", [
        "枪击", "枪支", "控枪", "枪响", "gun", "firearm", "nra",
    ]),
    "homelessness": ("无家可归", [
        "无家可归", "流浪汉", "帐篷", "homeless", "encampment",
    ]),
    "drug_crisis": ("毒品危机", [
        "芬太尼", "毒品", "阿片", "吸毒", "fentanyl", "opioid",
    ]),
    "ai_alignment": ("AI对齐", [
        "AI", "大模型", "审查", "幻觉", "对齐", "chatbot", "chatgpt", "deepseek",
    ]),
    "semiconductor": ("芯片半导体", [
        "芯片", "光刻", "半导体", "制裁芯片", "chip", "semiconductor", "asml",
    ]),
    "tech_privacy": ("科技隐私", [
        "隐私", "杀熟", "算法", "用户协议", "数据", "privacy", "algorithm",
    ]),
    "military_posture": ("军事姿态", [
        "军演", "台海", "航母", "北约", "基地", "威慑", "军费", "nato", "deterrence",
    ]),
    "diplomacy_double": ("外交双标", [
        "人权", "制裁", "双标", "战狼", "一带一路", "峰会", "签证", "制裁清单",
        "sanctions", "human rights",
    ]),
    "censorship": ("审查言论", [
        "审查", "删帖", "禁书", "书店", "取消文化", "言论", "国安", "censorship",
        "cancel culture",
    ]),
    "climate_policy": ("气候能源", [
        "双碳", "煤电", "气候", "热浪", "碳", "天然气", "油车", "排放", "climate",
        "emission",
    ]),
    "film_propaganda": ("电影宣传", [
        "主旋律", "包场", "票房", "配额", "下架", "好莱坞", "过审", "奥斯卡",
        "漫威", "box office",
    ]),
    "celebrity_scandal": ("明星塌房", [
        "塌房", "流量", "饭圈", "选秀", "丑闻", "取消", "明星", "scandal",
    ]),
    "sports_commerce": ("体育商业", [
        "世界杯", "票价", "球迷", "体育", "联赛", "world cup",
    ]),
    "media_narrative": ("舆论叙事", [
        "民调", "统计口径", "事实标签", "删帖", "舆情", "叙事", "poll",
    ]),
    "urban_memory": ("城市记忆", [
        "城市更新", "拆迁", "历史街区", "文物", "博物馆",
    ]),
}


def issue_label(slug: str) -> str:
    meta = MIRROR_ISSUES.get(slug)
    return meta[0] if meta else (slug or "同题")


def guess_mirror_issue(*texts: str) -> str:
    """从标题/摘要推断镜像议题；无匹配返回空串。"""
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return ""
    best, score = "", 0
    for slug, (_label, kws) in MIRROR_ISSUES.items():
        s = 0
        for kw in kws:
            if kw.lower() in blob:
                s += 2 if len(kw) >= 3 else 1
        if s > score:
            best, score = slug, s
    return best if score >= 2 else ""


def mirror_pair_score(
    left_issue: str,
    right_issue: str,
    left_text: str,
    right_text: str,
    *,
    absurdity_sum: float = 0,
) -> float:
    """镜像配对得分。同 mirror_issue 最高；仅同粗主题且议题不同则接近 0。"""
    if left_issue and right_issue and left_issue == right_issue:
        return 100.0 + absurdity_sum

    # 双方都能猜到议题但不一致：拒绝硬凑
    if left_issue and right_issue and left_issue != right_issue:
        return 0.0

    # 一方有标签：用关键词重叠做弱匹配
    issue = left_issue or right_issue
    if issue and issue in MIRROR_ISSUES:
        kws = MIRROR_ISSUES[issue][1]
        lt, rt = left_text.lower(), right_text.lower()
        hits = sum(1 for kw in kws if kw.lower() in lt and kw.lower() in rt)
        if hits >= 1:
            return 40.0 + hits * 5 + absurdity_sum * 0.1

    # 标题/摘要字符级粗重叠（很弱，几乎不当真配对）
    noise = set("的了在是与和及对把被从到也就都而")
    ls = set(left_text) - noise - set(" \n\t，。！？、：；“”‘’\"'")
    rs = set(right_text) - noise - set(" \n\t，。！？、：；“”‘’\"'")
    overlap = len(ls & rs)
    if overlap >= 6:
        return 15.0 + min(overlap, 12) + absurdity_sum * 0.05
    return 0.0


def ensure_mirror_issue(item: dict) -> str:
    """给文章 dict 补上 mirror_issue（就地修改并返回）。"""
    existing = (item.get("mirror_issue") or "").strip()
    if existing:
        return existing
    guessed = guess_mirror_issue(
        item.get("title_cn") or "",
        item.get("summary_cn") or "",
        item.get("quote_cn") or "",
    )
    if guessed:
        item["mirror_issue"] = guessed
    return guessed
