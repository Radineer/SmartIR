"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import type { Document } from "@/types";

const docTypeLabels: Record<string, string> = {
  financial_report: "決算短信",
  annual_report: "有価証券報告書",
  press_release: "プレスリリース",
  presentation: "決算説明会資料",
  other: "その他",
};

const docTypeColors: Record<string, string> = {
  financial_report: "from-emerald-500 to-green-500",
  annual_report: "from-purple-500 to-indigo-500",
  press_release: "from-amber-500 to-orange-500",
  presentation: "from-cyan-500 to-blue-500",
  other: "from-gray-400 to-gray-500",
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    setLoading(true);
    api.getDocuments(undefined, days)
      .then(setDocuments)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [days]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
            <h1 className="section-title text-2xl md:text-3xl">IR資料一覧</h1>
            <p className="text-gray-600 mt-3">
              「最新のIR資料をまとめています。気になる資料があれば、詳細を確認してみてください。」
            </p>
          </div>
          <div className="flex-shrink-0">
            <div className="relative">
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="pl-4 pr-10 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent appearance-none bg-white cursor-pointer"
              >
                <option value={1}>過去1日</option>
                <option value={7}>過去7日</option>
                <option value={30}>過去30日</option>
                <option value={90}>過去90日</option>
              </select>
              <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
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
            <p className="text-indigo-600 text-sm">資料を読み込んでいます...</p>
          </div>
        </div>
      ) : documents.length === 0 ? (
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
          <h3 className="text-lg font-medium text-gray-900 mb-2">資料が見つかりません</h3>
          <p className="text-gray-500 mb-4">「この期間のIR資料はまだないようです...」</p>
          <button
            onClick={() => setDays(90)}
            className="btn-iris"
          >
            期間を広げて検索
          </button>
        </div>
      ) : (
        <>
          <div className="mb-4 text-sm text-gray-500">
            {documents.length}件の資料
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.map((doc) => (
              <Link key={doc.id} href={`/documents/${doc.id}`}>
                <div className="holo-card p-4 cursor-pointer group h-full">
                  <div className="flex gap-3">
                    <div className={`w-1 rounded-full bg-gradient-to-b ${docTypeColors[doc.doc_type] || docTypeColors.other}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start gap-2">
                        <h3 className="text-sm font-medium text-gray-900 group-hover:text-indigo-600 transition-colors line-clamp-2">
                          {doc.title}
                        </h3>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <span className="flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-100 text-indigo-700 border border-indigo-200">
                          {docTypeLabels[doc.doc_type] || doc.doc_type}
                        </span>
                      </div>
                      <div className="mt-3 flex items-center justify-between">
                        <div className="flex items-center gap-3 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            {doc.publish_date}
                          </span>
                          <span
                            className={`flex items-center gap-1 ${
                              doc.is_processed ? "text-emerald-600" : "text-gray-400"
                            }`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${doc.is_processed ? "bg-emerald-500 animate-pulse" : "bg-gray-300"}`} />
                            {doc.is_processed ? "分析済" : "未分析"}
                          </span>
                        </div>
                        {doc.source_url && (
                          <a
                            href={doc.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-indigo-600 hover:bg-indigo-50 transition-colors"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            PDF
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
