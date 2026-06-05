import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import {
  getStockByTicker,
  getStockAnalysis,
  getAllTickerCodes,
  getRelatedStocks,
} from "@/lib/public-api";
import {
  BreadcrumbData,
  StockStructuredData,
  FAQData,
  ArticleStructuredData,
} from "@/components/StructuredData";
import type { Document, StockAnalysis, Company } from "@/types";
import { WatchlistButton } from "./WatchlistButton";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app";

interface PageProps {
  params: Promise<{ code: string }>;
}

// 動的レンダリング（ビルド時のAPI依存を回避）
export const dynamic = "force-dynamic";

// 静的パラメータを生成（SSG） - ビルド時はスキップ
export async function generateStaticParams() {
  // ビルド時はAPIが利用できないため空配列を返す
  // ページは初回アクセス時に生成される（ISR）
  return [];
}

// 動的メタデータ生成
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { code } = await params;

  try {
    const stock = await getStockByTicker(code);

    const title = `${stock.name}（${stock.ticker_code}）の決算・IR情報`;
    const description = `${stock.name}のIR資料をAIが分析。決算短信、有価証券報告書の要約と感情分析で投資判断をサポート。${stock.sector ? `業種: ${stock.sector}` : ""}`;
    const ogImageUrl = `${SITE_URL}/api/og?title=${encodeURIComponent(stock.name)}&subtitle=${encodeURIComponent(stock.description || "決算・IR情報をAIが分析")}&ticker=${stock.ticker_code}`;

    return {
      title,
      description,
      keywords: [
        stock.name,
        stock.ticker_code,
        stock.sector || "",
        stock.industry || "",
        "決算",
        "IR",
        "有価証券報告書",
        "決算短信",
        "AI分析",
      ].filter(Boolean),
      alternates: {
        canonical: `${SITE_URL}/stocks/${stock.ticker_code}`,
      },
      openGraph: {
        title: `${title} | AI-IR Insight`,
        description,
        type: "article",
        url: `${SITE_URL}/stocks/${stock.ticker_code}`,
        images: [
          {
            url: ogImageUrl,
            width: 1200,
            height: 630,
            alt: `${stock.name}のIR情報`,
          },
        ],
      },
      twitter: {
        card: "summary_large_image",
        title: `${title} | AI-IR Insight`,
        description,
        images: [ogImageUrl],
      },
    };
  } catch {
    return {
      title: "銘柄が見つかりません | AI-IR Insight",
    };
  }
}

// 1時間ごとに再生成
export const revalidate = 3600;

function SentimentBar({
  label,
  value,
  type,
}: {
  label: string;
  value: number;
  type: "positive" | "negative" | "neutral";
}) {
  const percentage = Math.round(value * 100);
  const colorClass = {
    positive: "sentiment-positive",
    negative: "sentiment-negative",
    neutral: "sentiment-neutral",
  }[type];

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-24">{label}</span>
      <div className="flex-1 sentiment-bar">
        <div
          className={`sentiment-bar-fill ${colorClass}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm font-semibold text-gray-700 w-12 text-right">
        {percentage}%
      </span>
    </div>
  );
}

// イリスのコメント生成
function getIrisComment(positive: number, negative: number): { comment: string; expression: string } {
  if (positive > 0.5) {
    const comments = [
      "この決算、なかなか良い数字ですね。詳しく見ていきましょう。",
      "ポジティブな要素が多いです。成長が期待できそうですね。",
      "データを見る限り、堅調な業績と言えそうです。",
    ];
    return { comment: comments[Math.floor(Math.random() * comments.length)], expression: "smile" };
  } else if (negative > 0.3) {
    const comments = [
      "少し気になる点がありますね...一緒に確認しましょう。",
      "慎重に分析する必要がありそうです。",
      "いくつか注意すべきポイントがあります。",
    ];
    return { comment: comments[Math.floor(Math.random() * comments.length)], expression: "thinking" };
  } else {
    const comments = [
      "データを整理しました。確認していきましょう。",
      "安定した数字が並んでいますね。",
      "特筆すべき変化は少ないですが、詳細を見てみましょう。",
    ];
    return { comment: comments[Math.floor(Math.random() * comments.length)], expression: "normal" };
  }
}

function AnalysisSection({ analysis }: { analysis: StockAnalysis }) {
  const irisData = getIrisComment(analysis.sentiment_positive, analysis.sentiment_negative);

  return (
    <div className="holo-card p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="section-title">AI分析結果</h2>
        <span className="iris-badge">
          {new Date(analysis.analyzed_at).toLocaleDateString("ja-JP")}更新
        </span>
      </div>

      {/* イリスのコメント */}
      <div className="mb-6 p-4 bg-gradient-to-r from-indigo-50 via-purple-50 to-cyan-50 rounded-xl border border-indigo-100">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-14 h-14 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
            <Image
              src="/images/iris/iris-analysis.png"
              alt="イリス"
              width={56}
              height={56}
              className="object-cover"
            />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-bold text-indigo-700">イリス</span>
              <span className="text-xs text-indigo-500 bg-white px-2 py-0.5 rounded-full border border-indigo-100">分析モード</span>
            </div>
            <p className="text-gray-700 leading-relaxed">「{irisData.comment}」</p>
          </div>
        </div>
      </div>

      <div className="mb-6 p-4 glass rounded-lg">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-gray-600">{analysis.document_title}</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-gray-500">{analysis.publish_date}</span>
          </div>
        </div>
      </div>

      {/* 要約 */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span className="w-1 h-5 bg-gradient-to-b from-indigo-500 to-cyan-500 rounded-full" />
          AI要約
        </h3>
        <p className="text-gray-700 leading-relaxed bg-gray-50/50 p-4 rounded-lg">{analysis.summary}</p>
      </div>

      {/* センチメント分析 */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-gradient-to-b from-indigo-500 to-cyan-500 rounded-full" />
          センチメント分析
        </h3>
        <div className="space-y-3 p-4 bg-gray-50/50 rounded-lg">
          <SentimentBar
            label="ポジティブ"
            value={analysis.sentiment_positive}
            type="positive"
          />
          <SentimentBar
            label="ネガティブ"
            value={analysis.sentiment_negative}
            type="negative"
          />
          <SentimentBar
            label="ニュートラル"
            value={analysis.sentiment_neutral}
            type="neutral"
          />
        </div>
      </div>

      {/* キーポイント */}
      {analysis.key_points.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="w-1 h-5 bg-gradient-to-b from-indigo-500 to-cyan-500 rounded-full" />
            重要ポイント
          </h3>
          <ul className="space-y-3">
            {analysis.key_points.map((point, index) => (
              <li key={index} className="flex items-start gap-3 p-3 bg-gray-50/50 rounded-lg">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-cyan-500 text-white text-xs flex items-center justify-center font-bold">
                  {index + 1}
                </span>
                <span className="text-gray-700">{point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function DocumentList({ documents }: { documents: Document[] }) {
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

  return (
    <div className="holo-card p-6">
      <h2 className="section-title mb-4">最新のIR資料</h2>
      {documents.length > 0 ? (
        <div className="space-y-3">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 p-3 glass rounded-lg group hover:bg-indigo-50/50 transition-colors"
            >
              <div className={`w-1 h-12 rounded-full bg-gradient-to-b ${docTypeColors[doc.doc_type] || docTypeColors.other}`} />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 group-hover:text-indigo-600 transition-colors truncate">{doc.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full border border-indigo-200">
                    {docTypeLabels[doc.doc_type] || doc.doc_type}
                  </span>
                  <time className="text-xs text-gray-500" dateTime={doc.publish_date}>
                    {doc.publish_date}
                  </time>
                </div>
              </div>
              {doc.source_url && (
                <a
                  href={doc.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium text-indigo-600 hover:bg-indigo-100 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  PDF
                </a>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-indigo-100 mb-3">
            <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-gray-500">IR資料がまだありません</p>
        </div>
      )}
    </div>
  );
}

function RelatedStocks({ stocks, currentSector }: { stocks: Company[]; currentSector: string }) {
  if (stocks.length === 0) return null;

  return (
    <section className="holo-card p-6 mt-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title">
          同じ業種の銘柄
        </h2>
        <span className="iris-badge">{currentSector}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {stocks.map((stock) => (
          <Link
            key={stock.id}
            href={`/stocks/${stock.ticker_code}`}
            className="block p-3 glass rounded-lg hover:bg-indigo-50/50 transition-all group"
          >
            <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
              {stock.ticker_code}
            </span>
            <p className="font-medium text-gray-900 text-sm mt-2 group-hover:text-indigo-600 transition-colors">{stock.name}</p>
            {stock.industry && (
              <p className="text-xs text-gray-500 mt-1 truncate">{stock.industry}</p>
            )}
          </Link>
        ))}
      </div>
      <Link
        href={`/sectors/${encodeURIComponent(currentSector)}`}
        className="inline-flex items-center gap-1 mt-4 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
      >
        {currentSector}の銘柄をすべて見る
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </Link>
    </section>
  );
}

export default async function StockDetailPage({ params }: PageProps) {
  const { code } = await params;

  let stock;
  try {
    stock = await getStockByTicker(code);
  } catch {
    notFound();
  }

  const analysis = await getStockAnalysis(code);

  // 関連銘柄（同じ業種）
  const relatedStocksData = stock.sector
    ? await getRelatedStocks(stock.sector, stock.ticker_code, 6)
    : { stocks: [], total: 0 };

  // パンくずリスト
  const breadcrumbs = [
    { name: "ホーム", url: "/" },
    { name: "銘柄一覧", url: "/stocks" },
    { name: stock.name, url: `/stocks/${stock.ticker_code}` },
  ];

  // FAQ構造化データ（SEO強化）
  const faqItems = [
    {
      question: `${stock.name}（${stock.ticker_code}）の決算情報は？`,
      answer: analysis
        ? analysis.summary
        : `${stock.name}のIR資料を分析中です。最新の決算情報が公開され次第、AIが自動分析を行います。`,
    },
    {
      question: `${stock.name}の業種は？`,
      answer: `${stock.name}は${stock.sector || "未分類"}に属する企業です。${stock.industry ? `業界は${stock.industry}です。` : ""}`,
    },
    {
      question: `${stock.name}のIR資料はどこで見れる？`,
      answer: `${stock.name}のIR資料は当サイトで${stock.document_count}件公開されています。決算短信、有価証券報告書などをAIが分析し、要約とセンチメント分析を提供しています。`,
    },
  ];

  return (
    <>
      <StockStructuredData
        tickerCode={stock.ticker_code}
        name={stock.name}
        description={stock.description || undefined}
        sector={stock.sector || undefined}
        industry={stock.industry || undefined}
      />
      <BreadcrumbData items={breadcrumbs} />
      <FAQData items={faqItems} />
      {analysis && (
        <ArticleStructuredData
          title={`${stock.name}のAI分析レポート`}
          description={analysis.summary}
          publishDate={analysis.publish_date}
          modifiedDate={new Date(analysis.analyzed_at).toISOString().split("T")[0]}
          url={`/stocks/${stock.ticker_code}`}
        />
      )}

      <div className="max-w-4xl mx-auto px-4 py-8">
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
          <span className="text-gray-900 font-medium">{stock.name}</span>
        </nav>

        {/* ヘッダー */}
        <div className="glass rounded-2xl p-6 mb-6">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-16 h-16 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
                <Image
                  src="/images/iris/iris-normal.png"
                  alt="イリス"
                  width={64}
                  height={64}
                  className="object-cover"
                />
              </div>
              <div>
                <span className="inline-flex px-3 py-1 rounded-full text-sm font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
                  {stock.ticker_code}
                </span>
                <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mt-2">
                  {stock.name}
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <WatchlistButton tickerCode={stock.ticker_code} stockName={stock.name} />
              {stock.website_url && (
                <a
                  href={stock.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-iris-outline text-sm inline-flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  公式サイト
                </a>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mt-4">
            {stock.sector && (
              <Link
                href={`/sectors/${encodeURIComponent(stock.sector)}`}
                className="iris-badge hover:bg-indigo-100 transition-colors"
              >
                {stock.sector}
              </Link>
            )}
            {stock.industry && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600 border border-gray-200">
                {stock.industry}
              </span>
            )}
          </div>

          {stock.description && (
            <p className="text-gray-600 mt-4 leading-relaxed">{stock.description}</p>
          )}

          <div className="mt-4 pt-4 border-t border-indigo-100/50 flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              IR資料 <span className="font-semibold text-indigo-600">{stock.document_count}</span> 件
            </div>
          </div>
        </div>

        {/* AI分析結果 */}
        {analysis && <AnalysisSection analysis={analysis} />}

        {/* 分析結果がない場合 */}
        {!analysis && (
          <div className="holo-card p-6 mb-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-14 h-14 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
                <Image
                  src="/images/iris/iris-normal.png"
                  alt="イリス"
                  width={56}
                  height={56}
                  className="object-cover"
                />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-bold text-indigo-700">イリス</span>
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">待機中</span>
                </div>
                <p className="text-gray-600 leading-relaxed">
                  「この銘柄の分析はまだ準備中です...IR資料が届き次第、分析を開始しますね。」
                </p>
                <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  分析待機中
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 最新のIR資料 */}
        <div className="mt-6">
          <DocumentList documents={stock.recent_documents} />
        </div>

        {/* 関連銘柄（内部リンク強化） */}
        {stock.sector && (
          <RelatedStocks
            stocks={relatedStocksData.stocks}
            currentSector={stock.sector}
          />
        )}
      </div>
    </>
  );
}
