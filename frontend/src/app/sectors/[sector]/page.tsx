import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import { getSectorStocks, getAllSectors } from "@/lib/public-api";
import { StructuredData } from "@/components/StructuredData";
import type { Company } from "@/types";

interface PageProps {
  params: Promise<{ sector: string }>;
}

// 動的レンダリング（ビルド時のAPI依存を回避）
export const dynamic = "force-dynamic";

// 静的パラメータを生成 - ビルド時はスキップ
export async function generateStaticParams() {
  // ビルド時はAPIが利用できないため空配列を返す
  return [];
}

// 動的メタデータ生成
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { sector: encodedSector } = await params;
  const sector = decodeURIComponent(encodedSector);

  const title = `${sector}関連銘柄一覧 | イリスのIR分析`;
  const description = `${sector}セクターの上場企業一覧。各社のIR資料をAIアナリスト「イリス」が分析し、決算情報を要約。`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
    },
  };
}

// 1時間ごとに再生成
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

export default async function SectorDetailPage({ params }: PageProps) {
  const { sector: encodedSector } = await params;
  const sector = decodeURIComponent(encodedSector);

  let data;
  try {
    data = await getSectorStocks(sector, 0, 500);
  } catch {
    notFound();
  }

  const { stocks, total } = data;

  // 構造化データ
  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "ホーム",
        item: process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app",
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "銘柄一覧",
        item: `${process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app"}/stocks`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: sector,
        item: `${process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app"}/sectors/${encodeURIComponent(sector)}`,
      },
    ],
  };

  return (
    <>
      <StructuredData data={breadcrumbData} />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* パンくずリスト */}
        <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/" className="hover:text-indigo-600 transition-colors">
            ホーム
          </Link>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <Link href="/stocks" className="hover:text-indigo-600 transition-colors">
            銘柄一覧
          </Link>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-gray-900 font-medium">{sector}</span>
        </nav>

        {/* ヘッダー */}
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
              <div className="flex items-center gap-3">
                <h1 className="section-title text-2xl md:text-3xl">{sector}</h1>
                <span className="iris-badge">{total.toLocaleString()}銘柄</span>
              </div>
              <p className="text-gray-600 mt-3">
                「{sector}セクターの銘柄を一覧でご確認いただけます。」
              </p>
            </div>
          </div>
        </div>

        {/* 銘柄グリッド */}
        {stocks.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {stocks.map((stock) => (
              <StockCard key={stock.id} stock={stock} />
            ))}
          </div>
        ) : (
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-indigo-100 mb-4">
              <Image
                src="/images/iris/iris-normal.png"
                alt="イリス"
                width={48}
                height={48}
                className="opacity-50"
              />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">銘柄が見つかりませんでした</h3>
            <p className="text-gray-500 mb-4">「この業種の銘柄はまだ登録されていないようです...」</p>
            <Link href="/stocks" className="btn-iris inline-block">
              すべての銘柄を見る
            </Link>
          </div>
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
