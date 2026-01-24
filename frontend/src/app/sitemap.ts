import { MetadataRoute } from "next";
import { getAllStocks, getAllSectors } from "@/lib/public-api";

// 動的生成（リクエスト時に生成）
export const dynamic = "force-dynamic";
export const revalidate = 3600;

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrls: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${SITE_URL}/stocks`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/sectors`,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/faq`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/glossary`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.7,
    },
  ];

  // 全銘柄のURL
  let stockUrls: MetadataRoute.Sitemap = [];
  try {
    const { stocks } = await getAllStocks(0, 5000);
    stockUrls = stocks.map((stock) => ({
      url: `${SITE_URL}/stocks/${stock.ticker_code}`,
      lastModified: new Date(stock.updated_at),
      changeFrequency: "daily" as const,
      priority: 0.8,
    }));
  } catch (error) {
    console.error("Failed to fetch stocks for sitemap:", error);
  }

  // 全業種のURL
  let sectorUrls: MetadataRoute.Sitemap = [];
  try {
    const { sectors } = await getAllSectors();
    sectorUrls = sectors.map((sector) => ({
      url: `${SITE_URL}/sectors/${encodeURIComponent(sector.name)}`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.7,
    }));
  } catch (error) {
    console.error("Failed to fetch sectors for sitemap:", error);
  }

  return [...baseUrls, ...stockUrls, ...sectorUrls];
}
