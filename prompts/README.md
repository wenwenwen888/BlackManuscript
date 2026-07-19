# LLM Prompt 模板设计

## 设计原则

1. **三段式流水线 + 一道安全阀**
   - `classify`：门控，判断是否在嘲讽对方。被否就丢弃，节省后续 token
   - `process`：摘要翻译 + 打主题标签 + 荒诞指数 + 金句提取，合并一次调用输出 JSON
   - `validate`：安全阀，校验摘要是否歪曲原意，被否丢入 drafts 池

2. **强制结构化输出（JSON）**
   - 每个 prompt 末尾固定要求返回严格 JSON，便于程序解析
   - 给 JSON Schema 示例，降低模型出格式错的概率

3. **分类标准要可操作**
   - "嘲讽" ≠ 单纯报道。明确给模型判断依据：负面评价、讽刺修辞、批评立场
   - 中性报道（如"中国 GDP 增长 5%"）不算，要剔除
   - 立场鲜明但纯赞美的也不算（如中国官媒夸中国自己）

4. **摘要风格：忠实事实，但绝不温吞**
   - 必须忠实于原文事实：不得编造原文没有的事件、数据、引语
   - **必须呈现原文的辛辣**：原文若用嘲讽、反讽、夸张、激烈修辞，摘要要忠实呈现这种力度，不得弱化
   - 摘要要**突出原文的嘲讽点**：抓住最尖锐的论断、最具张力的对比、最刺痛对方的措辞
   - 这是个微妙平衡："劲爆"来自原文本身，不是 LLM 加料

5. **金句 quote_cn**
   - 提取原文中**最辛辣、最具代表性**的一句话的中文版
   - 在卡片上以大引号高亮展示，是每条新闻的"炸点"
   - 必须是原文真实存在的句子，不得生成

6. **语言策略**
   - 英文源（CGTN/AP/Reuters/NYT/Economist）-> 中文摘要（强制翻译，传神有张力）
   - 中文源（环球/观察者网/参考消息）-> 中文摘要（直接凝练）

## 文件结构

```
prompts/
├── README.md           本文档
├── classify.py         分类 prompt（是否嘲讽对方）
├── process.py          处理 prompt（摘要+标签+荒诞指数+金句）
├── validate.py         校验 prompt（摘要是否歪曲原意）
└── examples.py         各 prompt 的示例输入/输出，便于回归测试
```

## 调用流程

```
对每条候选文章：
  1. 调 classify(title, body, side)
     -> 返回 {"pass": bool, "target": str, "reason": str}
     -> pass=false 则丢弃
  
  2. 调 process(title, body, source_lang, side)
     -> 返回 {"summary_cn": str, "topic": str, "absurdity": int, "quote_cn": str}
     -> summary_cn 2-3 句中文，最多 130 字
     -> topic 取自固定枚举
     -> absurdity 1-10
     -> quote_cn 原文最辛辣一句的中文版（可为空）
  
  3. 调 validate(original_body, summary_cn, source_lang)
     -> 返回 {"distorted": bool, "reason": str}
     -> distorted=true 则进 drafts 池，不发布
```

## 模型选择建议

- **classify**：用便宜快模型（DeepSeek-V3 / GPT-4o-mini / Claude Haiku），输入短
- **process**：用强模型（Claude Sonnet / GPT-4o / DeepSeek-V3），输入长正文，要质量
- **validate**：用便宜模型即可，对比任务简单

## 主题标签固定枚举

`政治 / 经济 / 社会 / 科技 / 军事 / 外交 / 文化 / 环境 / 其他`

固定枚举便于归档与检索，避免 LLM 自由发挥导致标签碎片化。

## 荒诞指数定义（1-10）

基于原文**既有的**嘲讽力度，不是让 LLM 自己加嘲讽：

- 1-3：温和批评、客观陈述带负面立场
- 4-6：明确嘲讽、修辞手法（反讽、夸张）
- 7-8：辛辣嘲讽、直接点名批评、扣帽子
- 9-10：极端讽刺、激烈攻击

用于排序与"今日对擂"挑选，不做展示夸张用。
