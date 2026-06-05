"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import DocumentCard from "@/components/DocumentCard";
import type { Company, Document } from "@/types";

export default function CompanyDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [company, setCompany] = useState<Company | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.getCompany(id),
      api.getDocuments(id, 365),
    ])
      .then(([companyData, docsData]) => {
        setCompany(companyData);
        setDocuments(docsData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!company) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-center text-red-600">{error || "企業が見つかりません"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* パンくず */}
      <nav className="text-sm mb-4">
        <Link href="/companies" className="text-blue-600 hover:underline">
          企業一覧
        </Link>
        <span className="mx-2 text-gray-400">/</span>
        <span className="text-gray-600">{company.name}</span>
      </nav>

      {/* 企業情報 */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{company.name}</h1>
            <p className="text-gray-500 mt-1">{company.ticker_code}</p>
          </div>
          <div className="flex space-x-2">
            {company.sector && (
              <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                {company.sector}
              </span>
            )}
            {company.industry && (
              <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                {company.industry}
              </span>
            )}
          </div>
        </div>

        {company.description && (
          <p className="mt-4 text-gray-600">{company.description}</p>
        )}

        {company.website_url && (
          <a
            href={company.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-block text-blue-600 hover:underline text-sm"
          >
            公式サイト
          </a>
        )}
      </div>

      {/* ドキュメント一覧 */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">IR資料</h2>
        {documents.length === 0 ? (
          <p className="text-gray-500">IR資料がありません</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.map((doc) => (
              <DocumentCard key={doc.id} document={doc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
