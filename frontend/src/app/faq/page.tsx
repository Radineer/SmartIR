import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { BreadcrumbData, FAQData } from "@/components/StructuredData";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app";

export const metadata: Metadata = {
  title: "よくある質問（FAQ） | イリスのIR分析",
  description:
    "イリスのIR分析に関するよくある質問と回答。IR資料の分析方法、利用料金、データの更新頻度などについてAIアナリスト「イリス」が解説します。",
  keywords: [
    "FAQ",
    "よくある質問",
    "IR分析",
    "使い方",
    "料金",
    "イリス",
    "AIアナリスト",
  ],
  alternates: {
    canonical: `${SITE_URL}/faq`,
  },
  openGraph: {
    title: "よくある質問（FAQ） | イリスのIR分析",
    description: "イリスのIR分析の使い方や機能についてよくある質問をまとめています。",
    type: "website",
    url: `${SITE_URL}/faq`,
  },
};

const faqCategories = [
  {
    title: "サービスについて",
    icon: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    faqs: [
      {
        question: "「イリスのIR分析」とは何ですか？",
        answer:
          "「イリスのIR分析」は、2050年から来たAIアナリスト「イリス」が上場企業のIR資料（決算短信、有価証券報告書など）を自動分析するプラットフォームです。企業の決算情報を要約し、センチメント分析（ポジティブ・ネガティブ・ニュートラルの割合）を提供することで、投資判断をサポートします。",
      },
      {
        question: "イリスとは誰ですか？",
        answer:
          "イリスは2050年の未来から来たAIアナリストです。銀色のショートボブヘアと、データ分析時に光るサイバーな瞳が特徴。普段はクールですが、面白いデータを見つけると少し興奮する一面も。「データは嘘をつきませんから」が口癖です。",
      },
      {
        question: "どのような企業のIR資料を分析できますか？",
        answer:
          "東証プライム、スタンダード、グロースに上場している日本企業のIR資料を対象としています。決算短信、有価証券報告書、四半期報告書、決算説明会資料などを分析しています。",
      },
    ],
  },
  {
    title: "IR分析について",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    faqs: [
      {
        question: "決算短信とは何ですか？",
        answer:
          "決算短信は、企業が決算期末後45日以内に発表する速報的な決算報告書です。売上高、営業利益、経常利益、純利益などの主要な財務数値と、業績の概況が記載されています。四半期ごとに発表されます。",
      },
      {
        question: "有価証券報告書とは何ですか？",
        answer:
          "有価証券報告書は、金融商品取引法に基づいて上場企業が年1回提出する法定開示書類です。企業の事業内容、財務状況、リスク情報、役員情報などが詳細に記載されており、決算短信よりも包括的な情報が含まれています。",
      },
      {
        question: "センチメント分析とは何ですか？",
        answer:
          "センチメント分析は、IR資料の文章からポジティブ（好材料）、ネガティブ（悪材料）、ニュートラル（中立）の感情傾向を数値化したものです。業績見通しや経営者のコメントなどから、企業の姿勢や市場の期待を読み取る参考になります。",
      },
      {
        question: "AIの分析精度はどの程度ですか？",
        answer:
          "AIによる分析は参考情報としてご利用ください。財務データの抽出は高い精度で行われますが、要約やセンチメント分析は解釈の余地があります。投資判断の際は、必ず原本のIR資料も確認することをお勧めします。",
      },
    ],
  },
  {
    title: "データと更新について",
    icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
    faqs: [
      {
        question: "IR資料はどのくらいの頻度で更新されますか？",
        answer:
          "IR資料は企業の発表後、通常1〜2日以内にシステムに取り込まれ、AI分析が行われます。決算発表シーズン（4月〜5月、7月〜8月、10月〜11月、1月〜2月）は特に多くの資料が更新されます。",
      },
      {
        question: "過去のIR資料も閲覧できますか？",
        answer:
          "はい、過去の決算短信や有価証券報告書も閲覧可能です。企業によって保存期間は異なりますが、通常は過去3〜5年分のデータを保存しています。",
      },
      {
        question: "リアルタイムの株価情報は見られますか？",
        answer:
          "現在のバージョンではリアルタイムの株価情報は提供していません。IR資料の分析に特化したサービスとなっています。株価情報は証券会社や金融情報サイトをご利用ください。",
      },
    ],
  },
  {
    title: "利用について",
    icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
    faqs: [
      {
        question: "サービスは無料で利用できますか？",
        answer:
          "基本的な銘柄情報の閲覧とAI分析結果の確認は無料でご利用いただけます。より詳細な分析機能や、アラート機能などの高度な機能は、今後有料プランとして提供予定です。",
      },
      {
        question: "会員登録は必要ですか？",
        answer:
          "銘柄情報やAI分析結果の閲覧は会員登録なしでご利用いただけます。ウォッチリストやアラート機能など、パーソナライズされた機能を利用する場合は会員登録が必要です。",
      },
      {
        question: "スマートフォンでも利用できますか？",
        answer:
          "はい、スマートフォン、タブレット、PCなど、様々なデバイスからアクセスいただけます。レスポンシブデザインに対応しており、画面サイズに応じて最適な表示がされます。",
      },
    ],
  },
];

// 全FAQをフラット化（構造化データ用）
const allFaqs = faqCategories.flatMap((category) =>
  category.faqs.map((faq) => ({
    question: faq.question,
    answer: faq.answer,
  }))
);

export default function FAQPage() {
  const breadcrumbs = [
    { name: "ホーム", url: "/" },
    { name: "よくある質問", url: "/faq" },
  ];

  return (
    <>
      <BreadcrumbData items={breadcrumbs} />
      <FAQData items={allFaqs} />

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* パンくずリスト */}
        <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/" className="hover:text-indigo-600 transition-colors">
            ホーム
          </Link>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-gray-900 font-medium">よくある質問</span>
        </nav>

        {/* ヘッダー */}
        <header className="glass rounded-2xl p-6 mb-8">
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
              <h1 className="section-title text-2xl md:text-3xl">よくある質問（FAQ）</h1>
              <p className="text-gray-600 mt-3">
                「よく聞かれる質問をまとめました。気になることがあれば確認してみてください。」
              </p>
            </div>
          </div>
        </header>

        {/* FAQセクション */}
        {faqCategories.map((category, categoryIndex) => (
          <section key={categoryIndex} className="mb-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={category.icon} />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-gray-900">
                {category.title}
              </h2>
            </div>
            <div className="space-y-3">
              {category.faqs.map((faq, faqIndex) => (
                <details
                  key={faqIndex}
                  className="holo-card overflow-hidden group"
                >
                  <summary className="px-6 py-4 cursor-pointer font-medium text-gray-900 hover:text-indigo-600 list-none flex items-center justify-between transition-colors">
                    <span className="pr-4">{faq.question}</span>
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 group-open:bg-indigo-600 group-open:text-white transition-colors">
                      <svg className="w-4 h-4 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </span>
                  </summary>
                  <div className="px-6 py-4 bg-gradient-to-r from-indigo-50/50 via-purple-50/50 to-cyan-50/50 border-t border-indigo-100">
                    <p className="text-gray-700 leading-relaxed">{faq.answer}</p>
                  </div>
                </details>
              ))}
            </div>
          </section>
        ))}

        {/* CTA */}
        <section className="holo-card p-6 mt-8">
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
              <h2 className="text-lg font-bold text-gray-900 mb-2">
                お探しの回答が見つかりませんでしたか？
              </h2>
              <p className="text-gray-600 mb-4">
                「他にも質問があれば、お気軽にどうぞ。銘柄分析のことなら何でも聞いてくださいね。」
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/stocks"
                  className="btn-iris inline-flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  銘柄一覧を見る
                </Link>
                <Link
                  href="/"
                  className="btn-iris-outline inline-flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                  </svg>
                  トップページへ
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
