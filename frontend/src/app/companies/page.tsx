"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import type { Company } from "@/types";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.getCompanies(0, 100)
      .then(setCompanies)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filteredCompanies = companies.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.ticker_code.includes(search) ||
      c.sector?.toLowerCase().includes(search.toLowerCase())
  );

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
          <p className="text-indigo-600 text-sm">企業データを読み込んでいます...</p>
        </div>
      </div>
    );
  }

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
            <h1 className="section-title text-2xl md:text-3xl">企業一覧</h1>
            <p className="text-gray-600 mt-3">
              「登録されている企業の一覧です。検索で絞り込むこともできますよ。」
            </p>
          </div>
          <div className="flex-shrink-0 w-full md:w-72">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <input
                type="text"
                placeholder="企業名・コード・業種で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>
        </div>
      </div>

      {filteredCompanies.length === 0 ? (
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
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {search ? "該当する企業が見つかりません" : "企業データがありません"}
          </h3>
          <p className="text-gray-500 mb-4">
            「{search ? "検索条件を変えてみてください" : "データの準備中です..."}」
          </p>
          {search && (
            <button
              onClick={() => setSearch("")}
              className="btn-iris"
            >
              検索をクリア
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="mb-4 text-sm text-gray-500">
            {filteredCompanies.length}社
            {search && ` (「${search}」で検索)`}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCompanies.map((company) => (
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
                  {company.description && (
                    <p className="mt-3 text-sm text-gray-600 line-clamp-2">
                      {company.description}
                    </p>
                  )}
                  {company.industry && (
                    <div className="mt-3 pt-3 border-t border-indigo-100/50">
                      <p className="text-xs text-gray-500 flex items-center gap-1">
                        <svg className="w-3 h-3 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                        {company.industry}
                      </p>
                    </div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
