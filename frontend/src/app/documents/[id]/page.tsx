"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import AnalysisResultComponent from "@/components/AnalysisResult";
import type { Document, Company, AnalysisResult } from "@/types";

export default function DocumentDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [document, setDocument] = useState<Document | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getDocument(id)
      .then(async (doc) => {
        setDocument(doc);
        const comp = await api.getCompany(doc.company_id);
        setCompany(comp);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setError("");
    try {
      const result = await api.analyzeDocument(id);
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析に失敗しました");
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-center text-red-600">{error || "ドキュメントが見つかりません"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* パンくず */}
      <nav className="text-sm mb-4">
        <Link href="/documents" className="text-blue-600 hover:underline">
          ドキュメント
        </Link>
        <span className="mx-2 text-gray-400">/</span>
        <span className="text-gray-600">{document.title}</span>
      </nav>

      {/* ヘッダー */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h1 className="text-xl font-bold text-gray-900 mb-2">{document.title}</h1>
        <div className="flex items-center space-x-4 text-sm text-gray-500">
          {company && (
            <Link
              href={`/companies/${company.id}`}
              className="text-blue-600 hover:underline"
            >
              {company.name} ({company.ticker_code})
            </Link>
          )}
          <span>{document.publish_date}</span>
          <span
            className={`px-2 py-0.5 rounded text-xs ${
              document.is_processed
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {document.is_processed ? "分析済み" : "未分析"}
          </span>
        </div>
        <div className="mt-4 flex space-x-3">
          <a
            href={document.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition"
          >
            PDFを開く
          </a>
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {analyzing ? "分析中..." : "AIで分析"}
          </button>
        </div>
      </div>

      {/* エラー表示 */}
      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6 text-sm">
          {error}
        </div>
      )}

      {/* 分析結果 */}
      {analysis && <AnalysisResultComponent result={analysis} />}
    </div>
  );
}
