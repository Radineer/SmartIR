import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/hooks/useAuth";
import { WatchlistProvider } from "@/contexts/WatchlistContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { SiteOrganizationData, WebSiteData } from "@/components/StructuredData";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://smartir-web-silk.vercel.app"),
  title: {
    default: "イリスのIR分析 | AI IR Insight",
    template: "%s | イリスのIR分析",
  },
  description: "2050年から来たAIアナリスト「イリス」が、上場企業のIR資料をわかりやすく解説。決算短信・有価証券報告書の要約、センチメント分析をお届けします。",
  keywords: ["IR分析", "決算", "有価証券報告書", "AI分析", "株式投資", "企業分析", "イリス"],
  authors: [{ name: "イリスのIR分析" }],
  openGraph: {
    type: "website",
    locale: "ja_JP",
    url: "https://smartir-web-silk.vercel.app",
    siteName: "イリスのIR分析",
    title: "イリスのIR分析 | AI IR Insight",
    description: "2050年から来たAIアナリスト「イリス」が、上場企業のIR資料をわかりやすく解説。",
    images: [
      {
        url: "/images/og-image.png",
        width: 1200,
        height: 630,
        alt: "イリスのIR分析",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "イリスのIR分析 | AI IR Insight",
    description: "2050年から来たAIアナリスト「イリス」が、IR資料をわかりやすく解説。",
    images: ["/images/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <head>
        <SiteOrganizationData />
        <WebSiteData />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-50`}
      >
        <AuthProvider>
          <WatchlistProvider>
            <Header />
            <main className="min-h-screen fade-in-up">{children}</main>
            <Footer />
          </WatchlistProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
