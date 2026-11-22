/**
 * 動態 sitemap 修補方案（Next.js App Router）
 *
 * 問題：目前 https://wiki.sengokus.jp/sitemap.xml 是靜態檔，只含 10 個欄目頁，
 *      不含任何 /articles/<slug>/ 文章頁 → 新文章永遠不會被百度／Google 發現。
 *
 * 這裡給兩個方案，擇一即可。技術方貼上後 Redeploy，再用
 * `curl -s https://wiki.sengokus.jp/sitemap.xml | grep logistics-two-ku-famine` 驗證。
 */

// ─────────────────────────────────────────────────────────────
// 方案 A（推薦）：新增 app/sitemap.ts，由 Next.js 自動產生 /sitemap.xml
// 優點：一個檔案搞定，靜態頁與文章頁一起輸出，不必改 robots.txt
// 注意：若專案已有 public/sitemap.xml 靜態檔，必須先刪掉，否則會衝突
// ─────────────────────────────────────────────────────────────

import type { MetadataRoute } from 'next'

type Article = {
  slug: string
  updatedAt: string // ISO 8601
  publishedAt: string
}

// ⚠️ 替換點：改成你們實際的資料來源（Prisma／Drizzle／KV／現有 GET API 皆可）
async function getPublishedArticles(): Promise<Article[]> {
  // 範例 A1：直接查資料庫
  // const rows = await db.article.findMany({
  //   where: { status: 'published' },
  //   select: { slug: true, updatedAt: true, publishedAt: true },
  // })
  // return rows.map(r => ({ ...r, updatedAt: r.updatedAt.toISOString(), publishedAt: r.publishedAt.toISOString() }))

  // 範例 A2：呼叫既有 API（需帶內部 Token，或用 server-only 的查詢函式避免外網呼叫）
  const res = await fetch('https://wiki.sengokus.jp/api/wiki/articles', {
    headers: { Authorization: `Bearer ${process.env.WIKI_API_TOKEN}` },
    next: { revalidate: 3600 }, // 每小時快取，避免每次請求都打 API
  })
  if (!res.ok) return [] // 取不到就只輸出靜態頁，不要讓 sitemap 掛掉
  const data = await res.json()
  const list = Array.isArray(data) ? data : (data.articles ?? [])
  return list
    .filter((a: any) => a.status === 'published')
    .map((a: any) => ({
      slug: a.slug,
      updatedAt: a.updatedAt ?? a.publishedAt,
      publishedAt: a.publishedAt,
    }))
}

const SITE = 'https://wiki.sengokus.jp'

// 靜態欄目頁（與目前 sitemap.xml 一致）
const STATIC_PAGES: { path: string; priority: number; changefreq: 'daily' | 'weekly' | 'monthly' }[] = [
  { path: '/', priority: 0.9, changefreq: 'daily' },
  { path: '/getting-started/', priority: 0.8, changefreq: 'weekly' },
  { path: '/battle/', priority: 0.8, changefreq: 'weekly' },
  { path: '/economy/', priority: 0.8, changefreq: 'weekly' },
  { path: '/database/', priority: 0.8, changefreq: 'weekly' },
  { path: '/npc/', priority: 0.8, changefreq: 'weekly' },
  { path: '/realm/', priority: 0.8, changefreq: 'weekly' },
  { path: '/articles/', priority: 0.8, changefreq: 'daily' }, // 文章列表頁改 daily，因為每週有新文
  { path: '/faq/', priority: 0.8, changefreq: 'weekly' },
]

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const articles = await getPublishedArticles().catch(() => [])

  const staticEntries: MetadataRoute.Sitemap = STATIC_PAGES.map((p) => ({
    url: `${SITE}${p.path}`,
    lastModified: new Date(),
    changeFrequency: p.changefreq,
    priority: p.priority,
  }))

  const articleEntries: MetadataRoute.Sitemap = articles.map((a) => ({
    url: `${SITE}/articles/${a.slug}/`,
    lastModified: new Date(a.updatedAt),
    changeFrequency: 'monthly',
    priority: 0.7,
  }))

  return [...staticEntries, ...articleEntries]
}

// ─────────────────────────────────────────────────────────────
// 方案 B（最小改動）：保留現有靜態 sitemap.xml，另加文章專用 sitemap
// 1) 新增 app/sitemap-articles.xml/route.ts，內容如下：
//
//    export const revalidate = 3600
//    export async function GET() {
//      const articles = await getPublishedArticles()
//      const urls = articles.map(a =>
//        `  <url><loc>${SITE}/articles/${a.slug}/</loc>` +
//        `<lastmod>${a.updatedAt}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>`
//      ).join('\n')
//      const xml = `<?xml version="1.0" encoding="UTF-8"?>
// <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
// ${urls}
// </urlset>`
//      return new Response(xml, { headers: { 'Content-Type': 'application/xml' } })
//    }
//
// 2) 在 public/robots.txt 末尾加一行：
//    Sitemap: https://wiki.sengokus.jp/sitemap-articles.xml
//
// 3) 到百度資源平台與 Google Search Console 各補提交這個新 sitemap
// ─────────────────────────────────────────────────────────────
