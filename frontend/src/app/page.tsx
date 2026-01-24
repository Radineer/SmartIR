"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import type { Company, Document } from "@/types";

export default function Home() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [irisMessage, setIrisMessage] = useState("");

  const irisGreetings = [
    "こんにちは！イリスです。一緒にIR資料を読み解きましょう。",
    "2050年から来ました、AIアナリストのイリスです。",
    "決算シーズンですね。データがいっぱいで楽しいです！",
    "IR資料、難しそう...？大丈夫、私が解説します！",
    "データは嘘をつきませんから。一緒に分析しましょう。",
  ];

  useEffect(() => {
    setIrisMessage(irisGreetings[Math.floor(Math.random() * irisGreetings.length)]);

    Promise.all([
      api.getCompanies(0, 6),
      api.getDocuments(undefined, 7),
    ])
      .then(([companiesData, documentsData]) => {
        setCompanies(companiesData);
        setDocuments(documentsData.slice(0, 6));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2 animate-pulse">
            <Image
              src="/images/iris/iris-normal.png"
              alt="イリス"
              width={64}
              height={64}
              className="object-cover"
            />
          </div>
          <p className="text-indigo-600 text-sm">データを読み込んでいます...</p>
        </div>
      </div>
    );
  }

  const docTypeLabels: Record<string, string> = {
    financial_report: "決算短信",
    annual_report: "有報",
    press_release: "PR",
    presentation: "説明資料",
    other: "その他",
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* ヒーローセクション */}
      <div className="relative overflow-hidden rounded-3xl mb-10">
        {/* 背景グラデーション */}
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600 via-purple-600 to-cyan-500" />

        {/* アニメーション背景 */}
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-0 right-0 w-96 h-96 bg-white rounded-full blur-3xl transform translate-x-1/3 -translate-y-1/3 animate-pulse" />
          <div className="absolute bottom-0 left-0 w-80 h-80 bg-cyan-300 rounded-full blur-3xl transform -translate-x-1/3 translate-y-1/3" />
          <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-pink-300 rounded-full blur-3xl transform -translate-x-1/2 -translate-y-1/2 animate-pulse" style={{ animationDelay: "1s" }} />
        </div>

        {/* データストリーム風エフェクト */}
        <div className="absolute inset-0 opacity-10 overflow-hidden">
          <div className="absolute inset-0" style={{ backgroundImage: "repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(255,255,255,0.1) 50px, rgba(255,255,255,0.1) 51px)" }} />
        </div>

        <div className="relative px-8 py-12 md:py-16">
          <div className="flex flex-col md:flex-row items-center gap-8">
            {/* イリスキャラクター */}
            <div className="flex-shrink-0 relative">
              <div className="absolute inset-0 bg-white/20 rounded-full blur-2xl scale-110" />
              <div className="relative w-36 h-36 md:w-48 md:h-48 rounded-full overflow-hidden ring-4 ring-white/30 ring-offset-4 ring-offset-transparent">
                <Image
                  src="/images/iris/iris-normal.png"
                  alt="イリス - AI IR アナリスト"
                  width={192}
                  height={192}
                  className="object-cover"
                  priority
                />
              </div>
              {/* ステータスバッジ */}
              <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 bg-white rounded-full px-3 py-1 shadow-lg">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                  <span className="text-xs font-medium text-gray-700">分析稼働中</span>
                </div>
              </div>
            </div>

            {/* テキストコンテンツ */}
            <div className="flex-1 text-center md:text-left text-white">
              <div className="inline-flex items-center gap-2 bg-white/20 backdrop-blur-sm rounded-full px-4 py-1.5 text-sm mb-4">
                <span className="w-2 h-2 bg-cyan-300 rounded-full animate-pulse" />
                <span>2050年から来たAIアナリスト</span>
              </div>
              <h1 className="text-3xl md:text-5xl font-bold mb-4 leading-tight">
                イリスと読み解く<br className="md:hidden" />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-200 to-white">IR資料</span>
              </h1>
              <div className="glass bg-white/10 rounded-xl p-4 mb-6 max-w-lg mx-auto md:mx-0">
                <p className="text-white/90 italic">「{irisMessage}」</p>
              </div>
              <p className="text-indigo-100 mb-8 max-w-xl mx-auto md:mx-0">
                上場企業のIR資料をAIが自動分析。重要ポイントの抽出、センチメント分析をわかりやすく解説します。
              </p>
              <div className="flex flex-wrap justify-center md:justify-start gap-4">
                <Link
                  href="/stocks"
                  className="btn-iris bg-white text-indigo-600 hover:bg-indigo-50 px-8 py-3 text-lg font-semibold shadow-xl"
                >
                  銘柄一覧を見る
                </Link>
                <Link
                  href="/faq"
                  className="px-8 py-3 rounded-xl font-medium bg-white/10 backdrop-blur-sm border border-white/30 hover:bg-white/20 transition"
                >
                  使い方を見る
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 特徴セクション */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        {[
          {
            icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
            title: "AI分析",
            description: "最新AIが決算短信・有報を自動要約",
          },
          {
            icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
            title: "センチメント",
            description: "ポジティブ/ネガティブを数値化",
          },
          {
            icon: "M13 10V3L4 14h7v7l9-11h-7z",
            title: "リアルタイム",
            description: "IR資料公開後すぐに分析開始",
          },
        ].map((feature, i) => (
          <div key={i} className="holo-card p-6 text-center group">
            <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center group-hover:scale-110 transition-transform">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={feature.icon} />
              </svg>
            </div>
            <h3 className="font-bold text-gray-900 mb-2">{feature.title}</h3>
            <p className="text-sm text-gray-600">{feature.description}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 注目企業 */}
        <div className="lg:col-span-2">
          <div className="flex justify-between items-center mb-4">
            <h2 className="section-title">注目企業</h2>
            <Link href="/stocks" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1">
              すべて見る
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {companies.map((company) => (
              <Link key={company.id} href={`/stocks/${company.ticker_code}`}>
                <div className="holo-card p-5 cursor-pointer group h-full">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
                        {company.ticker_code}
                      </span>
                      <h3 className="text-base font-semibold text-gray-900 mt-2 group-hover:text-indigo-600 transition-colors truncate">
                        {company.name}
                      </h3>
                    </div>
                    {company.sector && (
                      <span className="iris-badge flex-shrink-0">{company.sector}</span>
                    )}
                  </div>
                  {company.industry && (
                    <p className="text-xs text-gray-500 mt-2 truncate">{company.industry}</p>
                  )}
                  <div className="mt-3 pt-3 border-t border-indigo-100/50 flex items-center justify-end">
                    <span className="text-xs text-indigo-500 group-hover:translate-x-1 transition-transform">
                      詳細 →
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* 最新IR資料 */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="section-title">最新IR資料</h2>
            <Link href="/documents" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1">
              すべて見る
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
          <div className="space-y-3">
            {documents.map((doc) => (
              <Link key={doc.id} href={`/documents/${doc.id}`}>
                <div className="holo-card p-4 cursor-pointer group">
                  <div className="flex items-start gap-3">
                    <div className="w-1 h-12 rounded-full bg-gradient-to-b from-indigo-500 to-cyan-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-900 group-hover:text-indigo-600 transition-colors line-clamp-1">
                        {doc.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                          {docTypeLabels[doc.doc_type] || doc.doc_type}
                        </span>
                        <span className="text-xs text-gray-400">{doc.publish_date}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* CTAセクション */}
      <div className="mt-12 glass rounded-2xl p-8">
        <div className="flex flex-col md:flex-row items-center gap-6">
          <div className="flex-shrink-0 w-20 h-20 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-4">
            <Image
              src="/images/iris/iris-analysis.png"
              alt="イリス"
              width={80}
              height={80}
              className="object-cover"
            />
          </div>
          <div className="flex-1 text-center md:text-left">
            <h2 className="text-xl font-bold text-gray-900 mb-2">もっとIR分析を活用しませんか？</h2>
            <p className="text-gray-600">
              「気になる銘柄があれば、ぜひチェックしてみてください。データから見える企業の姿をお伝えします。」
            </p>
          </div>
          <div className="flex gap-3">
            <Link href="/stocks" className="btn-iris">
              銘柄を探す
            </Link>
            <Link href="/glossary" className="btn-iris-outline">
              用語を学ぶ
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
