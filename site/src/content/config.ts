import { defineCollection, z } from "astro:content";

/** 与 prompts/process.py TOPICS 保持一致 */
const TOPIC = z.enum([
  "政治", "经济", "社会", "科技", "军事",
  "外交", "文化", "环境", "电影", "娱乐", "其他",
]);

const articleFields = {
  side: z.enum(["left", "right"]),
  source: z.string(),
  source_country: z.string(),
  source_url: z.string().url(),
  topic: TOPIC,
  title_cn: z.string(),
  summary_cn: z.string(),
  quote_cn: z.string().optional(),
  absurdity: z.number().int().min(1).max(10),
  published: z.string().optional(),
};

const articleSchema = z.object(articleFields);

/**
 * 文章数据集合
 * 不分日期，所有文章作为统一流，客户端按 10 条/批无限滚动加载
 * 数据源：src/content/daily/articles.json（构建前复制到 public/）
 */
const h2hPair = z.object({
  left: articleSchema,
  right: articleSchema,
  note: z.string(),
});

const articles = defineCollection({
  type: "data",
  schema: z.object({
    date: z.string().optional(), // 日报日期 YYYY-MM-DD（首页展示用）
    items: z.array(articleSchema),
    // 今日对擂：最多 5 组；兼容旧版单对象
    head_to_head: z
      .union([h2hPair, z.array(h2hPair), z.null()])
      .optional(),
  }),
});

export const collections = { daily: articles };
