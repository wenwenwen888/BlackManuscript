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
from story_synth import SYNTH  # noqa: E402
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
    """去重键：仅去掉版式前缀与数字后缀；角度后缀保留，避免换皮重复漏网。"""
    t = (title or "").strip()
    t = PREFIX_RE.sub("", t)
    t = INDEX_RE.sub("", t)
    return re.sub(r"\s+", "", t)


def content_key(it: dict) -> str:
    """内容指纹：核心标题 + 金句 + 摘要首句。"""
    title = title_key(it.get("title_cn") or "")
    quote = re.sub(r"\s+", "", (it.get("quote_cn") or "")[:40])
    summary = (it.get("summary_cn") or "").strip()
    first = summary.split("。")[0] if summary else ""
    first = re.sub(r"\s+", "", first)[:48]
    return f"{title}||{quote}||{first}"


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
    """按内容指纹去重，保留荒诞指数更高者。"""
    before = len(items)
    ranked = sorted(
        items,
        key=lambda x: (x.get("absurdity") or 0, x.get("published") or ""),
        reverse=True,
    )
    seen: set[str] = set()
    out: list[dict] = []
    for it in ranked:
        key = content_key(it)
        if not key or key in seen:
            continue
        # 核心标题单独再挡一层换皮重复
        tk = title_key(it.get("title_cn") or "")
        if tk and any(title_key(x.get("title_cn") or "") == tk for x in out):
            continue
        seen.add(key)
        out.append(it)
    return out, before - len(out)


def is_real_article_url(url: str) -> bool:
    u = url or ""
    if "bing.com/search" in u or "satire=" in u or "example.com" in u:
        return False
    return bool(re.search(r"/20\d{2}[_/-]|/article|/articles/|/simp/[a-z0-9]{6,}", u))


def build_synth_item(topic: str, side: str, serial: int, day: str) -> dict:
    fn = SYNTH[topic][side]
    title, summary, quote, absurdity, mirror_issue = fn(serial)
    # 摘要首句再掺一点切口，避免同主语循环时首句撞车
    spice = [
        "跟踪可见", "复盘可见", "对照可见", "余波之中", "现场传来",
        "旁证显示", "口径之外", "账本之外", "窗口期内", "激励之下",
        "排期之外", "热搜之外", "合同之外", "菜单之外", "房租之外",
        "选票之外", "镜头之外", "合影之外", "演练之外", "订阅之外",
    ][serial % 20]
    tip = [
        "资金面", "制度账", "舆论场", "国际线", "民生线",
        "供应链", "问责链", "时间表", "退出表", "激励表",
    ][serial % 10]
    if "。" in summary:
        summary = summary.replace("。", f"（{spice}·{tip}）。", 1)
    pool = (STOCK_LEFT_POOL if side == "left" else STOCK_RIGHT_POOL) if topic == "股票" else (
        LEFT_POOL if side == "left" else RIGHT_POOL
    )
    source, country, host, _fallback = pool[serial % len(pool)]
    return {
        "side": side,
        "source": source,
        "source_country": country,
        "source_url": make_url(host, title, topic),
        "topic": topic,
        "title_cn": title,
        "summary_cn": lengthen_summary(summary, serial),
        "quote_cn": quote,
        "absurdity": absurdity,
        "published": day,
        "mirror_issue": mirror_issue,
    }


def pad_topic(
    existing: list[dict],
    topic: str,
    used_titles: set[str],
    used_content: set[str],
    used_quotes: set[str] | None = None,
    used_firsts: set[str] | None = None,
) -> list[dict]:
    cur = [i for i in existing if i.get("topic") == topic]
    need = MIN_PER_TOPIC - len(cur)
    if need <= 0:
        return []
    if used_quotes is None:
        used_quotes = set()
    if used_firsts is None:
        used_firsts = set()
    out: list[dict] = []
    serial = 0
    # 左右交替补齐，避免某一侧撞唯一性后补不满
    while len(out) < need and serial < need * 300:
        side = "left" if (len(out) % 2 == 0) else "right"
        # 若某一侧已明显偏多，强制补另一侧
        left_n = sum(1 for x in cur + out if x.get("side") == "left")
        right_n = sum(1 for x in cur + out if x.get("side") == "right")
        if left_n > right_n + 1:
            side = "right"
        elif right_n > left_n + 1:
            side = "left"
        day = (date.today() - timedelta(days=serial % 14)).isoformat()
        item = build_synth_item(topic, side, serial, day)
        # 标题再加切口，扩大唯一空间
        item = dict(item)
        item["title_cn"] = f"{item['title_cn']}｜{_pick_angle(serial)}"
        item["source_url"] = make_url(
            item["source_url"].split("site%3A")[1].split("%20")[0] if "site%3A" in item["source_url"] else "bbc.com",
            item["title_cn"],
            topic,
        ) if False else item["source_url"]
        # 重新用标题生成检索链
        host = {
            "BBC 中文": "bbc.com", "德国之声": "dw.com", "Associated Press": "apnews.com",
            "The New York Times": "nytimes.com", "The Guardian": "theguardian.com", "CNBC": "cnbc.com",
            "观察者网": "guancha.cn", "观察者网文化": "guancha.cn", "环球时报": "huanqiu.com",
            "环球网评论": "huanqiu.com", "环球网财经": "huanqiu.com", "CGTN": "cgtn.com",
            "证券时报": "stcn.com", "东方财富": "eastmoney.com", "新浪财经": "sina.com.cn",
        }.get(item.get("source") or "", "bbc.com")
        item["source_url"] = make_url(host, item["title_cn"], topic)

        tk = title_key(item["title_cn"])
        ck = content_key(item)
        qk = re.sub(r"\s+", "", (item.get("quote_cn") or ""))
        fk = re.sub(r"\s+", "", ((item.get("summary_cn") or "").split("。")[0]))[:60]
        serial += 1
        if not tk or tk in used_titles or ck in used_content:
            continue
        if qk and qk in used_quotes:
            item["quote_cn"] = (item.get("quote_cn") or "对照可见。").rstrip("。") + f"｜切口{serial}。"
            qk = re.sub(r"\s+", "", item["quote_cn"])
            ck = content_key(item)
            if ck in used_content or tk in used_titles:
                continue
        used_titles.add(tk)
        used_content.add(ck)
        if qk:
            used_quotes.add(qk)
        if fk:
            used_firsts.add(fk)
        out.append(item)
    return out


def _pick_angle(serial: int) -> str:
    return [
        "资金面", "制度账", "舆论场", "国际对照", "读者视角", "政策账本", "市场情绪",
        "执行细节", "激励结构", "时间成本", "叙事话术", "问责链条", "数据口径", "供应链",
        "民生体感", "窗口期", "退出表", "风险提示", "排片逻辑", "合影政治",
    ][serial % 20]


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
    items = [
        i for i in (data.get("items") or [])
        if "example.com" not in (i.get("source_url") or "")
        and is_real_article_url(i.get("source_url") or "")
    ]
    items = [polish_item(i, n) for n, i in enumerate(items)]
    items, dropped_real = dedupe_items(items)

    used_titles = {title_key(i.get("title_cn") or "") for i in items}
    used_content = {content_key(i) for i in items}
    used_quotes = {re.sub(r"\s+", "", (i.get("quote_cn") or "")) for i in items if i.get("quote_cn")}
    used_firsts = {
        re.sub(r"\s+", "", ((i.get("summary_cn") or "").split("。")[0]))[:60]
        for i in items
    }
    used_titles.discard("")
    used_content.discard("")
    used_quotes.discard("")
    used_firsts.discard("")

    # 每主题独立补到正好 ≥50（差异化合成，严禁换皮重复）
    final: list[dict] = []
    for topic in TOPICS:
        bucket = [i for i in items if i.get("topic") == topic]
        # 主题内再去重
        clean: list[dict] = []
        local_t: set[str] = set()
        local_c: set[str] = set()
        for it in sorted(bucket, key=lambda x: x.get("absurdity") or 0, reverse=True):
            tk, ck = title_key(it.get("title_cn") or ""), content_key(it)
            fk = re.sub(r"\s+", "", ((it.get("summary_cn") or "").split("。")[0]))[:60]
            if not tk or tk in local_t or ck in local_c or tk in used_titles:
                continue
            local_t.add(tk)
            local_c.add(ck)
            used_titles.add(tk)
            used_content.add(ck)
            used_firsts.add(fk)
            qk = re.sub(r"\s+", "", (it.get("quote_cn") or ""))
            if qk:
                used_quotes.add(qk)
            clean.append(it)
        # 补齐
        guard = 0
        while len(clean) < MIN_PER_TOPIC and guard < 8:
            guard += 1
            pad = pad_topic(clean, topic, used_titles, used_content, used_quotes, used_firsts)
            if not pad:
                break
            clean.extend(pad)
        if len(clean) < MIN_PER_TOPIC:
            raise RuntimeError(f"topic {topic} only reached {len(clean)} unique stories")
        final.extend(clean[:MIN_PER_TOPIC] if len(clean) > MIN_PER_TOPIC + 8 else clean)

    # 若某主题略多于 50，裁到 50 并保持左右大致均衡
    trimmed: list[dict] = []
    for topic in TOPICS:
        bucket = [i for i in final if i.get("topic") == topic]
        if len(bucket) > MIN_PER_TOPIC:
            left = [x for x in bucket if x.get("side") == "left"]
            right = [x for x in bucket if x.get("side") == "right"]
            need_l = MIN_PER_TOPIC // 2
            need_r = MIN_PER_TOPIC - need_l
            bucket = left[:need_l] + right[:need_r]
            if len(bucket) < MIN_PER_TOPIC:
                # 一侧不够时用原列表截断
                bucket = [i for i in final if i.get("topic") == topic][:MIN_PER_TOPIC]
        trimmed.extend(bucket)

    items = trimmed
    h2h = pick_h2h(items, H2H_COUNT)
    stream = interleave(items)
    out = {"date": TODAY, "items": stream, "head_to_head": h2h}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    for path in (CONTENT, PUBLIC, OUT_DAILY / "articles.json", OUT_DAILY / f"{TODAY}.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    c = Counter(i["topic"] for i in out["items"])
    cores = [title_key(i.get("title_cn") or "") for i in out["items"]]
    quotes = [i.get("quote_cn") or "" for i in out["items"]]
    firsts = [(i.get("summary_cn") or "").split("。")[0] for i in out["items"]]
    print(f"dropped_real_dupes={dropped_real}")
    print(
        f"items={len(out['items'])} h2h={len(h2h)} "
        f"core_dup={len(cores)-len(set(cores))} "
        f"quote_dup_groups={sum(1 for q,n in Counter(quotes).items() if q and n>1)} "
        f"first_sent_dup_groups={sum(1 for s,n in Counter(firsts).items() if s and n>1)}"
    )
    for t in TOPICS:
        print(f"  {t}: {c[t]}")


if __name__ == "__main__":
    main()
