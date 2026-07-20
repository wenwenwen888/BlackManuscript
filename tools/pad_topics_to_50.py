"""把各主题补齐到至少 50 条，并生成最多 5 组今日对擂。

- 保留已有真实抓取条目；按规范化标题去重
- 不足部分用中文嘲讽风格稿补齐（左右镜像议题）
- 原文链接：Bing 站内检索（可打开，且更贴近对应议题）
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "site" / "src" / "content" / "daily" / "articles.json"
PUBLIC = ROOT / "site" / "public" / "articles.json"
OUT_DAILY = ROOT / "scraper" / "output" / "daily"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scraper"))
from mirror_seed_pairs import MIRROR_PAIRS  # noqa: E402
from utils.mirror import ensure_mirror_issue, issue_label, mirror_pair_score  # noqa: E402

TOPICS = ["股票", "政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "电影", "娱乐", "其他"]
MIN_PER_TOPIC = 50
H2H_COUNT = 5
TODAY = date.today().isoformat()

# (媒体名, 国家, 站内检索 host, 可打开栏目页兜底)
# 避开常 401/付费墙：Bloomberg / WSJ / FT / Economist / Reuters
LEFT_POOL = [
    ("BBC 中文", "uk", "bbc.com", "https://www.bbc.com/zhongwen/simp"),
    ("德国之声", "de", "dw.com", "https://www.dw.com/zh/"),
    ("Associated Press", "us", "apnews.com", "https://apnews.com/hub/china"),
    ("The New York Times", "us", "nytimes.com", "https://www.nytimes.com/topic/destination/china"),
    ("The Guardian", "uk", "theguardian.com", "https://www.theguardian.com/world/china"),
    ("CNBC", "us", "cnbc.com", "https://www.cnbc.com/world/?region=world"),
]
RIGHT_POOL = [
    ("观察者网", "cn", "guancha.cn", "https://www.guancha.cn/internation"),
    ("环球时报", "cn", "huanqiu.com", "https://world.huanqiu.com/"),
    ("CGTN", "cn", "cgtn.com", "https://www.cgtn.com/opinions"),
    ("环球网评论", "cn", "huanqiu.com", "https://opinion.huanqiu.com/"),
    ("观察者网文化", "cn", "guancha.cn", "https://www.guancha.cn/culture"),
]
STOCK_LEFT_POOL = [
    ("BBC 中文", "uk", "bbc.com", "https://www.bbc.com/zhongwen/simp/business"),
    ("The Guardian", "uk", "theguardian.com", "https://www.theguardian.com/business"),
    ("CNBC", "us", "cnbc.com", "https://www.cnbc.com/world/?region=world"),
    ("Associated Press", "us", "apnews.com", "https://apnews.com/hub/china"),
    ("德国之声", "de", "dw.com", "https://www.dw.com/zh/"),
]
STOCK_RIGHT_POOL = [
    ("证券时报", "cn", "stcn.com", "https://www.stcn.com/"),
    ("东方财富", "cn", "eastmoney.com", "https://finance.eastmoney.com/a/cgspl.html"),
    ("新浪财经", "cn", "sina.com.cn", "https://finance.sina.com.cn/stock/"),
    ("观察者网", "cn", "guancha.cn", "https://www.guancha.cn/economy"),
    ("环球网财经", "cn", "huanqiu.com", "https://finance.huanqiu.com/"),
]

VARIANTS = [
    ("续闻｜", "进一步指出"),
    ("观察｜", "分析认为"),
    ("锐评｜", "评论写道"),
    ("深读｜", "报道详述"),
    ("焦点｜", "文章强调"),
    ("速览｜", "消息称"),
    ("对照｜", "对照可见"),
    ("余波｜", "余波之中"),
    ("追问｜", "有人追问"),
    ("现场｜", "现场传来"),
    ("复盘｜", "复盘可见"),
    ("旁证｜", "另有旁证"),
]
TITLE_ANGLES = [
    "资金面", "制度账", "舆论场", "国际对照", "读者视角",
    "政策账本", "市场情绪", "执行细节", "激励结构", "时间成本",
    "叙事话术", "问责链条", "数据口径", "供应链", "民生体感",
]
SUMMARY_TAILS = [
    "文章还补充了更多细节：公开表态与私下算账往往两套话术，真正的成本很少写进标题。",
    "评论认为，热闹的叙事掩盖了制度缺口，旁观者看得越清楚，当事人越急着换话题。",
    "报道末尾写道，口号可以日更，代价却按年结算；等账单摊开时，掌声早已散场。",
    "有分析指出，同类事件反复出现，说明问题不在个案运气，而在激励机制本身。",
    "读者更关心的是后续：问责名单会不会公布，补丁会不会变成下一次危机的说明书。",
    "对照其他国家同类议题，文章讽刺道：方法不同，避责的熟练度却惊人地相似。",
]

PREFIX_RE = re.compile(
    r"^(续闻｜|观察｜|锐评｜|深读｜|焦点｜|速览｜|对照｜|余波｜|追问｜|现场｜|复盘｜|旁证｜|"
    r"续：|观察：|锐评：|深读：|焦点：|速览：|对照：|余波：|追问：|现场：)"
)
ANGLE_RE = re.compile(r"｜[^｜]{2,8}$")
INDEX_RE = re.compile(r"（\d+）\s*$")


def title_key(title: str) -> str:
    """去重键：去掉版式前缀/数字后缀，保留角度后缀以区分不同切入点。"""
    t = (title or "").strip()
    t = PREFIX_RE.sub("", t)
    t = INDEX_RE.sub("", t)
    return re.sub(r"\s+", "", t)


def search_keywords(title: str, topic: str) -> str:
    core = title_key(title)
    core = re.sub(r"[“”‘’\"'：:，。！？、（）\(\)\[\]\|｜—\-]", " ", core)
    parts = [p for p in core.split() if len(p) >= 2]
    kw = " ".join(parts[:6]) if parts else topic
    return f"{topic} {kw}".strip()


def make_url(host: str, title: str, topic: str) -> str:
    """Bing 站内检索：可打开，并尽量落到对应议题相关结果。"""
    q = quote(f"site:{host} {search_keywords(title, topic)}")
    return f"https://www.bing.com/search?q={q}"


def strip_title_index(title: str) -> str:
    return INDEX_RE.sub("", (title or "").strip())


def sentence_count(text: str) -> int:
    return max(1, len([
        p for p in (text or "").replace("！", "。").replace("？", "。").split("。") if p.strip()
    ]))


def lengthen_summary(summary: str, variant_i: int = 0) -> str:
    s = (summary or "").strip()
    if not s:
        s = "报道称相关争议仍在发酵，细节与责任归属尚不清晰。"
    if not s.endswith(("。", "！", "？", "…")):
        s += "。"
    i = variant_i
    target = 5 if (variant_i % 2 == 0) else 6
    while sentence_count(s) < target or len(s) < 180:
        s += SUMMARY_TAILS[i % len(SUMMARY_TAILS)]
        i += 1
        if sentence_count(s) >= 6 and len(s) >= 180:
            break
    if len(s) > 360:
        cut = s[:360]
        if "。" in cut:
            cut = cut[: cut.rfind("。") + 1]
        s = cut
    return s


def expand_seed(seed: tuple[str, str, str, int], variant_i: int) -> tuple[str, str, str, int]:
    title, summary, quote, absurdity = seed
    if variant_i == 0:
        new_title = title
        new_summary = summary
    else:
        prefix, verb = VARIANTS[(variant_i - 1) % len(VARIANTS)]
        angle = TITLE_ANGLES[(variant_i - 1) % len(TITLE_ANGLES)]
        new_title = f"{prefix}{title}｜{angle}"
        bridge = f"{verb}，从{angle}看同类信号仍在扩散。"
        new_summary = summary.replace("。", f"。{bridge}", 1) if "。" in summary else summary + bridge
    return new_title, lengthen_summary(new_summary, variant_i), quote, min(10, absurdity + (variant_i % 2))


def build_item(
    topic: str,
    side: str,
    idx: int,
    seed: tuple[str, str, str, int],
    day: str,
    *,
    mirror_issue: str,
    variant_i: int,
) -> dict:
    pool = (STOCK_LEFT_POOL if side == "left" else STOCK_RIGHT_POOL) if topic == "股票" else (
        LEFT_POOL if side == "left" else RIGHT_POOL
    )
    source, country, host, _fallback = pool[idx % len(pool)]
    title, summary, quote, absurdity = expand_seed(seed, variant_i)
    return {
        "side": side,
        "source": source,
        "source_country": country,
        "source_url": make_url(host, title, topic),
        "topic": topic,
        "title_cn": title,
        "summary_cn": summary,
        "quote_cn": quote,
        "absurdity": absurdity,
        "published": day,
        "mirror_issue": mirror_issue,
    }


def dedupe_items(items: list[dict]) -> tuple[list[dict], int]:
    """按规范化标题去重，保留荒诞指数更高者。返回 (去重后, 删除数)。"""
    before = len(items)
    ranked = sorted(
        items,
        key=lambda x: (x.get("absurdity") or 0, x.get("published") or ""),
        reverse=True,
    )
    seen: set[str] = set()
    out: list[dict] = []
    for it in ranked:
        key = title_key(it.get("title_cn") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out, before - len(out)


def is_real_article_url(url: str) -> bool:
    u = url or ""
    if "bing.com/search" in u or "satire=" in u or "example.com" in u:
        return False
    return bool(re.search(r"/20\d{2}[_/-]|/article|/articles/|/simp/[a-z0-9]{6,}", u))


def pad_topic(existing: list[dict], topic: str, used_keys: set[str]) -> list[dict]:
    cur = [i for i in existing if i.get("topic") == topic]
    need = MIN_PER_TOPIC - len(cur)
    if need <= 0:
        return []
    pairs = MIRROR_PAIRS[topic]
    out: list[dict] = []
    left_n = need // 2
    right_n = need - left_n
    for side, count in (("left", left_n), ("right", right_n)):
        made = 0
        attempt = 0
        while made < count and attempt < count * 50:
            pair_i = attempt % len(pairs)
            variant_i = attempt // len(pairs)
            issue, left_seed, right_seed = pairs[pair_i]
            seed = left_seed if side == "left" else right_seed
            day = (date.today() - timedelta(days=attempt % 14)).isoformat()
            item = build_item(
                topic, side, made, seed, day,
                mirror_issue=issue, variant_i=variant_i,
            )
            key = title_key(item["title_cn"])
            attempt += 1
            if key in used_keys:
                continue
            used_keys.add(key)
            out.append(item)
            made += 1
    return out


def polish_item(it: dict, idx: int = 0) -> dict:
    out = dict(it)
    out["title_cn"] = strip_title_index(out.get("title_cn") or "")
    summary = out.get("summary_cn") or ""
    url = out.get("source_url") or ""
    if (not is_real_article_url(url)) or sentence_count(summary) < 4 or len(summary) < 140:
        if sentence_count(summary) < 4 or len(summary) < 140:
            out["summary_cn"] = lengthen_summary(summary, idx)
    ensure_mirror_issue(out)
    return out


def pick_h2h(items: list[dict], n: int = H2H_COUNT) -> list[dict]:
    for it in items:
        ensure_mirror_issue(it)

    candidates: list[tuple[float, dict, dict, str]] = []
    lefts = [i for i in items if i.get("side") == "left"]
    rights = [i for i in items if i.get("side") == "right"]
    for l in lefts:
        for r in rights:
            if l.get("topic") != r.get("topic"):
                continue
            if (l.get("absurdity") or 0) < 5 or (r.get("absurdity") or 0) < 5:
                continue
            li = (l.get("mirror_issue") or "").strip()
            ri = (r.get("mirror_issue") or "").strip()
            l_text = f"{l.get('title_cn') or ''} {l.get('summary_cn') or ''}"
            r_text = f"{r.get('title_cn') or ''} {r.get('summary_cn') or ''}"
            score = mirror_pair_score(
                li, ri, l_text, r_text,
                absurdity_sum=float((l.get("absurdity") or 0) + (r.get("absurdity") or 0)),
            )
            if score < 40:
                continue
            issue = li if li and li == ri else (li or ri)
            candidates.append((score, l, r, issue))

    candidates.sort(key=lambda x: x[0], reverse=True)
    used: set[str] = set()
    used_issues: set[str] = set()
    pairs: list[dict] = []
    for topic in TOPICS:
        for score, l, r, issue in candidates:
            if l.get("topic") != topic:
                continue
            if l["source_url"] in used or r["source_url"] in used:
                continue
            if issue and issue in used_issues:
                continue
            used.add(l["source_url"])
            used.add(r["source_url"])
            if issue:
                used_issues.add(issue)
            label = issue_label(issue) if issue else topic
            pairs.append({
                "left": {**l, "side": "left"},
                "right": {**r, "side": "right"},
                "note": f"今日对擂 · {label}：{l['source']} vs {r['source']}",
            })
            break
        if len(pairs) >= n:
            break
    return pairs[:n]


def interleave(items: list[dict]) -> list[dict]:
    left = [i for i in items if i["side"] == "left"]
    right = [i for i in items if i["side"] == "right"]
    left.sort(key=lambda x: x.get("published") or "", reverse=True)
    right.sort(key=lambda x: x.get("published") or "", reverse=True)
    out = []
    for i in range(max(len(left), len(right))):
        if i < len(left):
            out.append(left[i])
        if i < len(right):
            out.append(right[i])
    return out


def main():
    random.seed(42)
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    items = list(data.get("items") or [])

    # 1) 去掉假链；丢掉旧 satire 补齐稿（栏目假链），只留真实抓取
    items = [
        i for i in items
        if "example.com" not in (i.get("source_url") or "")
        and "satire=" not in (i.get("source_url") or "")
        and "bing.com/search" not in (i.get("source_url") or "")
    ]
    items = [polish_item(i, n) for n, i in enumerate(items)]

    # 2) 真实稿去重
    items, dropped_real = dedupe_items(items)

    # 3) 按主题补齐到 ≥50，标题键全局唯一
    used_keys = {title_key(i.get("title_cn") or "") for i in items}
    used_keys.discard("")
    added: list[dict] = []
    for topic in TOPICS:
        pad = pad_topic(items, topic, used_keys)
        added.extend(pad)
        items.extend(pad)

    # 4) 再去重一次（防真实稿与补齐稿撞车）并回补
    items, dropped_all = dedupe_items(items)
    used_keys = {title_key(i.get("title_cn") or "") for i in items}
    used_keys.discard("")
    for topic in TOPICS:
        pad = pad_topic(items, topic, used_keys)
        added.extend(pad)
        items.extend(pad)

    items = [polish_item(i, n) for n, i in enumerate(items)]
    h2h = pick_h2h(items, H2H_COUNT)
    stream = interleave(items)

    out = {
        "date": TODAY,
        "items": stream,
        "head_to_head": h2h,
    }
    text = json.dumps(out, ensure_ascii=False, indent=2)
    for path in (CONTENT, PUBLIC, OUT_DAILY / "articles.json", OUT_DAILY / f"{TODAY}.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    c = Counter(i["topic"] for i in out["items"])
    keys = [title_key(i.get("title_cn") or "") for i in out["items"]]
    dup_n = len(keys) - len(set(keys))
    bing_n = sum(1 for i in out["items"] if "bing.com/search" in (i.get("source_url") or ""))
    real_n = sum(1 for i in out["items"] if is_real_article_url(i.get("source_url") or ""))

    print(f"dropped_dupes={dropped_real}+extra pad/dedupe cycle")
    print(f"added {len(added)} padded articles")
    print(f"stream items={len(out['items'])} h2h={len(h2h)} bing_links={bing_n} real_links={real_n} title_dupes={dup_n}")
    for t in TOPICS:
        print(f"  {t}: {c[t]}")
    sample = next(i for i in out["items"] if "bing.com/search" in i["source_url"])
    print("sample title:", sample["title_cn"])
    print("sample url:", sample["source_url"][:120])


if __name__ == "__main__":
    main()
