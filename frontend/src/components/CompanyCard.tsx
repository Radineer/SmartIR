import Link from "next/link";
import type { Company } from "@/types";

interface CompanyCardProps {
  company: Company;
}

export default function CompanyCard({ company }: CompanyCardProps) {
  return (
    <Link href={`/companies/${company.id}`}>
      <div className="holo-card p-6 cursor-pointer group">
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              {/* Ticker Code Badge */}
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
                {company.ticker_code}
              </span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mt-2 group-hover:text-indigo-600 transition-colors">
              {company.name}
            </h3>
          </div>
          {company.sector && (
            <span className="iris-badge">
              {company.sector}
            </span>
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
  );
}
