import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { getAllStocks, getAllSectors } from "@/lib/public-api";
import { BreadcrumbData, ItemListData } from "@/components/StructuredData";
import type { Company, SectorInfo } from "@/types";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app";

export const metadata: Metadata = {
  title: "銘柄一覧 | イリスのIR分析",
  description:
    "上場企業のIR資料をAIアナリスト「イリス」が自動分析。決算短信、有価証券報告書の要約・センチメント分析で投資判断をサポート。",
  keywords: ["株式", "IR", "決算", "銘柄一覧", "有価証券報告書", "決算短信", "AI分析", "投資", "イリス"],
  alternates: {
    canonical: `${SITE_URL}/stocks`,
  },
  openGraph: {
    title: "銘柄一覧 | イリスのIR分析",
    description: "上場企業のIR資料をAIアナリスト「イリス」が自動分析。",
    type: "website",
    url: `${SITE_URL}/stocks`,
  },
};

// 動的レンダリング
export const dynamic = "force-dynamic";
export const revalidate = 3600;

function StockCard({ stock }: { stock: Company }) {
  return (
    <Link href={`/stocks/${stock.ticker_code}`}>
      <div className="holo-card p-4 cursor-pointer group h-full">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
              {stock.ticker_code}
            </span>
            <h3 className="text-base font-semibold text-gray-900 mt-2 group-hover:text-indigo-600 transition-colors truncate">
              {stock.name}
            </h3>
          </div>
        </div>
        {stock.sector && (
          <span className="iris-badge mt-3">
            {stock.sector}
          </span>
        )}
        {stock.industry && (
          <p className="text-xs text-gray-500 mt-2 truncate">{stock.industry}</p>
        )}
        <div className="mt-3 pt-3 border-t border-indigo-100/50 flex items-center justify-between">
          <span className="text-xs text-gray-400">IR資料 {stock.document_count || 0}件</span>
          <span className="text-xs text-indigo-500 group-hover:translate-x-1 transition-transform">
            詳細 →
          </span>
        </div>
      </div>
    </Link>
  );
}

function SectorFilter({
  sectors,
  currentSector,
}: {
  sectors: SectorInfo[];
  currentSector?: string;
}) {
  return (
    <div className="glass rounded-xl p-4 mb-8">
      <div className="flex items-center gap-3 mb-3">
        <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
        </svg>
        <span className="font-medium text-gray-700">業種で絞り込み</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link
          href="/stocks"
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
            !currentSector
              ? "btn-iris"
              : "bg-gray-100 text-gray-600 hover:bg-indigo-50 hover:text-indigo-600"
          }`}
        >
          すべて
        </Link>
        {sectors.map((sector) => (
          <Link
            key={sector.name}
            href={`/sectors/${encodeURIComponent(sector.name)}`}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              currentSector === sector.name
                ? "btn-iris"
                : "bg-gray-100 text-gray-600 hover:bg-indigo-50 hover:text-indigo-600"
            }`}
          >
            {sector.name}
            <span className="ml-1 text-xs opacity-70">({sector.stock_count})</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-16">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-indigo-100 mb-4">
        <Image
          src="/images/iris/iris-icon.png"
          alt="イリス"
          width={48}
          height={48}
          className="opacity-50"
        />
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">銘柄が見つかりませんでした</h3>
      <p className="text-gray-500 mb-4">「条件を変更して再度お試しください...」</p>
      <Link href="/stocks" className="btn-iris inline-block">
        すべての銘柄を見る
      </Link>
    </div>
  );
}

export default async function StocksPage() {
  const [stocksData, sectorsData] = await Promise.all([
    getAllStocks(0, 1000),
    getAllSectors(),
  ]);

  const { stocks, total } = stocksData;
  const { sectors } = sectorsData;

  const breadcrumbs = [
    { name: "ホーム", url: "/" },
    { name: "銘柄一覧", url: "/stocks" },
  ];

  const stockListItems = stocks.slice(0, 50).map((stock, index) => ({
    name: `${stock.name}（${stock.ticker_code}）`,
    url: `/stocks/${stock.ticker_code}`,
    position: index + 1,
  }));

  return (
    <>
      <BreadcrumbData items={breadcrumbs} />
      <ItemListData items={stockListItems} name="銘柄一覧" />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/" className="hover:text-indigo-600 transition-colors">
            ホーム
          </Link>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-gray-900 font-medium">銘柄一覧</span>
        </nav>

        {/* Header with Iris */}
        <div className="glass rounded-2xl p-6 mb-8">
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            <div className="flex-shrink-0">
              <div className="relative w-16 h-16 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
                <Image
                  src="/images/iris/iris-normal.png"
                  alt="イリス"
                  width={64}
                  height={64}
                  className="object-cover"
                />
              </div>
            </div>
            <div className="flex-1">
              <h1 className="section-title text-2xl md:text-3xl">銘柄一覧</h1>
              <p className="text-gray-600 mt-4">
                <span className="text-indigo-600 font-semibold">{total.toLocaleString()}</span>銘柄のIR資料をAI分析中
              </p>
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100">
                <span className="text-sm text-indigo-700">「気になる銘柄を見つけてみてください」</span>
              </div>
            </div>
          </div>
        </div>

        {/* Sector Filter */}
        <SectorFilter sectors={sectors} />

        {/* Stock Grid */}
        {stocks.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {stocks.map((stock) => (
              <StockCard key={stock.id} stock={stock} />
            ))}
          </div>
        ) : (
          <EmptyState />
        )}

        {/* Stats */}
        {stocks.length > 0 && (
          <div className="mt-8 text-center">
            <p className="text-sm text-gray-500">
              表示中: {stocks.length} / {total.toLocaleString()} 銘柄
            </p>
          </div>
        )}
      </div>
    </>
  );
}
