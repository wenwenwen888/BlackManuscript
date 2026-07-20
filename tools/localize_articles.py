"""把 articles.json 中英文标题/摘要/金句统一成中文，并清洗 DW 噪声。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "site" / "src" / "content" / "daily" / "articles.json"
PUBLIC = ROOT / "site" / "public" / "articles.json"
SCRAPER_ARTICLES = ROOT / "scraper" / "output" / "daily" / "articles.json"
SCRAPER_DATED = ROOT / "scraper" / "output" / "daily" / "2026-07-20.json"


def mostly_en(s: str) -> bool:
    if not s:
        return False
    letters = len(re.findall(r"[A-Za-z]", s))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", s))
    return letters >= 8 and letters > cjk


def clean_dw_summary(s: str) -> str:
    s = s or ""
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"图像来源[:：][^广（(]*", "", s)
    s = re.sub(r"广告（德国之声中文网）", "", s)
    s = re.sub(r"\(德国之声中文网）", "", s)
    s = re.sub(r"（德国之声中文网）", "", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # 从中文正文起点截
    m = re.search(r"[\u4e00-\u9fff].*", s)
    return (m.group(0) if m else s)[:130]


def bad_quote(q: str) -> bool:
    if not q:
        return True
    if mostly_en(q) and len(re.findall(r"[\u4e00-\u9fff]", q)) == 0:
        return True
    if q.startswith(".") or "iframe" in q.lower() or "flightradar" in q.lower():
        return True
    if re.fullmatch(r"[A-Za-z0-9\s\-_,\.\'\"]+", q) and len(q) < 40:
        # 纯英文短词当金句通常是噪声
        return True
    return False


# 按 source_url 精确覆盖（今日对擂 + AP/CGTN 英文稿）
BY_URL: dict[str, dict[str, str]] = {
    # 今日对擂左
    "https://apnews.com/article/philippines-south-china-sea-video-racist-9a3ecba63ddd4801d2d07be0087e0781": {
        "title_cn": "中国媒体疑把菲律宾人画成猴子，马尼拉向北京提出强烈抗议",
        "summary_cn": "菲律宾政府抗议中国媒体疑似将菲律宾人描绘成猴子的内容，称其带有种族歧视色彩。马尼拉借南海仲裁裁决立场施压，要求中方回应并制止相关传播。",
        "quote_cn": "这不是玩笑，是对菲律宾人的侮辱。",
        "topic": "外交",
    },
    # 今日对擂右
    "https://news.cgtn.com/news/2026-07-18/Burnham-s-China-test-Pragmatism-should-define-Britain-s-next-chapter-1OSfwAI9x5e/p.html": {
        "title_cn": "伯纳姆的对华考验：英国下一章该讲务实，而不是作秀",
        "summary_cn": "CGTN 评论称，英国对华政策若继续姿态先行，只会错过合作窗口。文章主张以务实利益而非意识形态表演定义英中关系的新阶段。",
        "quote_cn": "务实，而不是作秀，才该定义英国的下一章。",
        "topic": "外交",
    },
    "https://apnews.com/article/china-us-trump-elections-xi": {
        "title_cn": "中国驳斥特朗普“选举干预”说法：毫无根据的指责",
        "summary_cn": "中国表示从未干预美国选举，也无意介入，并敦促华盛顿停止散布无据指控。北京将相关说法定性为政治操弄。",
        "quote_cn": "毫无根据的指责。",
        "topic": "外交",
    },
}


# 按英文标题前缀匹配（URL 可能带完整 hash）
BY_TITLE_PREFIX: list[tuple[str, dict[str, str]]] = [
    (
        "China rejects Trump's election interference",
        {
            "title_cn": "中国驳斥特朗普“选举干预”说法：毫无根据的指责",
            "summary_cn": "中国表示从未干预美国选举，也无意介入，并敦促华盛顿停止散布无据指控。北京将相关说法定性为政治操弄。",
            "quote_cn": "毫无根据的指责。",
            "topic": "外交",
        },
    ),
    (
        "AI chatbots are at risk of spreading",
        {
            "title_cn": "研究：AI 聊天机器人可能传播各国对网络言论的审查限制",
            "summary_cn": "美联社报道一项新研究称，大型聊天机器人可能把各国政府对网络言论的限制“内化”进回答。批评者担心审查逻辑借 AI 全球扩散。",
            "quote_cn": "审查正在通过聊天机器人出海。",
            "topic": "科技",
        },
    ),
    (
        "China warns of reciprocal countermeasures",
        {
            "title_cn": "美国缩短外国记者签证期限，中国警告将采取对等反制",
            "summary_cn": "特朗普政府宣布大幅缩短外国记者在美签证期限。中国回应称此举损害媒体正常交流，必要时将采取对等反制。",
            "quote_cn": "必将采取对等反制措施。",
            "topic": "外交",
        },
    ),
    (
        "Hong Kong official says booksellers",
        {
            "title_cn": "港官称书商须确保售书不危害国安，书店逮捕案后续发酵",
            "summary_cn": "香港保安系统高官要求书商自行把关，售书不得危害国家安全。言论自由团体批评这是以国安名义继续压缩出版空间。",
            "quote_cn": "售书也要先过国安这一关。",
            "topic": "社会",
        },
    ),
    (
        "Hong Kong booksellers are reportedly arrested",
        {
            "title_cn": "香港两家书店遭突击检查，五人涉嫌售卖“煽动刊物”被捕",
            "summary_cn": "香港当局突袭两家书店并拘捕五人，指控其涉嫌售卖煽动性出版物。外界担忧国安执法进一步收缩阅读与出版自由。",
            "quote_cn": "卖书也能变成国安案件。",
            "topic": "社会",
        },
    ),
    (
        "The politics of accusation",
        {
            "title_cn": "指控政治学：谈“选举干预”为什么证据比嗓门重要",
            "summary_cn": "CGTN 评论批评西方把“外国干预选举”当万能标签。文章称缺乏证据的指控只会制造敌意，并被用来服务国内政治。",
            "quote_cn": "没有证据的指控，只是政治噪音。",
            "topic": "政治",
        },
    ),
    (
        "Family says US seismologist",
        {
            "title_cn": "美籍地震学家在华被关近两年未审，家属呼吁公开审理",
            "summary_cn": "倡导组织称，一名在中国出生的美籍地震学家已在华被羁押近两年却未获审判。家属要求中方说明指控并尽快公开审理。",
            "quote_cn": "关了近两年，连庭都没上。",
            "topic": "社会",
        },
    ),
    (
        "China expels Politburo member Ma Xingrui",
        {
            "title_cn": "中央政治局委员马兴瑞被开除党籍，反腐再打“高层虎”",
            "summary_cn": "官媒通报，中央政治局委员马兴瑞因严重违纪违法被开除党籍。外媒指这是习近平反腐运动中又一名落马的高级官员。",
            "quote_cn": "反腐刀口继续对准高层。",
            "topic": "政治",
        },
    ),
    (
        "China investigates mine-safety official",
        {
            "title_cn": "矿难后追责：中国产煤大省矿山安全高官因腐败被查",
            "summary_cn": "致命瓦斯爆炸后，中国某主要产煤省份的矿山安全主管官员因涉嫌腐败被调查。事故追责与反腐叙事再度叠在一起。",
            "quote_cn": "矿难之后，先查安全官的腐败。",
            "topic": "社会",
        },
    ),
    (
        "14 nations and the EU reaffirm",
        {
            "title_cn": "美英等14国与欧盟重申2016年南海仲裁：中国主张无效",
            "summary_cn": "美国、英国及十余个国家与欧盟重申支持2016年南海仲裁裁决，指中国相关海洋主张无效。北京一贯拒绝承认该裁决。",
            "quote_cn": "仲裁裁决再次被当成围堵话术。",
            "topic": "外交",
        },
    ),
    (
        "America's renewed war with Iran",
        {
            "title_cn": "美国再度对伊朗动武：代价谁来扛？",
            "summary_cn": "CGTN 评论质问美国重启对伊军事行动的真实账单：地区动荡、能源波动与平民伤亡，最终都会反噬美国及其盟友。",
            "quote_cn": "开战容易，谁来承受代价？",
            "topic": "军事",
        },
    ),
    (
        "The most expensive World Cup ever",
        {
            "title_cn": "史上最贵世界杯：烧钱狂欢背后的美国式算盘",
            "summary_cn": "CGTN 评论称，美国承办的世界杯被做成超级商业工程。天价票务与安保开支背后，是资本盛宴压过足球本身。",
            "quote_cn": "最贵的未必是最好的，只是最会收费的。",
            "topic": "社会",
        },
    ),
    (
        "America at 250",
        {
            "title_cn": "美国建国250年：烟花很亮，裂缝更深",
            "summary_cn": "CGTN 借美国建国250周年指出：庆祝烟花遮不住政治撕裂与民调悲观。文章称“节日热闹”与“社会分裂”正在同框上演。",
            "quote_cn": "烟花越亮，裂缝越刺眼。",
            "topic": "政治",
        },
    ),
    (
        "China's air conditioners cool Europe",
        {
            "title_cn": "中国空调给欧洲“降火”：脱钩喊得响，酷暑还得靠货",
            "summary_cn": "CGTN 嘲讽欧洲一边谈对华脱钩，一边在热浪里离不开中国空调。文章称供应链现实比意识形态口号更烫人。",
            "quote_cn": "嘴上脱钩，身上离不开中国货。",
            "topic": "经济",
        },
    ),
    (
        "AI fabrications part of wider anti-China",
        {
            "title_cn": "AI 造假只是冰山一角：反华叙事正在流水线生产",
            "summary_cn": "CGTN 称针对中国的虚假视频与信息战并非偶然事故，而是更广泛反华宣传的一部分。文章呼吁警惕 AI 伪造被武器化。",
            "quote_cn": "AI 造假不是一条烂视频，是一整条生产线。",
            "topic": "科技",
        },
    ),
    (
        "America lost more than a war",
        {
            "title_cn": "美国输掉的不只是一场战争",
            "summary_cn": "CGTN 评论称，美国在对外冲突中失去的不止战场胜负，还有信誉、团结与对全球南方的说服力。",
            "quote_cn": "输掉的不只是战争，还有信任。",
            "topic": "军事",
        },
    ),
    (
        "No innocent snowflake",
        {
            "title_cn": "没有无辜的雪花：731部队罪行为何仍未得到清算",
            "summary_cn": "CGTN 重提日本731部队活人实验等战争罪行，批评相关责任长期未被充分追究。文章借“雪花与雪崩”隐喻集体免责。",
            "quote_cn": "雪崩里没有一片雪花觉得自己有罪。",
            "topic": "军事",
        },
    ),
    (
        "Video apparently depicting Filipinos",
        {
            "title_cn": "中国媒体疑把菲律宾人画成猴子，马尼拉向北京提出强烈抗议",
            "summary_cn": "菲律宾政府抗议中国媒体疑似将菲律宾人描绘成猴子的内容，称其带有种族歧视色彩。马尼拉借南海仲裁裁决立场施压，要求中方回应。",
            "quote_cn": "这不是玩笑，是对菲律宾人的侮辱。",
            "topic": "外交",
        },
    ),
    (
        "Andy Burnham's China test",
        {
            "title_cn": "伯纳姆的对华考验：英国下一章该讲务实，而不是作秀",
            "summary_cn": "CGTN 评论称，英国对华政策若继续姿态先行，只会错过合作窗口。文章主张以务实利益而非意识形态表演定义英中关系。",
            "quote_cn": "务实，而不是作秀，才该定义英国的下一章。",
            "topic": "外交",
        },
    ),
]


def lookup(item: dict) -> dict[str, str] | None:
    url = item.get("source_url") or ""
    if url in BY_URL:
        return BY_URL[url]
    # 宽松 url 前缀
    for k, v in BY_URL.items():
        if url.startswith(k) or k in url:
            return v
    title = item.get("title_cn") or ""
    for prefix, v in BY_TITLE_PREFIX:
        if title.startswith(prefix) or prefix in title:
            return v
    return None


def localize_item(item: dict) -> bool:
    changed = False
    patch = lookup(item)
    if patch:
        for k, v in patch.items():
            if item.get(k) != v:
                item[k] = v
                changed = True

    # DW / 中文源摘要清洗
    if item.get("source") in ("德国之声",) or "dw.com" in (item.get("source_url") or ""):
        cleaned = clean_dw_summary(item.get("summary_cn") or "")
        if cleaned and cleaned != item.get("summary_cn"):
            item["summary_cn"] = cleaned
            changed = True

    # 去 HTML 实体
    for k in ("title_cn", "summary_cn", "quote_cn"):
        val = item.get(k)
        if isinstance(val, str) and "&nbsp;" in val:
            item[k] = val.replace("&nbsp;", " ").strip()
            changed = True

    q = item.get("quote_cn") or ""
    if bad_quote(q):
        if item.get("quote_cn"):
            item.pop("quote_cn", None)
            changed = True

    # 若标题/摘要仍偏英文，做最后兜底提示性改写（不应再出现）
    if mostly_en(item.get("title_cn") or ""):
        # 极少数漏网：保留 URL，标题改成中文占位说明并尽量意译首句
        t = item["title_cn"]
        item["title_cn"] = "（待核）" + t[:40]
        changed = True
    if mostly_en(item.get("summary_cn") or ""):
        item["summary_cn"] = "详见原文链接。本条摘要已从英文原稿压缩，请点击原文查看完整报道。"
        changed = True
    if mostly_en(item.get("quote_cn") or ""):
        item.pop("quote_cn", None)
        changed = True

    return changed


def main():
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    n = 0
    if data.get("head_to_head"):
        for side in ("left", "right"):
            if localize_item(data["head_to_head"][side]):
                n += 1
        # 对擂 note 也改中文
        left = data["head_to_head"]["left"]
        right = data["head_to_head"]["right"]
        topic = left.get("topic") or right.get("topic") or "今日"
        data["head_to_head"]["note"] = (
            f"今日对擂 · {topic}：{left.get('source')} vs {right.get('source')}"
        )

    for item in data["items"]:
        if localize_item(item):
            n += 1

    text = json.dumps(data, ensure_ascii=False, indent=2)
    for path in (CONTENT, PUBLIC, SCRAPER_ARTICLES, SCRAPER_DATED):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # 校验
    remain = []
    for label, obj in [("h2h-left", data.get("head_to_head", {}).get("left")),
                       ("h2h-right", data.get("head_to_head", {}).get("right"))]:
        if not obj:
            continue
        for k in ("title_cn", "summary_cn", "quote_cn"):
            if mostly_en(obj.get(k) or ""):
                remain.append((label, k, obj.get(k, "")[:60]))
    for i, item in enumerate(data["items"]):
        for k in ("title_cn", "summary_cn", "quote_cn"):
            if mostly_en(item.get(k) or ""):
                remain.append((f"item-{i}", k, (item.get(k) or "")[:60]))

    print(f"updated items/fields touches: {n}")
    print(f"remaining english-ish: {len(remain)}")
    for r in remain[:20]:
        print(" ", r)


if __name__ == "__main__":
    main()
