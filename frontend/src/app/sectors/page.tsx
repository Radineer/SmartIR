import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { getAllSectors } from "@/lib/public-api";
import { BreadcrumbData } from "@/components/StructuredData";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app";

export const metadata: Metadata = {
  title: "業種別銘柄一覧 | イリスのIR分析",
  description:
    "業種別に上場企業のIR資料を分析。製造業、情報通信、金融など各セクターの決算情報をAIアナリスト「イリス」が要約。",
  alternates: {
    canonical: `${SITE_URL}/sectors`,
  },
  openGraph: {
    title: "業種別銘柄一覧 | イリスのIR分析",
    description: "業種別に上場企業のIR資料を分析。各セクターの決算情報をAIが要約。",
    type: "website",
    url: `${SITE_URL}/sectors`,
  },
};

// 動的レンダリング（ビルド時のAPI依存を回避）
export const dynamic = "force-dynamic";
export const revalidate = 3600;

// セクターごとのアイコン
const sectorIcons: Record<string, string> = {
  情報通信: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
  サービス業: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z",
  小売業: "M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z",
  電気機器: "M13 10V3L4 14h7v7l9-11h-7z",
  機械: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
  化学: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
  銀行業: "M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z",
  不動産業: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  医薬品: "M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z",
  食料品: "M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z",
};

export default async function SectorsPage() {
  const { sectors } = await getAllSectors();

  const breadcrumbs = [
    { name: "ホーム", url: "/" },
    { name: "業種別", url: "/sectors" },
  ];

  // 銘柄数でソート
  const sortedSectors = [...sectors].sort((a, b) => b.stock_count - a.stock_count);

  return (
    <>
      <BreadcrumbData items={breadcrumbs} />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* パンくずリスト */}
        <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/" className="hover:text-indigo-600 transition-colors">
            ホーム
          </Link>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-gray-900 font-medium">業種別</span>
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
              <h1 className="section-title text-2xl md:text-3xl">業種別銘柄一覧</h1>
              <p className="text-gray-600 mt-3">
                <span className="text-indigo-600 font-semibold">{sectors.length}</span>業種の上場企業をAI分析中
              </p>
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100">
                <span className="text-sm text-indigo-700">「業種ごとにまとめて確認できますよ」</span>
              </div>
            </div>
          </div>
        </div>

        {/* 業種グリッド */}
        {sortedSectors.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sortedSectors.map((sector) => (
              <Link
                key={sector.name}
                href={`/sectors/${encodeURIComponent(sector.name)}`}
              >
                <div className="holo-card p-6 cursor-pointer group h-full">
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center">
                      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d={sectorIcons[sector.name] || "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"}
                        />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <h2 className="text-lg font-semibold text-gray-900 group-hover:text-indigo-600 transition-colors">
                        {sector.name}
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        {sector.stock_count.toLocaleString()}銘柄
                      </p>
                    </div>
                    <span className="text-indigo-500 group-hover:translate-x-1 transition-transform">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </span>
                  </div>
                </div>
              </Link>
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
            <h3 className="text-lg font-medium text-gray-900 mb-2">業種データがありません</h3>
            <p className="text-gray-500 mb-4">「データの準備中です...」</p>
            <Link href="/stocks" className="btn-iris inline-block">
              銘柄一覧を見る
            </Link>
          </div>
        )}
      </div>
    </>
  );
}
