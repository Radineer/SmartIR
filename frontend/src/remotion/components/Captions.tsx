import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";

// ============================================
// カラーパレット
// ============================================
const COLORS = {
  primary: "#4f46e5", // インディゴ
  secondary: "#06b6d4", // シアン
  accent: "#818cf8", // ライトインディゴ
  positive: "#22c55e", // 上昇（緑）
  negative: "#ef4444", // 下落（赤）
  white: "#ffffff",
  dark: "#1e1b4b",
  overlay: "rgba(30, 27, 75, 0.9)",
};

// ============================================
// ニュースティッカー（テロップバー）
// ============================================
interface NewsTickerProps {
  text: string;
  label?: string;
  startFrame?: number;
  durationFrames?: number;
  speed?: number; // スクロール速度（ピクセル/フレーム）
}

export const NewsTicker: React.FC<NewsTickerProps> = ({
  text,
  label = "BREAKING",
  startFrame = 0,
  durationFrames = 300,
  speed = 2,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // スライドイン
  const slideIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  // スライドアウト
  const slideOut =
    animFrame > durationFrames - 30
      ? interpolate(
          animFrame,
          [durationFrames - 30, durationFrames],
          [0, 100],
          { extrapolateRight: "clamp" }
        )
      : 0;

  // テキストスクロール
  const scrollOffset = animFrame * speed;

  if (animFrame < 0 || animFrame > durationFrames) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 80,
        left: 0,
        right: 0,
        height: 60,
        transform: `translateY(${interpolate(slideIn, [0, 1], [100, 0]) + slideOut}px)`,
        display: "flex",
        alignItems: "stretch",
        overflow: "hidden",
      }}
    >
      {/* ラベル部分 */}
      <div
        style={{
          background: `linear-gradient(135deg, ${COLORS.primary} 0%, ${COLORS.accent} 100%)`,
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "4px 0 16px rgba(0, 0, 0, 0.3)",
          zIndex: 1,
        }}
      >
        <span
          style={{
            color: COLORS.white,
            fontSize: 18,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
      </div>

      {/* テキスト部分 */}
      <div
        style={{
          flex: 1,
          background: COLORS.overlay,
          backdropFilter: "blur(10px)",
          display: "flex",
          alignItems: "center",
          overflow: "hidden",
          borderTop: `2px solid ${COLORS.secondary}`,
          borderBottom: `2px solid ${COLORS.secondary}`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            whiteSpace: "nowrap",
            transform: `translateX(${1920 - scrollOffset}px)`,
          }}
        >
          <span
            style={{
              color: COLORS.white,
              fontSize: 24,
              fontWeight: 500,
              marginRight: 100,
            }}
          >
            {text}
          </span>
          <span
            style={{
              color: COLORS.secondary,
              fontSize: 20,
            }}
          >
            ●
          </span>
          <span
            style={{
              color: COLORS.white,
              fontSize: 24,
              fontWeight: 500,
              marginLeft: 100,
            }}
          >
            {text}
          </span>
        </div>
      </div>
    </div>
  );
};

// ============================================
// キーワードハイライトテキスト
// ============================================
interface KeywordHighlightProps {
  text: string;
  keywords: Array<{
    word: string;
    color?: string;
    backgroundColor?: string;
  }>;
  style?: React.CSSProperties;
}

export const KeywordHighlight: React.FC<KeywordHighlightProps> = ({
  text,
  keywords,
  style,
}) => {
  const renderHighlightedText = () => {
    let result: React.ReactNode[] = [];
    let remainingText = text;
    let keyIndex = 0;

    while (remainingText.length > 0) {
      let earliestMatch: {
        keyword: (typeof keywords)[0];
        index: number;
      } | null = null;

      for (const keyword of keywords) {
        const idx = remainingText.indexOf(keyword.word);
        if (
          idx !== -1 &&
          (earliestMatch === null || idx < earliestMatch.index)
        ) {
          earliestMatch = { keyword, index: idx };
        }
      }

      if (earliestMatch) {
        // マッチ前のテキスト
        if (earliestMatch.index > 0) {
          result.push(
            <span key={`text-${keyIndex++}`}>
              {remainingText.slice(0, earliestMatch.index)}
            </span>
          );
        }
        // ハイライトされたキーワード
        result.push(
          <span
            key={`keyword-${keyIndex++}`}
            style={{
              color: earliestMatch.keyword.color || COLORS.secondary,
              backgroundColor:
                earliestMatch.keyword.backgroundColor ||
                "rgba(6, 182, 212, 0.2)",
              padding: "2px 8px",
              borderRadius: 4,
              fontWeight: 600,
            }}
          >
            {earliestMatch.keyword.word}
          </span>
        );
        remainingText = remainingText.slice(
          earliestMatch.index + earliestMatch.keyword.word.length
        );
      } else {
        result.push(<span key={`text-${keyIndex++}`}>{remainingText}</span>);
        remainingText = "";
      }
    }

    return result;
  };

  return (
    <span
      style={{
        color: COLORS.white,
        fontSize: 28,
        lineHeight: 1.6,
        ...style,
      }}
    >
      {renderHighlightedText()}
    </span>
  );
};

// ============================================
// 数値ハイライト（上昇/下落）
// ============================================
interface NumberHighlightProps {
  value: number;
  prefix?: string;
  suffix?: string;
  showSign?: boolean;
  fontSize?: number;
  animated?: boolean;
  startFrame?: number;
}

export const NumberHighlight: React.FC<NumberHighlightProps> = ({
  value,
  prefix = "",
  suffix = "",
  showSign = true,
  fontSize = 32,
  animated = true,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const isPositive = value >= 0;
  const color = isPositive ? COLORS.positive : COLORS.negative;

  // カウントアップアニメーション
  const progress = animated
    ? interpolate(animFrame, [0, 30], [0, 1], {
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      })
    : 1;

  const displayValue = value * progress;
  const sign = showSign && value > 0 ? "+" : "";

  // パルスアニメーション
  const pulse = spring({
    frame: animFrame,
    fps,
    config: { damping: 8, stiffness: 200 },
  });

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        color,
        fontSize,
        fontWeight: 700,
        fontFamily: "monospace",
        transform: `scale(${interpolate(pulse, [0, 1], [0.8, 1])})`,
      }}
    >
      {/* 矢印アイコン */}
      <svg
        width={fontSize * 0.6}
        height={fontSize * 0.6}
        viewBox="0 0 24 24"
        style={{
          transform: isPositive ? "rotate(0deg)" : "rotate(180deg)",
        }}
      >
        <path
          d="M12 4 L20 14 L16 14 L16 20 L8 20 L8 14 L4 14 Z"
          fill={color}
        />
      </svg>
      <span>
        {prefix}
        {sign}
        {typeof displayValue === "number"
          ? displayValue.toFixed(2)
          : displayValue}
        {suffix}
      </span>
    </span>
  );
};

// ============================================
// タイプライター効果
// ============================================
interface TypewriterProps {
  text: string;
  startFrame?: number;
  charPerFrame?: number;
  cursorBlink?: boolean;
  style?: React.CSSProperties;
}

export const Typewriter: React.FC<TypewriterProps> = ({
  text,
  startFrame = 0,
  charPerFrame = 0.5,
  cursorBlink = true,
  style,
}) => {
  const frame = useCurrentFrame();
  const animFrame = Math.max(0, frame - startFrame);

  const visibleChars = Math.floor(animFrame * charPerFrame);
  const displayText = text.slice(0, Math.min(visibleChars, text.length));
  const isComplete = visibleChars >= text.length;

  // カーソル点滅
  const cursorOpacity = cursorBlink
    ? Math.sin(animFrame * 0.2) > 0
      ? 1
      : 0
    : 1;

  return (
    <span
      style={{
        color: COLORS.white,
        fontSize: 28,
        fontFamily: "monospace",
        ...style,
      }}
    >
      {displayText}
      {!isComplete && (
        <span
          style={{
            opacity: cursorOpacity,
            color: COLORS.secondary,
            marginLeft: 2,
          }}
        >
          |
        </span>
      )}
    </span>
  );
};

// ============================================
// スライドインテキスト
// ============================================
interface SlideTextProps {
  text: string;
  direction?: "left" | "right" | "top" | "bottom";
  startFrame?: number;
  exitFrame?: number;
  style?: React.CSSProperties;
}

export const SlideText: React.FC<SlideTextProps> = ({
  text,
  direction = "left",
  startFrame = 0,
  exitFrame,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // 入場アニメーション
  const slideIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 100 },
  });

  // 退場アニメーション
  let slideOut = 0;
  if (exitFrame !== undefined && frame >= exitFrame) {
    slideOut = spring({
      frame: frame - exitFrame,
      fps,
      config: { damping: 20, stiffness: 100 },
    });
  }

  const getTransform = () => {
    const distance = 100;
    const enterOffset = interpolate(slideIn, [0, 1], [distance, 0]);
    const exitOffset = interpolate(slideOut, [0, 1], [0, distance]);

    switch (direction) {
      case "left":
        return `translateX(${-enterOffset + exitOffset}px)`;
      case "right":
        return `translateX(${enterOffset - exitOffset}px)`;
      case "top":
        return `translateY(${-enterOffset + exitOffset}px)`;
      case "bottom":
        return `translateY(${enterOffset - exitOffset}px)`;
    }
  };

  return (
    <div
      style={{
        color: COLORS.white,
        fontSize: 32,
        fontWeight: 600,
        transform: getTransform(),
        opacity: interpolate(slideIn, [0, 1], [0, 1]) *
          interpolate(slideOut, [0, 1], [1, 0]),
        ...style,
      }}
    >
      {text}
    </div>
  );
};

// ============================================
// テロップボックス（画面下部）
// ============================================
interface CaptionBoxProps {
  text: string;
  speaker?: string;
  startFrame?: number;
  durationFrames?: number;
  position?: "bottom" | "top";
}

export const CaptionBox: React.FC<CaptionBoxProps> = ({
  text,
  speaker,
  startFrame = 0,
  durationFrames = 120,
  position = "bottom",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  if (animFrame < 0 || animFrame > durationFrames) return null;

  // スライドイン
  const slideIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 100 },
  });

  // フェードアウト
  const fadeOut =
    animFrame > durationFrames - 15
      ? interpolate(
          animFrame,
          [durationFrames - 15, durationFrames],
          [1, 0],
          { extrapolateRight: "clamp" }
        )
      : 1;

  const positionStyle =
    position === "bottom"
      ? { bottom: 100, left: 60, right: 500 }
      : { top: 100, left: 60, right: 500 };

  return (
    <div
      style={{
        position: "absolute",
        ...positionStyle,
        transform: `translateY(${interpolate(slideIn, [0, 1], [30, 0])}px)`,
        opacity: interpolate(slideIn, [0, 1], [0, 1]) * fadeOut,
      }}
    >
      {/* グラスモーフィズムコンテナ */}
      <div
        style={{
          background: COLORS.overlay,
          backdropFilter: "blur(20px)",
          borderRadius: 16,
          border: `1px solid rgba(129, 140, 248, 0.3)`,
          boxShadow: `
            0 8px 32px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.1)
          `,
          overflow: "hidden",
        }}
      >
        {/* アクセントライン */}
        <div
          style={{
            height: 3,
            background: `linear-gradient(90deg, ${COLORS.primary} 0%, ${COLORS.secondary} 100%)`,
          }}
        />

        <div style={{ padding: "16px 24px" }}>
          {/* スピーカー名 */}
          {speaker && (
            <div
              style={{
                color: COLORS.secondary,
                fontSize: 14,
                fontWeight: 600,
                marginBottom: 8,
                letterSpacing: "0.05em",
              }}
            >
              {speaker}
            </div>
          )}

          {/* テキスト */}
          <div
            style={{
              color: COLORS.white,
              fontSize: 28,
              fontWeight: 500,
              lineHeight: 1.5,
            }}
          >
            {text}
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// エクスポート
// ============================================
export default {
  NewsTicker,
  KeywordHighlight,
  NumberHighlight,
  Typewriter,
  SlideText,
  CaptionBox,
};
