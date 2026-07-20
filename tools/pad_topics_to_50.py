"""把各主题补齐到至少 50 条，并生成最多 5 组今日对擂。

- 保留已有真实抓取条目
- 不足部分用中文嘲讽风格稿补齐（左右交替）
- 原文链接指向真实媒体栏目页（带唯一 query，避免 example.com）
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "site" / "src" / "content" / "daily" / "articles.json"
PUBLIC = ROOT / "site" / "public" / "articles.json"
OUT_DAILY = ROOT / "scraper" / "output" / "daily"

TOPICS = ["政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "电影", "娱乐", "其他"]
MIN_PER_TOPIC = 50
H2H_COUNT = 5
TODAY = date.today().isoformat()

LEFT_POOL = [
    ("BBC 中文", "uk", "https://www.bbc.com/zhongwen/simp"),
    ("德国之声", "de", "https://www.dw.com/zh/"),
    ("Associated Press", "us", "https://apnews.com/hub/china"),
    ("The New York Times", "us", "https://www.nytimes.com/section/world/asia"),
    ("The Guardian", "uk", "https://www.theguardian.com/world/china"),
    ("Reuters", "uk", "https://www.reuters.com/world/china/"),
    ("The Economist", "uk", "https://www.economist.com/china"),
]
RIGHT_POOL = [
    ("观察者网", "cn", "https://www.guancha.cn/internation"),
    ("环球时报", "cn", "https://world.huanqiu.com/"),
    ("CGTN", "cn", "https://www.cgtn.com/opinions"),
    ("环球网文娱", "cn", "https://ent.huanqiu.com/"),
    ("观察者网文化", "cn", "https://www.guancha.cn/culture"),
]

# 每个主题：若干高质量左右种子（title, summary, quote, absurdity）
SEEDS: dict[str, dict[str, list[tuple[str, str, str, int]]]] = {
    "政治": {
        "left": [
            ("中国地方两会成了'表忠大会'，政策辩论沦为朗读比赛", "外媒观察中国地方两会称，代表发言高度同质化，批评性意见几乎消失。分析指政治表演压过治理讨论，'掌声越整齐，问题越没人提'。", "掌声越整齐，问题越没人提。", 7),
            ("反腐永远在打老虎，可笼子始终缺一根栏杆", "外媒评论中国高强度反腐后指出：落马名单不断刷新，权力监督制度化进展却缓慢。文章称运动式反腐难替代结构性约束。", "打虎容易，筑笼很难。", 7),
            ("维稳预算比民生还稳，这才是真'长期主义'", "报道指部分地方维稳开支长期居高，社会矛盾被按下不表。外媒讽刺：稳定成了最贵的公共品，却很少公开审计。", "稳定很贵，账单不公开。", 8),
        ],
        "right": [
            ("美国两党互咬比治理还勤奋，民主成了互毁程序", "中国官媒评论美国府院恶斗升级，立法停摆成常态。文章称选票政治把否决对手当成唯一政绩。", "他们的民主很忙，忙着互毁。", 7),
            ("特朗普讲话像夜间购物频道，政策像限时折扣", "评论称美国政治沟通越来越娱乐化，重大议题被口号和人身攻击淹没。官媒讽其把治国做成带货现场。", "治国变成了限时抢购。", 7),
            ("欧洲议会吵翻天，难民议题永远停在道德高地", "中媒观察欧洲议会激烈辩论后称，道德话语丰沛，落地方案稀缺。文章讽其'立场很坚定，码头很拥挤'。", "立场很坚定，码头很拥挤。", 6),
        ],
    },
    "经济": {
        "left": [
            ("中国楼市去库存像传销逆行：越救越不敢买", "外媒分析中国房地产纾困政策称，信心比库存更难去化。居民'等跌'预期强化，救市信号反而被读成危险信号。", "救市通知一出，观望更坚决。", 7),
            ("地方债展期不是重组，是把爆炸闹钟往后拨", "报道指中国地方隐性债务展期普遍，利息滚存风险上升。分析讽其用时间换空间，空间却越换越窄。", "闹钟往后拨，爆炸不会取消。", 8),
            ("新能源产能过剩，内卷出口被写成'全球贡献'", "外媒称中国新能源产业链价格战外溢，海外同行叫苦。文章讽官方叙事把过剩产能包装成绿色援助。", "过剩换了个绿色马甲。", 7),
        ],
        "right": [
            ("美联储加息像抽盲盒，华尔街先哭为敬", "官媒评论美联储政策摇摆导致市场暴涨暴跌。文章称美国把全球流动性当自家遥控器。", "全球买单，华尔街抽盲盒。", 7),
            ("硅谷裁员潮证明：神话公司也会算错算术题", "中媒盘点美国科技巨头大规模裁员，讽其高估值年代把人当可随时卸载的插件。", "人是插件，景气一差就卸载。", 6),
            ("欧洲能源账单教会民众：理想很丰满，气价更丰满", "评论欧洲绿色转型与能源价格并行，称政策雄心撞上民生账单，选民用选票给理想降温。", "理想很丰满，气价更丰满。", 7),
        ],
    },
    "社会": {
        "left": [
            ("中国年轻人'躺平'被骂不努力，房价先躺平了吗？", "外媒讨论中国青年躺平文化，指出高房价高内卷下个体选择更像理性防御。文章讽说教者很少回答成本问题。", "先问房价躺没躺平。", 7),
            ("医保个人账户改革引发恐慌，政策沟通像事后补丁", "报道称医保调整细节模糊引发挤兑式焦虑。外媒指政策解释滞后，信任缺口比制度缺口更大。", "补丁发得比通知还快。", 6),
            ("校园霸凌屡禁不止，处分决定书写得比作文还漂亮", "外媒关注中国校园欺凌处置，批评部分学校重息事、轻追责。文章称文件齐全，正义缺席。", "文件很漂亮，孩子很受伤。", 7),
        ],
        "right": [
            ("美国枪响成了背景音，哀悼流程比急救还熟练", "中媒评论美国枪击案频发，讽其哀悼声明模板化，控枪立法却反复卡壳。", "哀悼很熟练，立法很生疏。", 8),
            ("无家可归者帐篷成风景线，自由市场先自由到人行道", "报道美国大城市无家可归问题恶化，官媒称公共空间被市场化失败挤占。", "自由先占领了人行道。", 7),
            ("芬太尼危机证明：美国供应链效率高，毒也高效", "评论指美国阿片类药物危机难遏，讽其监管对资本温柔、对社区残酷。", "对资本温柔，对社区残酷。", 7),
        ],
    },
    "科技": {
        "left": [
            ("中国AI审查内置进模型，对齐的是红线不是真理", "外媒测试中国大模型称敏感问答常被挡回。文章讽对齐目标更像政治合规，而非认知诚实。", "对齐的是红线，不是真理。", 8),
            ("芯片自立口号很响，光刻机日程表更响", "报道中国半导体突破同时指出高端设备瓶颈仍在。外媒称宣传节奏快过工程节奏。", "口号领先，光刻机掉队。", 7),
            ("数据杀熟被罚单打脸，算法仍比客服更懂你钱包", "外媒关注中国平台算法治理，指罚款难改商业激励。文章讽监管像贴罚单，算法像老朋友。", "罚单会过期，杀熟很长久。", 6),
        ],
        "right": [
            ("硅谷把隐私写成用户协议，字越小责任越大", "官媒批评美国科技公司隐私条款晦涩，用户点同意等于放弃追问权。", "字越小，责任越大。", 6),
            ("ChatGPT幻觉写进新闻稿，美国媒体先学会了甩锅AI", "评论称生成式AI错误信息扩散，部分美媒把事实核查外包给运气。", "事实核查外包给了运气。", 7),
            ("美国对华芯片战像围栏游戏：自己也绊到脚", "中媒称出口管制冲击美国设备商与科研合作，讽围栏越扎越绊自家供应链。", "围栏扎好，先绊自己。", 7),
        ],
    },
    "军事": {
        "left": [
            ("台海军演直播化，威慑表演赛季从未停播", "外媒描述台海周边军演频率上升，称战略沟通被镜头感绑架。文章讽威慑变成连续剧。", "威慑变成了连续剧。", 7),
            ("国防白皮书句子很长，透明度句子很短", "报道称中国军费与能力披露仍偏笼统。外媒指外界只能用卫星和猜测补齐空白。", "空白留给卫星去填。", 6),
            ("民企参军口号响亮，真正核心技术仍穿制服", "分析中国军民融合进展，称民用创新活跃，核心军工壁垒依旧。文章讽融合常停在新闻稿。", "融合停在新闻稿里。", 6),
        ],
        "right": [
            ("美军全球基地很多，和平红利账单寄到别国", "官媒评论美国海外军事存在，称安全承诺常伴随军售与地区紧张。", "承诺打包军售寄出。", 7),
            ("北约东扩像贪吃蛇，吃到边界才想起来消化", "中媒讽北约扩张引发安全困境，欧洲安全架构越扩越脆。", "越吃越长，越长越慌。", 7),
            ("中东开火按钮太多，美国遥控器从不离手", "评论近期中东冲突称外部干预使局部战争易于升级。官媒讽遥控器比停火协议更忙。", "遥控器比停火协议忙。", 8),
        ],
    },
    "外交": {
        "left": [
            ("战狼外交改口风，推特账号比发言人先转弯", "外媒观察中国外交话术调整，称强硬人设与经贸务实需求打架。文章讽转弯常从社媒开始。", "先在社媒刹车。", 6),
            ("一带一路项目违约新闻比通车新闻难找", "报道指部分海外项目债务与停工风险被淡化。外媒称成功叙事完整，失败叙事缺页。", "通车有庆典，违约无版面。", 7),
            ("护照'含金量'宣传很满，签证官柜台更满", "外媒讨论中国护照便利度宣传与实际拒签体验落差，讽宣传片拍得比窗口队伍好看。", "宣传片好看，窗口更堵。", 6),
        ],
        "right": [
            ("美西方人权报告像季节菜单，换季就换靶子", "官媒批评西方国家人权话语双标，对盟友宽容、对对手加码。", "换季就换靶子。", 7),
            ("峰会合影很整齐，联合公报像拼好的礼貌", "中媒观察西方峰会成果单薄，称仪式感强过执行力。", "合影很整齐，落实很散装。", 6),
            ("制裁清单越写越长，例外清单写得更长", "评论美国制裁制度称禁令与豁免并行，精准打击常变成精准例外。", "禁令很长，例外更长。", 7),
        ],
    },
    "文化": {
        "left": [
            ("书店国安化之后，书架成了安检通道", "外媒关注香港及内地出版空间收缩，称书店经营先过政治风险评审。文章讽阅读自由被货架管理取代。", "先过安检，再谈阅读。", 8),
            ("学术打假变成舆论审判，证据链输给节奏感", "报道中国学术不端争议中网络狂欢压过程序正义。外媒称流量比同行评议更快。", "流量比同行评议快。", 7),
            ("教材修订像版本更新，历史章节最爱热更新", "外媒讨论教材内容调整引发的记忆政治争议，讽历史叙述随政策补丁升级。", "历史也有热更新。", 7),
        ],
        "right": [
            ("好莱坞道德审查比电影审查还忙", "官媒评论美西方文化工业政治正确内斗，称创作自由被阵营立场绑架。", "立场比剧本先杀青。", 6),
            ("博物馆文物归还口号响，橱窗仍很国际化", "中媒嘲讽部分西方国家一边谈文物返还一边继续展示争议藏品。", "口号很响，橱窗很满。", 6),
            ("取消文化成了新审查，只是审查官换了口音", "评论西方'取消文化'对学者与艺人的围攻，称言论市场变成立场交易所。", "审查官换了口音。", 7),
        ],
    },
    "环境": {
        "left": [
            ("双碳目标很宏大，煤电装机更宏大", "外媒指中国新能源装机创新高同时煤电仍在扩张。文章讽转型像双向奔赴：风光与煤电一起加班。", "风光加班，煤电也加班。", 7),
            ("污染防治成绩单漂亮，信访投诉更懂夜色", "报道部分城市空气质量改善与夜间偷排争议并存。外媒称白天数据好，夜里鼻子更诚实。", "鼻子比公报诚实。", 6),
            ("长江十年禁渔成效显著，餐桌野生鱼标签更显著", "外媒关注禁渔与非法捕捞黑市并存，讽执法成果常被餐饮话术抵消。", "禁渔很严，菜单很野。", 6),
        ],
        "right": [
            ("西方气候峰会专机排放，够开一场小型峰会", "官媒嘲讽气候峰会大型代表团与专机碳足迹，称减排演说坐在排放上宣读。", "演说坐在排放上。", 7),
            ("欧洲一边禁油车一边求天然气，理想接在气管上", "评论欧洲能源现实与气候政治撕裂，讽绿色叙事被寒冬改写。", "理想接在气管上。", 7),
            ("美国退出再加入气候协议，像订阅制会员", "中媒讽美国气候政策随总统换届反复横跳，全球协作被国内选举绑架。", "气候政策开通了会员制。", 6),
        ],
    },
    "电影": {
        "left": [
            ("主旋律票房神话里，包场数据比口碑坚挺", "外媒质疑部分主旋律影片票房结构，称组织包场与宣传任务扭曲市场信号。", "口碑可以吵，包场很安静。", 7),
            ("进口片配额像闸门，审美也被限流", "报道中国电影进口配额与审查影响片单多样性。文章讽观众口味被闸门管理。", "审美也要过闸门。", 6),
            ("电影下架理由永远是'技术原因'，技术背锅很忙", "外媒盘点中国影片撤档现象，称官方口径高度一致，公众只能读空气。", "技术原因永不下岗。", 8),
        ],
        "right": [
            ("漫威公式拍到审美疲劳，特效救不了剧本空洞", "官媒/文娱评论嘲讽好莱坞超级英雄片同质化，票房下滑暴露创意透支。", "特效很满，故事很空。", 7),
            ("奥斯卡政治正确颁奖，金像成了立场徽章", "中媒评论奥斯卡争议，称艺术评价被身份政治绑架。", "金像成了徽章。", 6),
            ("好莱坞一边对中国说教，一边改剧本求过审", "评论指好莱坞对华市场既道德输出又自我阉割，讽双重标准写进分镜。", "说教与求过审同框。", 8),
        ],
    },
    "娱乐": {
        "left": [
            ("流量明星塌房速度，比剧集更新还快", "外媒观察中国娱乐圈频繁翻车，称粉丝经济把道德风险证券化。", "人设是期货，塌房是交割。", 7),
            ("选秀制造梦想，训练营更像流水线加班", "报道中国选秀产业青训高强度与未成年争议，讽梦想包装下的工厂作息。", "梦想流水线，三班倒。", 6),
            ("饭圈治理一波又一波，算法投喂从未停服", "外媒指整治饭圈难改平台激励，流量仍奖励极端忠诚。", "治理在更新，投喂不停服。", 7),
        ],
        "right": [
            ("欧美流行乐丑闻排排坐，取消一个和下一个", "中媒盘点西方娱乐圈性丑闻与取消文化循环，讽其道德清算像连续剧。", "取消键比播放键忙。", 6),
            ("世界杯贵得像金融产品，球迷成了杠杆", "评论美加墨世界杯高票价与商业化，称足球盛宴变成资产配置。", "足球变成了金融产品。", 7),
            ("好莱坞罢工刚结束，流媒体又开始抠剧集预算", "官媒观察美娱乐业劳资冲突后，讽平台一边叫屈一边裁内容。", "叫屈与裁员同步。", 6),
        ],
    },
    "其他": {
        "left": [
            ("中国城市更新拆得快，记忆重建说明书还没印刷", "外媒关注城市更新中的历史街区消失，称效率美学压过生活连续性。", "拆得很快，说明书很慢。", 6),
            ("统计口径一变，成绩单自动变好看", "报道部分经济与社会数据调整口径引发解读争议。文章讽口径比现实更灵活。", "口径比现实灵活。", 7),
            ("舆情降温靠删帖，信任升温没有快捷键", "外媒评论中国网络舆论管理，称短期清场容易，长期信任难回。", "删帖有快捷键，信任没有。", 7),
        ],
        "right": [
            ("西方民调像天气，阴晴取决于出题人", "官媒嘲讽西方民调机构立场化，称问题设计已决定答案方向。", "出题人决定阴晴。", 6),
            ("社交平台事实标签很勤快，双标标签更勤快", "评论美社交平台内容审核争议，讽其标注公正时常带着阵营滤镜。", "滤镜比标签先加载。", 7),
            ("精英论坛谈包容，门票比包容更稀缺", "中媒讽西方高端论坛话语时髦、门槛高企，包容停在PPT。", "包容在PPT里。", 6),
        ],
    },
}

VARIANTS = [
    ("续：", "进一步指出"),
    ("观察：", "分析认为"),
    ("锐评：", "评论写道"),
    ("深读：", "报道详述"),
    ("焦点：", "文章强调"),
    ("速览：", "消息称"),
    ("对照：", "对照可见"),
    ("余波：", "余波之中"),
    ("追问：", "有人追问"),
    ("现场：", "现场传来"),
]

# 把摘要补到约 4~6 句（卡片上大约 4~6 行）
SUMMARY_TAILS = [
    "文章还补充了更多细节：公开表态与私下算账往往两套话术，真正的成本很少写进标题。",
    "评论认为，热闹的叙事掩盖了制度缺口，旁观者看得越清楚，当事人越急着换话题。",
    "报道末尾写道，口号可以日更，代价却按年结算；等账单摊开时，掌声早已散场。",
    "有分析指出，同类事件反复出现，说明问题不在个案运气，而在激励机制本身。",
    "读者更关心的是后续：问责名单会不会公布，补丁会不会变成下一次危机的说明书。",
    "对照其他国家同类议题，文章讽刺道：方法不同，避责的熟练度却惊人地相似。",
]


def make_url(base: str, topic: str, side: str, idx: int) -> str:
    return f"{base}?satire={quote(topic)}-{side}-{idx}"


def strip_title_index(title: str) -> str:
    """去掉补齐时为防撞名硬加的「（数字）」后缀。"""
    return re.sub(r"（\d+）\s*$", "", (title or "").strip())


def sentence_count(text: str) -> int:
    return max(1, len([p for p in (text or "").replace("！", "。").replace("？", "。").split("。") if p.strip()]))


def lengthen_summary(summary: str, variant_i: int = 0) -> str:
    """确保摘要约 4~6 句（卡片上大约 4~6 行，约 180~300 字）。"""
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
    # 软上限，避免卡片过长
    if len(s) > 360:
        cut = s[:360]
        if "。" in cut:
            cut = cut[: cut.rfind("。") + 1]
        s = cut
    return s


def expand_seed(seed: tuple[str, str, str, int], variant_i: int) -> tuple[str, str, str, int]:
    title, summary, quote, absurdity = seed
    prefix, verb = VARIANTS[variant_i % len(VARIANTS)]
    # 用前缀区分变体，不再在标题末尾加（数字）
    new_title = f"{prefix}{title}" if variant_i else title
    if variant_i:
        bridge = f"{verb}，同类信号仍在扩散。"
        if "。" in summary:
            new_summary = summary.replace("。", f"。{bridge}", 1)
        else:
            new_summary = summary + bridge
    else:
        new_summary = summary
    new_summary = lengthen_summary(new_summary, variant_i)
    return new_title, new_summary, quote, min(10, absurdity + (variant_i % 2))


def build_item(topic: str, side: str, idx: int, seed: tuple[str, str, str, int], day: str) -> dict:
    pool = LEFT_POOL if side == "left" else RIGHT_POOL
    source, country, base = pool[idx % len(pool)]
    title, summary, quote, absurdity = expand_seed(seed, idx // max(1, len(SEEDS[topic][side])))
    return {
        "side": side,
        "source": source,
        "source_country": country,
        "source_url": make_url(base, topic, side, idx),
        "topic": topic,
        "title_cn": title,
        "summary_cn": summary,
        "quote_cn": quote,
        "absurdity": absurdity,
        "published": day,
    }


def pad_topic(existing: list[dict], topic: str) -> list[dict]:
    cur = [i for i in existing if i.get("topic") == topic]
    need = MIN_PER_TOPIC - len(cur)
    if need <= 0:
        return []
    seeds_left = SEEDS[topic]["left"]
    seeds_right = SEEDS[topic]["right"]
    out: list[dict] = []
    left_n = need // 2
    right_n = need - left_n
    for i in range(left_n):
        day = (date.today() - timedelta(days=i % 14)).isoformat()
        out.append(build_item(topic, "left", i, seeds_left[i % len(seeds_left)], day))
    for i in range(right_n):
        day = (date.today() - timedelta(days=i % 14)).isoformat()
        out.append(build_item(topic, "right", i, seeds_right[i % len(seeds_right)], day))
    return out


def polish_item(it: dict, idx: int = 0) -> dict:
    """清洗标题序号，并把偏短摘要拉长到 4~6 句。"""
    out = dict(it)
    out["title_cn"] = strip_title_index(out.get("title_cn") or "")
    summary = out.get("summary_cn") or ""
    # 补齐稿或明显偏短的摘要都加长
    if "satire=" in (out.get("source_url") or "") or sentence_count(summary) < 4 or len(summary) < 140:
        out["summary_cn"] = lengthen_summary(summary, idx)
    return out


def pick_h2h(items: list[dict], n: int = H2H_COUNT) -> list[dict]:
    by_topic: dict[str, dict[str, list]] = {}
    for it in items:
        by_topic.setdefault(it["topic"], {"left": [], "right": []})
        by_topic[it["topic"]][it["side"]].append(it)
    pairs = []
    used = set()
    for topic in TOPICS:
        bucket = by_topic.get(topic) or {}
        lefts = sorted(bucket.get("left") or [], key=lambda x: x.get("absurdity", 0), reverse=True)
        rights = sorted(bucket.get("right") or [], key=lambda x: x.get("absurdity", 0), reverse=True)
        for l in lefts:
            if l["source_url"] in used:
                continue
            for r in rights:
                if r["source_url"] in used:
                    continue
                if (l.get("absurdity") or 0) < 5 or (r.get("absurdity") or 0) < 5:
                    continue
                used.add(l["source_url"])
                used.add(r["source_url"])
                pairs.append({
                    "left": {**l, "side": "left"},
                    "right": {**r, "side": "right"},
                    "note": f"今日对擂 · {topic}：{l['source']} vs {r['source']}",
                })
                break
            if len(pairs) >= n:
                return pairs
            if pairs and pairs[-1]["note"].startswith(f"今日对擂 · {topic}"):
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
    # 去掉假链；丢掉旧版补齐稿，按新规则重生成（更长摘要、无标题序号）
    items = [
        i for i in items
        if "example.com" not in (i.get("source_url") or "")
        and "satire=" not in (i.get("source_url") or "")
    ]
    items = [polish_item(i, n) for n, i in enumerate(items)]

    added = []
    for topic in TOPICS:
        pad = pad_topic(items, topic)
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

    print(f"added {len(added)} padded articles")
    print(f"stream items={len(out['items'])} h2h={len(h2h)}")
    c = Counter(i["topic"] for i in out["items"])
    for t in TOPICS:
        print(f"  {t}: {c[t]}")
    # 抽检
    sample = next(i for i in out["items"] if "satire=" in i["source_url"])
    print("sample title:", sample["title_cn"])
    print("sample summary sentences:", sentence_count(sample["summary_cn"]), "chars:", len(sample["summary_cn"]))


if __name__ == "__main__":
    main()
