"use client";

import Link from "next/link";
import Image from "next/image";

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="relative mt-16 overflow-hidden">
      {/* Top Wave Decoration */}
      <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-transparent to-indigo-950/5" />

      {/* Main Footer */}
      <div className="bg-gradient-to-br from-indigo-950 via-indigo-900 to-slate-900 text-white">
        {/* Data Stream Animation */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-pulse" />
          <div className="absolute top-2/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-indigo-400 to-transparent animate-pulse delay-500" />
          <div className="absolute top-3/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-purple-400 to-transparent animate-pulse delay-1000" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {/* Brand Section */}
            <div className="md:col-span-2">
              <div className="flex items-center gap-3 mb-4">
                <div className="relative w-12 h-12 rounded-full overflow-hidden ring-2 ring-cyan-400/30">
                  <Image
                    src="/images/iris/iris-icon.png"
                    alt="イリス"
                    width={48}
                    height={48}
                    className="object-cover"
                  />
                </div>
                <div>
                  <h3 className="text-xl font-bold bg-gradient-to-r from-white to-cyan-200 bg-clip-text text-transparent">
                    イリスのIR分析
                  </h3>
                  <p className="text-xs text-indigo-300">AI Analyst from 2050</p>
                </div>
              </div>
              <p className="text-indigo-200 text-sm leading-relaxed mb-4 max-w-md">
                2050年から来たAIアナリスト「イリス」が、上場企業のIR資料を自動分析。
                決算短信、有価証券報告書の要約・センチメント分析で投資判断をサポートします。
              </p>

              {/* Iris Comment */}
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-800/50 border border-indigo-700/50">
                <span className="text-cyan-400 text-sm">「</span>
                <span className="text-indigo-200 text-sm italic">
                  データは嘘をつきません。でも解釈には注意が必要です。
                </span>
                <span className="text-cyan-400 text-sm">」</span>
              </div>
            </div>

            {/* Navigation */}
            <div>
              <h4 className="font-semibold text-white mb-4 flex items-center gap-2">
                <span className="w-1 h-4 bg-gradient-to-b from-indigo-400 to-cyan-400 rounded-full" />
                ナビゲーション
              </h4>
              <ul className="space-y-2">
                <FooterLink href="/">ホーム</FooterLink>
                <FooterLink href="/stocks">銘柄一覧</FooterLink>
                <FooterLink href="/sectors">業種別</FooterLink>
                <FooterLink href="/glossary">用語集</FooterLink>
                <FooterLink href="/faq">よくある質問</FooterLink>
              </ul>
            </div>

            {/* Legal & Info */}
            <div>
              <h4 className="font-semibold text-white mb-4 flex items-center gap-2">
                <span className="w-1 h-4 bg-gradient-to-b from-indigo-400 to-cyan-400 rounded-full" />
                インフォメーション
              </h4>
              <ul className="space-y-2">
                <FooterLink href="/login">ログイン</FooterLink>
                <FooterLink href="/register">新規登録</FooterLink>
              </ul>

              {/* Social Links - Placeholder */}
              <div className="mt-6">
                <p className="text-sm text-indigo-400 mb-2">Coming Soon</p>
                <div className="flex gap-3">
                  <SocialPlaceholder label="X" />
                  <SocialPlaceholder label="YT" />
                </div>
              </div>
            </div>
          </div>

          {/* Disclaimer */}
          <div className="mt-10 pt-6 border-t border-indigo-800/50">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-2 text-xs text-indigo-400">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  当サイトの情報は投資助言ではありません。投資判断はご自身の責任で行ってください。
                </span>
              </div>
              <p className="text-xs text-indigo-500">
                &copy; {currentYear} イリスのIR分析 All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <li>
      <Link
        href={href}
        className="text-indigo-300 hover:text-cyan-300 transition-colors text-sm flex items-center gap-1 group"
      >
        <span className="w-0 group-hover:w-2 h-px bg-cyan-400 transition-all duration-300" />
        {children}
      </Link>
    </li>
  );
}

function SocialPlaceholder({ label }: { label: string }) {
  return (
    <div className="w-8 h-8 rounded-full bg-indigo-800/50 border border-indigo-700/50 flex items-center justify-center text-indigo-400 text-xs">
      {label}
    </div>
  );
}
