import Link from "next/link";
import Image from "next/image";

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="text-center">
        {/* イリスキャラクター */}
        <div className="relative inline-block mb-8">
          <div className="absolute inset-0 bg-indigo-200/50 rounded-full blur-3xl scale-150" />
          <div className="relative w-40 h-40 rounded-full overflow-hidden ring-4 ring-indigo-200 ring-offset-4 mx-auto">
            <Image
              src="/images/iris/iris-normal.png"
              alt="イリス"
              width={160}
              height={160}
              className="object-cover"
            />
          </div>
        </div>

        {/* エラーコード */}
        <div className="relative mb-6">
          <span className="text-8xl md:text-9xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-500">
            404
          </span>
        </div>

        {/* メッセージ */}
        <div className="glass rounded-2xl p-6 max-w-md mx-auto mb-8">
          <h1 className="text-xl font-bold text-gray-900 mb-3">
            ページが見つかりません
          </h1>
          <p className="text-gray-600 leading-relaxed">
            「あれ...？このデータ、存在しないみたいです。
            <br />
            URLを確認するか、トップページから探してみてください。」
          </p>
        </div>

        {/* ナビゲーション */}
        <div className="flex flex-wrap justify-center gap-4">
          <Link href="/" className="btn-iris">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            トップページへ
          </Link>
          <Link href="/stocks" className="btn-iris-outline">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            銘柄を探す
          </Link>
        </div>

        {/* おすすめリンク */}
        <div className="mt-12 pt-8 border-t border-indigo-100">
          <p className="text-sm text-gray-500 mb-4">「こちらのページはいかがですか？」</p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/documents" className="text-sm text-indigo-600 hover:text-indigo-800 hover:underline">
              最新IR資料
            </Link>
            <span className="text-gray-300">|</span>
            <Link href="/glossary" className="text-sm text-indigo-600 hover:text-indigo-800 hover:underline">
              用語集
            </Link>
            <span className="text-gray-300">|</span>
            <Link href="/faq" className="text-sm text-indigo-600 hover:text-indigo-800 hover:underline">
              よくある質問
            </Link>
            <span className="text-gray-300">|</span>
            <Link href="/sectors" className="text-sm text-indigo-600 hover:text-indigo-800 hover:underline">
              業種一覧
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
