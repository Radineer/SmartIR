"use client";

import Image from "next/image";
import { useState, useEffect } from "react";

export type IrisExpression =
  | "normal"
  | "smile"
  | "analysis"
  | "surprise"
  | "confused"
  | "thinking"
  | "freeze"
  | "eating";

interface IrisCharacterProps {
  expression?: IrisExpression;
  size?: "sm" | "md" | "lg" | "xl";
  showSpeechBubble?: boolean;
  message?: string;
  className?: string;
}

const sizeMap = {
  sm: { width: 80, height: 80 },
  md: { width: 150, height: 150 },
  lg: { width: 250, height: 375 },
  xl: { width: 400, height: 600 },
};

// イリスのコメントパターン
const irisComments = {
  greeting: [
    "こんにちは！イリスです。今日も一緒にIR資料を読み解きましょう。",
    "おはようございます。決算シーズン、データがいっぱいで楽しいですね。",
    "いらっしゃいませ。何かお手伝いできることはありますか？",
  ],
  positive: [
    "この決算、なかなか良い数字ですね。詳しく見ていきましょう。",
    "営業利益の伸びが印象的です。",
    "データを見る限り、堅調な業績と言えそうです。",
    "前年同期比でプラス成長。良い傾向ですね。",
  ],
  negative: [
    "少し気になる点がありますね...一緒に確認しましょう。",
    "前期比で減少している項目がありますね。",
    "慎重に分析する必要がありそうです。",
    "この数字は要注意かもしれません...",
  ],
  neutral: [
    "データを整理しました。確認していきましょう。",
    "特筆すべき変化は少ないですが、詳細を見てみましょう。",
    "安定した数字が並んでいますね。",
    "大きな変動はありません。着実な経営と言えるかもしれません。",
  ],
  loading: [
    "分析中です...少々お待ちください...",
    "データを処理しています...",
    "もう少しで完了します...たぶん...",
    "2050年のコンピュータなら一瞬なんですけどね...",
  ],
  error: [
    "あれ...？データの取得に失敗しました...",
    "すみません、ちょっとフリーズしちゃいました...",
    "エラーです...再読み込みをお試しください...",
    "転送時のバグがまた...申し訳ありません...",
  ],
  empty: [
    "まだ分析データがありません。IR資料が届き次第、解析を開始します。",
    "このページにはまだ情報がないみたいですね...",
    "データがありません...少々お待ちを...",
  ],
};

export function getRandomComment(
  type: keyof typeof irisComments
): string {
  const comments = irisComments[type];
  return comments[Math.floor(Math.random() * comments.length)];
}

export function IrisCharacter({
  expression = "normal",
  size = "md",
  showSpeechBubble = false,
  message,
  className = "",
}: IrisCharacterProps) {
  const [mounted, setMounted] = useState(false);
  const dimensions = sizeMap[size];

  useEffect(() => {
    setMounted(true);
  }, []);

  // 画像がない間はプレースホルダーを表示
  const imageSrc = `/images/iris/iris-${expression === "analysis" ? "analysis" : "normal"}.png`;
  const placeholderSrc = "/images/iris/iris-placeholder.svg";

  return (
    <div className={`relative inline-block ${className}`}>
      {/* キャラクター画像 */}
      <div
        className="relative"
        style={{ width: dimensions.width, height: dimensions.height }}
      >
        {mounted && (
          <Image
            src={imageSrc}
            alt="イリス"
            width={dimensions.width}
            height={dimensions.height}
            className="object-contain"
            onError={(e) => {
              // 画像がない場合はプレースホルダーに
              (e.target as HTMLImageElement).src = placeholderSrc;
            }}
          />
        )}
      </div>

      {/* 吹き出し */}
      {showSpeechBubble && message && (
        <div className="absolute -top-2 left-full ml-2 max-w-xs">
          <div className="relative bg-white rounded-lg shadow-lg border border-gray-200 p-3">
            {/* 吹き出しの三角形 */}
            <div className="absolute top-4 -left-2 w-0 h-0 border-t-8 border-t-transparent border-r-8 border-r-white border-b-8 border-b-transparent" />
            <div className="absolute top-4 -left-[9px] w-0 h-0 border-t-8 border-t-transparent border-r-8 border-r-gray-200 border-b-8 border-b-transparent" />
            <p className="text-sm text-gray-700">{message}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// アイコン用の小さいイリス
export function IrisIcon({ size = 32 }: { size?: number }) {
  return (
    <div
      className="relative rounded-full overflow-hidden bg-gradient-to-br from-indigo-100 to-cyan-100"
      style={{ width: size, height: size }}
    >
      <Image
        src="/images/iris/iris-icon.png"
        alt="イリス"
        width={size}
        height={size}
        className="object-cover"
        onError={(e) => {
          // プレースホルダー: イニシャル表示
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
      {/* フォールバック: イニシャル */}
      <div className="absolute inset-0 flex items-center justify-center text-indigo-600 font-bold text-xs">
        IR
      </div>
    </div>
  );
}

// 分析結果に応じたイリスコメントコンポーネント
interface IrisAnalysisCommentProps {
  sentimentPositive?: number;
  sentimentNegative?: number;
  isLoading?: boolean;
  hasError?: boolean;
  isEmpty?: boolean;
}

export function IrisAnalysisComment({
  sentimentPositive = 0,
  sentimentNegative = 0,
  isLoading = false,
  hasError = false,
  isEmpty = false,
}: IrisAnalysisCommentProps) {
  const [comment, setComment] = useState("");
  const [expression, setExpression] = useState<IrisExpression>("normal");

  useEffect(() => {
    if (isLoading) {
      setComment(getRandomComment("loading"));
      setExpression("thinking");
    } else if (hasError) {
      setComment(getRandomComment("error"));
      setExpression("freeze");
    } else if (isEmpty) {
      setComment(getRandomComment("empty"));
      setExpression("confused");
    } else if (sentimentPositive > 0.5) {
      setComment(getRandomComment("positive"));
      setExpression("smile");
    } else if (sentimentNegative > 0.3) {
      setComment(getRandomComment("negative"));
      setExpression("confused");
    } else {
      setComment(getRandomComment("neutral"));
      setExpression("normal");
    }
  }, [sentimentPositive, sentimentNegative, isLoading, hasError, isEmpty]);

  return (
    <div className="flex items-start gap-4 p-4 bg-gradient-to-r from-indigo-50 to-cyan-50 rounded-lg border border-indigo-100">
      <IrisCharacter expression={expression} size="sm" />
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-semibold text-indigo-700">イリス</span>
          <span className="text-xs text-gray-500">AI分析アシスタント</span>
        </div>
        <p className="text-gray-700 text-sm leading-relaxed">{comment}</p>
        <p className="text-xs text-gray-400 mt-2">
          ※イリスの分析は参考情報です。投資判断はご自身の責任でお願いします。
        </p>
      </div>
    </div>
  );
}
