import { defineCollection, z } from "astro:content";

/**
 * 文章数据集合
 * 不分日期，所有文章作为统一流，客户端按 10 条/批无限滚动加载
 * 数据文件位置：src/content/daily/{任意名}.json，每个文件含若干条
 */
const articles = defineCollection({
  type: "data",
  schema: z.object({
    // 文章列表（混合 left/right，由 side 字段区分栏位）
    items: z.array(
      z.object({
        side: z.enum(["left", "right"]),
        source: z.string(),                    // 媒体名或社交账号
        source_country: z.string(),
        source_url: z.string().url(),
        topic: z.enum([
          "政治", "经济", "社会", "科技", "军事",
          "外交", "文化", "环境", "其他",
        ]),
        title_cn: z.string(),
        summary_cn: z.string(),
        quote_cn: z.string().optional(),
        absurdity: z.number().int().min(1).max(10),
      }),
    ),
  }),
});

export const collections = { daily: articles };
