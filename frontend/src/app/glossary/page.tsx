import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { BreadcrumbData, StructuredData } from "@/components/StructuredData";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://smartir-web-silk.vercel.app";

export const metadata: Metadata = {
  title: "IR・投資用語集 | イリスのIR分析",
  description:
    "IR資料や株式投資でよく使われる用語をAIアナリスト「イリス」が解説。決算短信、有価証券報告書、PER、PBR、ROEなどの基本用語から専門用語まで網羅。",
  keywords: [
    "IR用語",
    "投資用語",
    "決算用語",
    "株式用語",
    "PER",
    "PBR",
    "ROE",
    "決算短信",
    "有価証券報告書",
    "用語集",
    "イリス",
  ],
  alternates: {
    canonical: `${SITE_URL}/glossary`,
  },
  openGraph: {
    title: "IR・投資用語集 | イリスのIR分析",
    description: "IR資料や株式投資でよく使われる用語をわかりやすく解説。",
    type: "website",
    url: `${SITE_URL}/glossary`,
  },
};

interface GlossaryTerm {
  term: string;
  reading?: string;
  english?: string;
  description: string;
  relatedTerms?: string[];
}

interface GlossaryCategory {
  title: string;
  icon: string;
  terms: GlossaryTerm[];
}

const glossaryData: GlossaryCategory[] = [
  {
    title: "IR・開示書類",
    icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    terms: [
      {
        term: "IR",
        english: "Investor Relations",
        description:
          "企業が株主や投資家に対して行う広報活動のこと。財務状況、経営戦略、業績見通しなどの情報を適切に開示し、企業価値を正しく理解してもらうための活動。",
        relatedTerms: ["有価証券報告書", "決算短信", "適時開示"],
      },
      {
        term: "決算短信",
        reading: "けっさんたんしん",
        description:
          "上場企業が決算期末後45日以内に発表する速報的な決算報告書。売上高、営業利益、経常利益、純利益などの主要数値と業績概況が記載される。四半期ごとに発表。",
        relatedTerms: ["有価証券報告書", "四半期報告書"],
      },
      {
        term: "有価証券報告書",
        reading: "ゆうかしょうけんほうこくしょ",
        description:
          "金融商品取引法に基づき上場企業が年1回提出する法定開示書類。事業内容、財務状況、リスク情報、役員情報などを詳細に記載。略して「有報」とも呼ばれる。",
        relatedTerms: ["決算短信", "四半期報告書", "適時開示"],
      },
      {
        term: "四半期報告書",
        reading: "しはんきほうこくしょ",
        description:
          "四半期（3ヶ月）ごとの業績を報告する開示書類。第1〜第3四半期に提出され、決算短信よりも詳細な情報が含まれる。",
        relatedTerms: ["決算短信", "有価証券報告書"],
      },
      {
        term: "適時開示",
        reading: "てきじかいじ",
        english: "Timely Disclosure",
        description:
          "投資判断に重要な影響を与える情報を、発生次第すみやかに開示すること。業績予想の修正、M&A、役員人事などが該当。",
        relatedTerms: ["IR", "重要事実"],
      },
    ],
  },
  {
    title: "財務指標",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    terms: [
      {
        term: "PER",
        english: "Price Earnings Ratio",
        description:
          "株価収益率。株価÷1株当たり純利益で算出。株価が1株利益の何倍かを示し、株価の割安・割高を判断する指標。業界平均との比較が重要。",
        relatedTerms: ["PBR", "EPS", "配当利回り"],
      },
      {
        term: "PBR",
        english: "Price Book-value Ratio",
        description:
          "株価純資産倍率。株価÷1株当たり純資産で算出。1倍を下回ると企業の解散価値を下回っていることを意味し、割安と判断されることが多い。",
        relatedTerms: ["PER", "BPS", "ROE"],
      },
      {
        term: "ROE",
        english: "Return On Equity",
        description:
          "自己資本利益率。純利益÷自己資本×100で算出。株主が投資した資本に対してどれだけ効率よく利益を上げているかを示す。一般的に10%以上が優良とされる。",
        relatedTerms: ["ROA", "PBR", "自己資本比率"],
      },
      {
        term: "ROA",
        english: "Return On Assets",
        description:
          "総資産利益率。純利益÷総資産×100で算出。企業が保有する全ての資産を使ってどれだけ効率よく利益を上げているかを示す指標。",
        relatedTerms: ["ROE", "総資産回転率"],
      },
      {
        term: "EPS",
        english: "Earnings Per Share",
        description:
          "1株当たり純利益。純利益÷発行済株式数で算出。企業の収益力を1株単位で表した指標で、PERの算出にも使用される。",
        relatedTerms: ["PER", "BPS", "配当性向"],
      },
      {
        term: "BPS",
        english: "Book-value Per Share",
        description:
          "1株当たり純資産。純資産÷発行済株式数で算出。企業を解散した場合に株主に分配される1株あたりの金額の目安となる。",
        relatedTerms: ["PBR", "EPS", "純資産"],
      },
    ],
  },
  {
    title: "財務諸表",
    icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    terms: [
      {
        term: "貸借対照表",
        reading: "たいしゃくたいしょうひょう",
        english: "Balance Sheet",
        description:
          "決算日時点での企業の財政状態を表す財務諸表。資産、負債、純資産の3つで構成され、企業が持っているもの（資産）と、その調達源泉（負債・純資産）を示す。",
        relatedTerms: ["損益計算書", "キャッシュフロー計算書"],
      },
      {
        term: "損益計算書",
        reading: "そんえきけいさんしょ",
        english: "Income Statement / P&L",
        description:
          "一定期間の経営成績を表す財務諸表。売上高から各種費用を差し引いて、最終的な純利益を算出する。収益性を判断する基本資料。",
        relatedTerms: ["貸借対照表", "営業利益", "経常利益"],
      },
      {
        term: "キャッシュフロー計算書",
        reading: "キャッシュフローけいさんしょ",
        english: "Cash Flow Statement",
        description:
          "一定期間の現金の流れを表す財務諸表。営業活動、投資活動、財務活動の3つに区分され、企業の資金繰りの健全性を判断できる。",
        relatedTerms: ["営業CF", "投資CF", "財務CF"],
      },
      {
        term: "営業利益",
        reading: "えいぎょうりえき",
        english: "Operating Income",
        description:
          "売上高から売上原価と販売費及び一般管理費を差し引いた利益。本業での稼ぐ力を示す重要な指標。",
        relatedTerms: ["経常利益", "純利益", "営業利益率"],
      },
      {
        term: "経常利益",
        reading: "けいじょうりえき",
        english: "Ordinary Income",
        description:
          "営業利益に営業外収益を加え、営業外費用を差し引いた利益。本業以外の金融活動なども含めた、通常の事業活動で得られる利益。",
        relatedTerms: ["営業利益", "純利益", "特別損益"],
      },
    ],
  },
  {
    title: "株式・配当",
    icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    terms: [
      {
        term: "配当",
        reading: "はいとう",
        english: "Dividend",
        description:
          "企業が稼いだ利益の一部を株主に分配すること。1株あたりの金額で表され、年1〜2回支払われることが多い。",
        relatedTerms: ["配当利回り", "配当性向", "増配"],
      },
      {
        term: "配当利回り",
        reading: "はいとうりまわり",
        english: "Dividend Yield",
        description:
          "年間配当金÷株価×100で算出。株価に対して何%の配当がもらえるかを示す。高配当株の目安は3%以上とされることが多い。",
        relatedTerms: ["配当", "PER", "配当性向"],
      },
      {
        term: "配当性向",
        reading: "はいとうせいこう",
        english: "Payout Ratio",
        description:
          "年間配当金÷純利益×100で算出。利益のうちどれだけを配当に回しているかを示す。30〜50%程度が一般的。",
        relatedTerms: ["配当", "EPS", "内部留保"],
      },
      {
        term: "株式分割",
        reading: "かぶしきぶんかつ",
        english: "Stock Split",
        description:
          "1株を複数株に分割すること。株価が下がり流動性が高まるが、企業価値自体は変わらない。投資家の売買がしやすくなる効果がある。",
        relatedTerms: ["株式併合", "発行済株式数"],
      },
      {
        term: "自社株買い",
        reading: "じしゃかぶがい",
        english: "Stock Buyback",
        description:
          "企業が自社の株式を市場から買い戻すこと。発行済株式数が減少し、1株当たりの価値が高まる。株主還元の一つの方法。",
        relatedTerms: ["配当", "EPS", "株主還元"],
      },
    ],
  },
];

// DefinedTermList構造化データ
function GlossaryStructuredData() {
  const definedTerms = glossaryData.flatMap((category) =>
    category.terms.map((term) => ({
      "@type": "DefinedTerm",
      name: term.term,
      description: term.description,
      ...(term.english && { alternateName: term.english }),
    }))
  );

  const data = {
    "@context": "https://schema.org",
    "@type": "DefinedTermSet",
    name: "IR・投資用語集",
    description: "IR資料や株式投資でよく使われる用語の解説集",
    url: `${SITE_URL}/glossary`,
    hasDefinedTerm: definedTerms,
  };

  return <StructuredData data={data} />;
}

export default function GlossaryPage() {
  const breadcrumbs = [
    { name: "ホーム", url: "/" },
    { name: "用語集", url: "/glossary" },
  ];

  return (
    <>
      <BreadcrumbData items={breadcrumbs} />
      <GlossaryStructuredData />

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* パンくずリスト */}
        <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link href="/" className="hover:text-indigo-600 transition-colors">
            ホーム
          </Link>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-gray-900 font-medium">用語集</span>
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
              <h1 className="section-title text-2xl md:text-3xl">IR・投資用語集</h1>
              <p className="text-gray-600 mt-3">
                「IR資料でよく使われる用語をまとめました。わからない言葉があれば、ここで確認してみてくださいね。」
              </p>
            </div>
          </div>
        </header>

        {/* 目次 */}
        <nav className="holo-card p-5 mb-8">
          <h2 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
            </svg>
            カテゴリー
          </h2>
          <div className="flex flex-wrap gap-2">
            {glossaryData.map((category, index) => (
              <a
                key={index}
                href={`#category-${index}`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-full text-sm hover:bg-indigo-100 transition-colors border border-indigo-100"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={category.icon} />
                </svg>
                {category.title}
              </a>
            ))}
          </div>
        </nav>

        {/* 用語リスト */}
        {glossaryData.map((category, categoryIndex) => (
          <section
            key={categoryIndex}
            id={`category-${categoryIndex}`}
            className="mb-10"
          >
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
            <div className="space-y-4">
              {category.terms.map((term, termIndex) => (
                <article
                  key={termIndex}
                  id={term.term}
                  className="holo-card p-5"
                >
                  <header className="mb-3">
                    <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                      {term.term}
                      {term.reading && (
                        <span className="text-sm font-normal text-gray-500">
                          （{term.reading}）
                        </span>
                      )}
                    </h3>
                    {term.english && (
                      <p className="text-sm text-indigo-600 mt-1">{term.english}</p>
                    )}
                  </header>
                  <p className="text-gray-700 leading-relaxed">
                    {term.description}
                  </p>
                  {term.relatedTerms && term.relatedTerms.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-indigo-100/50">
                      <span className="text-sm text-gray-500 mr-2">関連用語:</span>
                      <div className="inline-flex flex-wrap gap-2 mt-1">
                        {term.relatedTerms.map((related, i) => (
                          <a
                            key={i}
                            href={`#${related}`}
                            className="text-sm text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded hover:bg-indigo-100 transition-colors"
                          >
                            {related}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        ))}

        {/* CTA */}
        <section className="holo-card p-6 mt-8">
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
              <h2 className="text-lg font-bold text-gray-900 mb-2">
                実際のIR資料で確認してみましょう
              </h2>
              <p className="text-gray-600 mb-4">
                「用語を学んだら、実際のIR資料でどのように使われているか見てみましょう。私が解説付きで分析していますよ。」
              </p>
              <Link
                href="/stocks"
                className="btn-iris inline-flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                銘柄一覧を見る
              </Link>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
