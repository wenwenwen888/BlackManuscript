"""无 LLM 时的启发式：主题、摘要、嘲讽门控、假链过滤。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from sources.base import Article

FAKE_HOST_MARKERS = (
    "example.com",
    "example.org",
    "localhost",
    "127.0.0.1",
)

# left：明显在夸中国 / 嘲讽外国 → 剔除
LEFT_PRAISE_PATTERNS = [
    r"杀疯了",
    r"碾压",
    r"跪求",
    r"遥遥领先",
    r"完胜",
    r"吊打",
    r"横扫欧洲",
    r"横扫全球",
    r"领先世界",
    r"令.*羡慕",
    r"震惊世界的中国",
    r"takes .* by surprise",
    r"more favorably",
    r"leads the world",
    r"success story",
    r"miracle",
]

# left：明显无关娱乐/体育等（除非标题同时含中国批评词）
LEFT_OFFTOPIC = [
    r"世界杯",
    r"World Cup",
    r"欧冠",
    r"NBA",
]

# right：明显在夸中国自己、不指向海外批评 → 剔除
RIGHT_SELF_PRAISE_PATTERNS = [
    r"^中国.*再创新高",
    r"中国模式.*优越",
    r"充分证明.*正确",
    r"reputation soars",
    r"Chinese modernization",
    r"Shenzhen speed",
    r"steps up,? not dictates",
    r"appeal and lessons of China",
    r"people.?s gauge",
    r"AI for good",
    r"future for all",
    r"green development",
    r"Dear You",
    r"international students on Chi",
    r"growth momentum",
    r"iconic trends",
    r"right to development begins",
    r"WAICO",
    r"solo performance by any single",
]

# 越靠前优先级越高（同分时取前者）；关键词带权重
TOPIC_RULES: list[tuple[str, list[tuple[str, int]]]] = [
    ("电影", [
        ("电影", 3), ("票房", 3), ("奥斯卡", 3), ("好莱坞", 3), ("院线", 3),
        ("影节", 3), ("影片", 2), ("导演", 2), ("演员", 1), ("film", 3), ("movie", 3),
        ("cinema", 2), ("box office", 3),
    ]),
    ("娱乐", [
        ("娱乐", 3), ("综艺", 3), ("选秀", 3), ("明星", 2), ("流量", 2),
        ("世界杯", 3), ("足球", 2), ("梅西", 3), ("C罗", 3), ("因凡蒂诺", 3),
        ("国家队", 2), ("克洛普", 3), ("体育", 2), ("球赛", 2),
    ]),
    ("环境", [
        ("气候", 3), ("碳排放", 3), ("污染", 3), ("环保", 3), ("热浪", 3),
        ("排放", 2), ("碳中和", 3), ("沙漠", 2), ("空调", 1), ("climate", 3),
        ("emission", 2), ("heatwave", 3),
    ]),
    ("文化", [
        ("禁书", 3), ("书店", 3), ("书商", 3), ("出版", 3), ("审查", 3),
        ("国安法", 2), ("学术", 2), ("高校", 2), ("教育", 2), ("文化", 2),
        ("言论", 2), ("签证", 1), ("留学生", 2), ("censorship", 3), ("bookseller", 3),
    ]),
    ("军事", [
        ("航母", 3), ("导弹", 3), ("台海", 3), ("战争", 3), ("袭击", 2),
        ("美军", 3), ("以军", 3), ("伊朗", 2), ("霍尔木兹", 3), ("北约", 2),
        ("武器", 2), ("military", 3), ("navy", 2), ("strike", 2),
    ]),
    ("科技", [
        ("芯片", 3), ("人工智能", 3), ("DeepSeek", 3), ("大模型", 3),
        ("AI", 2), ("半导体", 3), ("华为", 2), ("航天", 2), ("火箭", 2),
        ("chatbot", 2), ("tech", 1),
    ]),
    ("经济", [
        ("关税", 3), ("贸易", 3), ("股市", 3), ("债务", 3), ("通胀", 3),
        ("GDP", 3), ("电动车", 3), ("车企", 2), ("钢铁", 2), ("国有化", 2),
        ("经济", 2), ("export", 2), ("trade", 2),
    ]),
    ("外交", [
        ("外交", 3), ("制裁", 3), ("大使", 3), ("峰会", 2), ("联合国", 2),
        ("仲裁", 3), ("南海", 2), ("外交部", 3), ("diplomacy", 3), ("sanctions", 3),
    ]),
    ("政治", [
        ("选举", 3), ("议会", 3), ("国会", 3), ("政党", 2), ("政治局", 3),
        ("反腐", 3), ("维稳", 2), ("政治", 2), ("election", 3), ("politburo", 3),
    ]),
    ("社会", [
        ("民生", 3), ("户籍", 3), ("失业", 3), ("人口", 2), ("疫情", 2),
        ("火灾", 2), ("腐败", 2), ("毒品", 3), ("社会", 1), ("corruption", 2),
    ]),
]


def is_fake_url(url: str) -> bool:
    if not url:
        return True
    host = (urlparse(url).netloc or "").lower()
    return any(m in host for m in FAKE_HOST_MARKERS) or "/example-" in url


def guess_topic(text: str) -> str:
    """按加权关键词打标签；同分取更靠前（更具体）的主题。"""
    t = (text or "").lower()
    best, score = "其他", 0
    for topic, rules in TOPIC_RULES:
        s = 0
        for kw, w in rules:
            if kw.lower() in t:
                s += w
        if s > score:
            best, score = topic, s
    return best


def _clean_zh_noise(text: str) -> str:
    """清洗 DW 等中文源抓取噪声。"""
    s = text or ""
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"图像来源[:：][^广（(]*", "", s)
    s = re.sub(r"广告（德国之声中文网）|\(德国之声中文网）|（德国之声中文网）", "", s)
    s = re.sub(r"Editor's note:.*?(?=\S)", "", s, flags=re.I)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def make_summary(article: Article, max_chars: int = 130) -> str:
    """从正文压缩摘要（无 LLM）。英文源给出中文提示性摘要，避免页面直接出英文。"""
    body = _clean_zh_noise(article.body or "")
    title = article.title_cn or article.title or ""
    if not body:
        return title[:max_chars]

    if article.body_lang == "en":
        # 无翻译模型时：不把英文正文塞进摘要，避免首页出现大段英文
        tip = f"「{title}」相关报道，详见原文。原文为英文，需机翻后发布。"
        return tip[:max_chars]

    # 取前 2-3 句
    parts = re.split(r"(?<=[。！？.!?])\s+", body)
    chunks: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) < 8:
            continue
        # 跳过仍含大量噪声的段
        if p.startswith("http") or "图像来源" in p:
            continue
        chunks.append(p)
        if len("".join(chunks)) >= max_chars or len(chunks) >= 3:
            break
    summary = "".join(chunks)
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"
    # 从第一个汉字起算
    m = re.search(r"[\u4e00-\u9fff].*", summary)
    if m:
        summary = m.group(0)[:max_chars]
    return summary or title[:max_chars]


def extract_quote(article: Article, max_chars: int = 60) -> str:
    """粗提取一句短引语；英文源暂不提取，避免页面出现英文金句。"""
    if article.body_lang == "en":
        return ""
    body = _clean_zh_noise(article.body or "")
    # 中文引号
    m = re.search(r"[「“\"]([^」”\"]{8,60})[」”\"]", body)
    if m:
        q = m.group(1).strip()
        if re.search(r"[\u4e00-\u9fff]", q):
            return q[:max_chars]
    # 取较短有力中文句
    for p in re.split(r"[。！？]", body):
        p = p.strip()
        if 12 <= len(p) <= max_chars and re.search(r"[\u4e00-\u9fff]", p):
            return p
    return ""


def looks_like_satire(article: Article) -> tuple[bool, str]:
    """启发式嘲讽门控。返回 (通过, 原因)。"""
    title = article.title or ""
    body = (article.body or "")[:1500]
    text = title + " " + body

    if is_fake_url(article.url):
        return False, "fake_url"

    if len(body) < 50:
        return False, "body_too_short"

    if article.side == "left":
        for pat in LEFT_PRAISE_PATTERNS:
            if re.search(pat, title, re.I) or re.search(pat, body[:400], re.I):
                return False, f"left_praise:{pat}"
        china_hit = bool(re.search(
            r"中国|中共|北京|习近平|台湾|香港|China|Chinese|Beijing|Xi Jinping|Hong Kong|Taiwan|Xinjiang",
            text,
            re.I,
        ))
        if not china_hit:
            return False, "left_not_about_china"
        for pat in LEFT_OFFTOPIC:
            if re.search(pat, title, re.I) and not re.search(
                r"批评|丑闻|打压|审查|corrupt|crackdown|censor|detention", text, re.I
            ):
                return False, f"left_offtopic:{pat}"
        neg = bool(re.search(
            r"批评|质疑|丑闻|腐败|打压|审查|维稳|崩溃|危机|镇压|威胁|警告|争议|洗钱|强迫|"
            r"critic|corrupt|crackdown|censor|scandal|crisis|threat|allege|probe|"
            r"detention|authoritarian|expels|arrest|interference|reject",
            text,
            re.I,
        ))
        praise = bool(re.search(
            r"领先全球|世界第一|伟大成就|榜样|miracle|leads the world|success story|"
            r"more favorably|by surprise|tames desert",
            text,
            re.I,
        ))
        if praise and not neg:
            return False, "left_praise_tone"
        # 英文左栏（AP）要求有更明确负面线索，避免中性/夸赞稿
        if article.body_lang == "en" and not neg:
            return False, "left_en_needs_neg"
        if not neg:
            return True, "left_neutral_ok"
        return True, "left_neg"

    # right
    for pat in RIGHT_SELF_PRAISE_PATTERNS:
        if re.search(pat, title, re.I) or re.search(pat, body[:300], re.I):
            return False, f"right_self_praise:{pat}"
    # 右栏若主要吹中国成就、锋芒不在海外 → 剔除
    china_boast = bool(re.search(
        r"中国成就|中国贡献|中国经验|中国速度|中国智慧|现代化|世界看好中国|"
        r"China.?s (rise|success|model|modernization)|views China",
        text,
        re.I,
    ))
    foreign_hit = bool(re.search(
        r"美国|西方|欧洲|欧盟|日本|印度|北约|特朗普|拜登|马斯克|华尔街|好莱坞|漫威|迪士尼|"
        r"奥斯卡|伊朗|以色列|Netflix|汤姆.?克鲁斯|阿汤哥|"
        r"US|USA|America|Europe|EU|Trump|Biden|Japan|India|NATO|West|Iran|Israel|Britain|UK|"
        r"Hollywood|Marvel|Disney|Oscar|Netflix|Cruise",
        text,
        re.I,
    ))
    if china_boast and not foreign_hit:
        return False, "right_china_boast"
    if not foreign_hit:
        return False, "right_not_about_foreign"
    neg = bool(re.search(
        r"批评|质疑|丑闻|虚伪|双标|失控|衰落|溃败|闹剧|翻车|失败|危机|傲慢|混乱|"
        r"critic|hypocr|scandal|fail|crisis|chaos|decline|farce|war|cost",
        text,
        re.I,
    ))
    if not neg:
        return True, "right_neutral_ok"
    return True, "right_neg"


def guess_absurdity(article: Article, reason: str) -> int:
    if "neg" in reason:
        return 6
    if "neutral" in reason:
        return 4
    return 5


def enrich_without_llm(article: Article) -> Article | None:
    """无 LLM 填充字段；不过门控则返回 None。"""
    ok, reason = looks_like_satire(article)
    if not ok:
        article.classify_pass = False
        article.reject_reason = reason
        return None

    article.classify_pass = True
    article.validate_pass = True  # 无 LLM 时视为已本地校验
    article.title_cn = article.title if article.body_lang == "zh" else _rough_title_cn(article.title)
    article.summary_cn = make_summary(article)
    article.topic = guess_topic(article.title + " " + article.summary_cn + " " + (article.body or "")[:300])
    article.quote_cn = extract_quote(article)
    article.absurdity = guess_absurdity(article, reason)
    return article


def _rough_title_cn(title: str) -> str:
    """有中文则直接用；纯英文标题加前缀，提醒后续 localize/LLM 翻译。"""
    t = (title or "").strip()
    if re.search(r"[\u4e00-\u9fff]", t):
        return t
    return t  # 英文标题由 tools/localize_articles.py 或 LLM process 译成中文
