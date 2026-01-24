import Link from "next/link";
import type { Document } from "@/types";

interface DocumentCardProps {
  document: Document;
  showCompany?: boolean;
}

const docTypeLabels: Record<string, string> = {
  financial_report: "決算短信",
  annual_report: "有価証券報告書",
  press_release: "プレスリリース",
  presentation: "説明資料",
  other: "その他",
};

const docTypeColors: Record<string, string> = {
  financial_report: "from-emerald-500 to-green-500",
  annual_report: "from-purple-500 to-indigo-500",
  press_release: "from-amber-500 to-orange-500",
  presentation: "from-cyan-500 to-blue-500",
  other: "from-gray-400 to-gray-500",
};

export default function DocumentCard({ document, showCompany }: DocumentCardProps) {
  return (
    <Link href={`/documents/${document.id}`}>
      <div className="holo-card p-4 cursor-pointer group">
        <div className="flex gap-3">
          {/* Type Indicator */}
          <div className={`w-1 rounded-full bg-gradient-to-b ${docTypeColors[document.doc_type] || docTypeColors.other}`} />

          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-start gap-2">
              <h3 className="text-sm font-medium text-gray-900 group-hover:text-indigo-600 transition-colors line-clamp-1">
                {document.title}
              </h3>
              <span className="flex-shrink-0 px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600">
                {docTypeLabels[document.doc_type] || document.doc_type}
              </span>
            </div>

            <div className="mt-2 flex items-center justify-between">
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  {document.publish_date}
                </span>

                {/* Analysis Status */}
                <span
                  className={`flex items-center gap-1 ${
                    document.is_processed ? "text-emerald-600" : "text-gray-400"
                  }`}
                >
                  {document.is_processed ? (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      分析済
                    </>
                  ) : (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                      未分析
                    </>
                  )}
                </span>
              </div>

              {/* PDF Link */}
              <a
                href={document.source_url}
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
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}
