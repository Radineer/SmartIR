"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import type { Company, Document } from "@/types";

interface SearchResult {
  companies: Company[];
  documents: Document[];
}

export default function GlobalSearch() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult>({ companies: [], documents: [] });
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // キーボードショートカット
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen(true);
      }
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // フォーカス
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // 外側クリックで閉じる
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  // 検索
  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults({ companies: [], documents: [] });
      return;
    }

    setLoading(true);
    try {
      const [companies, documents] = await Promise.all([
        api.getCompanies(0, 100),
        api.getDocuments(undefined, 30),
      ]);

      const searchLower = q.toLowerCase();
      const filteredCompanies = companies.filter(
        (c) =>
          c.name.toLowerCase().includes(searchLower) ||
          c.ticker_code.includes(q) ||
          c.sector?.toLowerCase().includes(searchLower)
      ).slice(0, 5);

      const filteredDocuments = documents.filter(
        (d) => d.title.toLowerCase().includes(searchLower)
      ).slice(0, 5);

      setResults({ companies: filteredCompanies, documents: filteredDocuments });
    } catch (err) {
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      search(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, search]);

  const handleSelect = () => {
    setIsOpen(false);
    setQuery("");
  };

  return (
    <>
      {/* 検索ボタン */}
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-indigo-50 border border-gray-200 hover:border-indigo-200 transition-colors text-sm text-gray-500"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <span className="hidden sm:inline">検索</span>
        <kbd className="hidden sm:inline px-1.5 py-0.5 text-xs bg-white rounded border border-gray-300 font-mono">
          ⌘K
        </kbd>
      </button>

      {/* モーダル */}
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-20 px-4">
          {/* オーバーレイ */}
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />

          {/* 検索コンテナ */}
          <div
            ref={containerRef}
            className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden border border-indigo-100"
          >
            {/* 検索入力 */}
            <div className="flex items-center gap-3 px-4 py-4 border-b border-indigo-100">
              <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="銘柄名・証券コード・IR資料を検索..."
                className="flex-1 text-lg outline-none bg-transparent placeholder-gray-400"
              />
              {loading && (
                <svg className="w-5 h-5 text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* 検索結果 */}
            <div className="max-h-[60vh] overflow-y-auto">
              {!query ? (
                <div className="p-8 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full overflow-hidden ring-2 ring-indigo-100 opacity-50">
                    <Image
                      src="/images/iris/iris-normal.png"
                      alt="イリス"
                      width={64}
                      height={64}
                      className="object-cover"
                    />
                  </div>
                  <p className="text-gray-400 text-sm">
                    「検索キーワードを入力してください」
                  </p>
                </div>
              ) : results.companies.length === 0 && results.documents.length === 0 ? (
                <div className="p-8 text-center">
                  <p className="text-gray-400 text-sm">
                    「{query}」に一致する結果が見つかりません
                  </p>
                </div>
              ) : (
                <div className="py-2">
                  {/* 銘柄結果 */}
                  {results.companies.length > 0 && (
                    <div>
                      <div className="px-4 py-2 text-xs font-medium text-gray-400 uppercase tracking-wider">
                        銘柄
                      </div>
                      {results.companies.map((company) => (
                        <Link
                          key={company.id}
                          href={`/stocks/${company.ticker_code}`}
                          onClick={handleSelect}
                          className="flex items-center gap-3 px-4 py-3 hover:bg-indigo-50 transition-colors"
                        >
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-100 to-cyan-100 flex items-center justify-center">
                            <span className="text-xs font-mono font-bold text-indigo-600">
                              {company.ticker_code.slice(-2)}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-900 truncate">
                              {company.name}
                            </div>
                            <div className="text-xs text-gray-500">
                              {company.ticker_code} {company.sector && `・ ${company.sector}`}
                            </div>
                          </div>
                          <svg className="w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </Link>
                      ))}
                    </div>
                  )}

                  {/* 資料結果 */}
                  {results.documents.length > 0 && (
                    <div>
                      <div className="px-4 py-2 text-xs font-medium text-gray-400 uppercase tracking-wider border-t border-gray-100 mt-2">
                        IR資料
                      </div>
                      {results.documents.map((doc) => (
                        <Link
                          key={doc.id}
                          href={`/documents/${doc.id}`}
                          onClick={handleSelect}
                          className="flex items-center gap-3 px-4 py-3 hover:bg-indigo-50 transition-colors"
                        >
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-100 to-green-100 flex items-center justify-center">
                            <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-900 truncate">
                              {doc.title}
                            </div>
                            <div className="text-xs text-gray-500">
                              {doc.publish_date}
                            </div>
                          </div>
                          <svg className="w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* フッター */}
            <div className="px-4 py-3 border-t border-indigo-100 bg-gray-50 flex items-center justify-between text-xs text-gray-400">
              <div className="flex items-center gap-2">
                <kbd className="px-1.5 py-0.5 bg-white rounded border border-gray-200 font-mono">↵</kbd>
                <span>選択</span>
                <kbd className="px-1.5 py-0.5 bg-white rounded border border-gray-200 font-mono ml-2">ESC</kbd>
                <span>閉じる</span>
              </div>
              <span>⌘K でいつでも検索</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
