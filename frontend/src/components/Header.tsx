"use client";

import Link from "next/link";
import Image from "next/image";
import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import GlobalSearch from "./GlobalSearch";

export default function Header() {
  const { user, logout } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled
          ? "glass shadow-lg"
          : "bg-white/80 backdrop-blur-sm"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo & Nav */}
          <div className="flex items-center space-x-8">
            <Link href="/" className="flex items-center gap-3 group">
              {/* Iris Icon */}
              <div className="relative w-10 h-10 rounded-full overflow-hidden shadow-md group-hover:shadow-lg transition-shadow">
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 via-purple-500 to-cyan-500 opacity-90" />
                <Image
                  src="/images/iris/iris-icon.png"
                  alt="イリス"
                  width={40}
                  height={40}
                  className="relative z-10 object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 group-hover:opacity-0 transition-opacity" />
              </div>
              {/* Logo Text */}
              <div className="flex flex-col">
                <span className="text-lg font-bold bg-gradient-to-r from-indigo-600 to-cyan-600 bg-clip-text text-transparent">
                  イリスのIR分析
                </span>
                <span className="text-[10px] text-gray-400 -mt-1 hidden sm:block">
                  AI Analyst from 2050
                </span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center space-x-1">
              <NavLink href="/stocks">銘柄一覧</NavLink>
              <NavLink href="/sectors">業種別</NavLink>
              <NavLink href="/glossary">用語集</NavLink>
              <NavLink href="/faq">FAQ</NavLink>
              <NavLink href="/watchlist">ウォッチ</NavLink>
            </nav>
          </div>

          {/* Right Section */}
          <div className="flex items-center space-x-3">
            {/* Global Search */}
            <GlobalSearch />

            {/* Status Badge */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-gradient-to-r from-indigo-50 to-cyan-50 border border-indigo-100">
              <span className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
              <span className="text-xs font-medium text-indigo-600">分析稼働中</span>
            </div>

            {user ? (
              <div className="flex items-center space-x-3">
                <span className="text-sm text-gray-600 hidden sm:block">
                  {user.name || user.email}
                </span>
                {user.role === "admin" && (
                  <Link
                    href="/admin"
                    className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                  >
                    管理
                  </Link>
                )}
                <button
                  onClick={logout}
                  className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
                >
                  ログアウト
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <Link
                  href="/login"
                  className="text-sm text-gray-600 hover:text-indigo-600 transition-colors px-3 py-1.5"
                >
                  ログイン
                </Link>
                <Link
                  href="/register"
                  className="btn-iris text-sm px-4 py-1.5"
                >
                  無料登録
                </Link>
              </div>
            )}

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-indigo-50 transition-colors"
            >
              <svg
                className="w-6 h-6 text-gray-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden glass border-t border-indigo-100">
          <nav className="px-4 py-3 space-y-1">
            <MobileNavLink href="/stocks" onClick={() => setMobileMenuOpen(false)}>
              銘柄一覧
            </MobileNavLink>
            <MobileNavLink href="/sectors" onClick={() => setMobileMenuOpen(false)}>
              業種別
            </MobileNavLink>
            <MobileNavLink href="/glossary" onClick={() => setMobileMenuOpen(false)}>
              用語集
            </MobileNavLink>
            <MobileNavLink href="/faq" onClick={() => setMobileMenuOpen(false)}>
              FAQ
            </MobileNavLink>
            <MobileNavLink href="/watchlist" onClick={() => setMobileMenuOpen(false)}>
              ウォッチリスト
            </MobileNavLink>
          </nav>
        </div>
      )}
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="relative px-4 py-2 text-sm font-medium text-gray-600 hover:text-indigo-600 transition-colors rounded-lg hover:bg-indigo-50/50 group"
    >
      {children}
      <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-0.5 bg-gradient-to-r from-indigo-500 to-cyan-500 group-hover:w-1/2 transition-all duration-300" />
    </Link>
  );
}

function MobileNavLink({
  href,
  onClick,
  children,
}: {
  href: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="block px-4 py-2.5 text-gray-600 hover:text-indigo-600 hover:bg-indigo-50/50 rounded-lg transition-colors"
    >
      {children}
    </Link>
  );
}
