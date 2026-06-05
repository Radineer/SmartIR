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
// 共通のカードコンテナ
// ============================================
interface CardContainerProps {
  children: React.ReactNode;
  width?: number | string;
  startFrame?: number;
  hoverEffect?: boolean;
  glowColor?: string;
}

const CardContainer: React.FC<CardContainerProps> = ({
  children,
  width = "auto",
  startFrame = 0,
  hoverEffect = true,
  glowColor = COLORS.primary,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // フェードイン
  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 100 },
  });

  // ホバー風のパルス効果
  const pulse = hoverEffect
    ? interpolate(
        Math.sin(animFrame * 0.05),
        [-1, 1],
        [0.98, 1.02]
      )
    : 1;

  // グロー効果
  const glowIntensity = hoverEffect
    ? interpolate(Math.sin(animFrame * 0.03), [-1, 1], [0.3, 0.6])
    : 0.3;

  return (
    <div
      style={{
        width,
        background: COLORS.overlay,
        backdropFilter: "blur(20px)",
        borderRadius: 16,
        border: "1px solid rgba(129, 140, 248, 0.2)",
        boxShadow: `
          0 8px 32px rgba(0, 0, 0, 0.4),
          0 0 40px ${glowColor}${Math.round(glowIntensity * 255).toString(16).padStart(2, '0')},
          inset 0 1px 0 rgba(255, 255, 255, 0.1)
        `,
        overflow: "hidden",
        opacity: fadeIn,
        transform: `
          scale(${interpolate(fadeIn, [0, 1], [0.9, 1]) * pulse})
          translateY(${interpolate(fadeIn, [0, 1], [30, 0])}px)
        `,
      }}
    >
      {children}
    </div>
  );
};

// ============================================
// 銘柄情報カード
// ============================================
interface StockCardProps {
  ticker: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  marketCap?: number;
  volume?: number;
  high52w?: number;
  low52w?: number;
  startFrame?: number;
  compact?: boolean;
}

export const StockCard: React.FC<StockCardProps> = ({
  ticker,
  name,
  price,
  change,
  changePercent,
  marketCap,
  volume,
  high52w,
  low52w,
  startFrame = 0,
  compact = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const isPositive = change >= 0;
  const changeColor = isPositive ? COLORS.positive : COLORS.negative;

  // 価格カウントアップ
  const priceProgress = interpolate(animFrame, [10, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const displayPrice = price * priceProgress;

  // ミニチャートのモックデータ
  const miniChartPoints = isPositive
    ? [40, 35, 45, 38, 50, 42, 55, 48, 60, 52, 58, 65]
    : [65, 58, 52, 60, 48, 55, 42, 50, 38, 45, 35, 40];

  const formatNumber = (num: number): string => {
    if (num >= 1e12) return `${(num / 1e12).toFixed(2)}兆`;
    if (num >= 1e8) return `${(num / 1e8).toFixed(2)}億`;
    if (num >= 1e4) return `${(num / 1e4).toFixed(2)}万`;
    return num.toLocaleString();
  };

  return (
    <CardContainer
      width={compact ? 280 : 360}
      startFrame={startFrame}
      glowColor={changeColor}
    >
      {/* ヘッダーバー */}
      <div
        style={{
          height: 4,
          background: `linear-gradient(90deg, ${COLORS.primary} 0%, ${changeColor} 100%)`,
        }}
      />

      <div style={{ padding: compact ? 16 : 24 }}>
        {/* ティッカーと銘柄名 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: compact ? 12 : 16,
          }}
        >
          <div>
            <div
              style={{
                color: COLORS.secondary,
                fontSize: compact ? 14 : 16,
                fontWeight: 700,
                letterSpacing: "0.05em",
                fontFamily: "monospace",
              }}
            >
              {ticker}
            </div>
            <div
              style={{
                color: "rgba(255, 255, 255, 0.7)",
                fontSize: compact ? 12 : 14,
                marginTop: 2,
              }}
            >
              {name}
            </div>
          </div>

          {/* ミニチャート */}
          <svg
            width={compact ? 60 : 80}
            height={compact ? 30 : 40}
            viewBox="0 0 80 40"
          >
            <defs>
              <linearGradient
                id={`miniGradient-${ticker}`}
                x1="0%"
                y1="0%"
                x2="0%"
                y2="100%"
              >
                <stop offset="0%" stopColor={changeColor} stopOpacity={0.4} />
                <stop offset="100%" stopColor={changeColor} stopOpacity={0} />
              </linearGradient>
            </defs>

            {/* エリア */}
            <path
              d={`M 0 40 ${miniChartPoints.map((p, i) => `L ${(i * 80) / (miniChartPoints.length - 1)} ${40 - (p / 65) * 35}`).join(" ")} L 80 40 Z`}
              fill={`url(#miniGradient-${ticker})`}
              opacity={priceProgress}
            />

            {/* ライン */}
            <path
              d={`M ${miniChartPoints.map((p, i) => `${(i * 80) / (miniChartPoints.length - 1)} ${40 - (p / 65) * 35}`).join(" L ")}`}
              fill="none"
              stroke={changeColor}
              strokeWidth={2}
              strokeLinecap="round"
              opacity={priceProgress}
            />
          </svg>
        </div>

        {/* 価格 */}
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 12,
            marginBottom: compact ? 12 : 20,
          }}
        >
          <span
            style={{
              color: COLORS.white,
              fontSize: compact ? 28 : 36,
              fontWeight: 700,
              fontFamily: "monospace",
            }}
          >
            ¥{displayPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>

          {/* 変動 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              color: changeColor,
              fontSize: compact ? 14 : 16,
              fontWeight: 600,
              fontFamily: "monospace",
              opacity: priceProgress,
            }}
          >
            {/* 矢印 */}
            <svg
              width={16}
              height={16}
              viewBox="0 0 16 16"
              style={{
                transform: isPositive ? "rotate(0deg)" : "rotate(180deg)",
              }}
            >
              <path
                d="M8 3 L13 10 L10 10 L10 13 L6 13 L6 10 L3 10 Z"
                fill={changeColor}
              />
            </svg>
            <span>
              {isPositive ? "+" : ""}
              {change.toLocaleString()} ({isPositive ? "+" : ""}
              {changePercent.toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* 詳細情報 */}
        {!compact && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 12,
              paddingTop: 16,
              borderTop: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            {marketCap && (
              <div>
                <div
                  style={{
                    color: "rgba(255, 255, 255, 0.5)",
                    fontSize: 12,
                    marginBottom: 4,
                  }}
                >
                  時価総額
                </div>
                <div
                  style={{
                    color: COLORS.white,
                    fontSize: 14,
                    fontWeight: 600,
                    fontFamily: "monospace",
                  }}
                >
                  {formatNumber(marketCap)}円
                </div>
              </div>
            )}

            {volume && (
              <div>
                <div
                  style={{
                    color: "rgba(255, 255, 255, 0.5)",
                    fontSize: 12,
                    marginBottom: 4,
                  }}
                >
                  出来高
                </div>
                <div
                  style={{
                    color: COLORS.white,
                    fontSize: 14,
                    fontWeight: 600,
                    fontFamily: "monospace",
                  }}
                >
                  {formatNumber(volume)}株
                </div>
              </div>
            )}

            {high52w && (
              <div>
                <div
                  style={{
                    color: "rgba(255, 255, 255, 0.5)",
                    fontSize: 12,
                    marginBottom: 4,
                  }}
                >
                  52週高値
                </div>
                <div
                  style={{
                    color: COLORS.positive,
                    fontSize: 14,
                    fontWeight: 600,
                    fontFamily: "monospace",
                  }}
                >
                  ¥{high52w.toLocaleString()}
                </div>
              </div>
            )}

            {low52w && (
              <div>
                <div
                  style={{
                    color: "rgba(255, 255, 255, 0.5)",
                    fontSize: 12,
                    marginBottom: 4,
                  }}
                >
                  52週安値
                </div>
                <div
                  style={{
                    color: COLORS.negative,
                    fontSize: 14,
                    fontWeight: 600,
                    fontFamily: "monospace",
                  }}
                >
                  ¥{low52w.toLocaleString()}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </CardContainer>
  );
};

// ============================================
// 指数情報カード
// ============================================
interface IndexCardProps {
  name: string;
  value: number;
  change: number;
  changePercent: number;
  icon?: string;
  startFrame?: number;
}

export const IndexCard: React.FC<IndexCardProps> = ({
  name,
  value,
  change,
  changePercent,
  icon = "📊",
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const animFrame = Math.max(0, frame - startFrame);

  const isPositive = change >= 0;
  const changeColor = isPositive ? COLORS.positive : COLORS.negative;

  // 値のアニメーション
  const valueProgress = interpolate(animFrame, [10, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const displayValue = value * valueProgress;

  return (
    <CardContainer
      width={260}
      startFrame={startFrame}
      glowColor={changeColor}
    >
      <div style={{ padding: 20 }}>
        {/* アイコンと名前 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: `linear-gradient(135deg, ${COLORS.primary}60 0%, ${COLORS.secondary}60 100%)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
            }}
          >
            {icon}
          </div>
          <div
            style={{
              color: COLORS.white,
              fontSize: 16,
              fontWeight: 600,
            }}
          >
            {name}
          </div>
        </div>

        {/* 値 */}
        <div
          style={{
            color: COLORS.white,
            fontSize: 32,
            fontWeight: 700,
            fontFamily: "monospace",
            marginBottom: 8,
          }}
        >
          {displayValue.toLocaleString(undefined, {
            maximumFractionDigits: 2,
          })}
        </div>

        {/* 変動 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: changeColor,
            fontSize: 16,
            fontWeight: 600,
            opacity: valueProgress,
          }}
        >
          <svg
            width={18}
            height={18}
            viewBox="0 0 18 18"
            style={{
              transform: isPositive ? "rotate(0deg)" : "rotate(180deg)",
            }}
          >
            <path
              d="M9 3 L15 11 L11 11 L11 15 L7 15 L7 11 L3 11 Z"
              fill={changeColor}
            />
          </svg>
          <span>
            {isPositive ? "+" : ""}
            {change.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
          <span style={{ opacity: 0.8 }}>
            ({isPositive ? "+" : ""}
            {changePercent.toFixed(2)}%)
          </span>
        </div>
      </div>
    </CardContainer>
  );
};

// ============================================
// ニュースヘッドラインカード
// ============================================
interface NewsHeadlineCardProps {
  headline: string;
  source?: string;
  time?: string;
  category?: string;
  sentiment?: "positive" | "negative" | "neutral";
  startFrame?: number;
}

export const NewsHeadlineCard: React.FC<NewsHeadlineCardProps> = ({
  headline,
  source,
  time,
  category,
  sentiment = "neutral",
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const sentimentColor =
    sentiment === "positive"
      ? COLORS.positive
      : sentiment === "negative"
        ? COLORS.negative
        : COLORS.secondary;

  // テキストのタイプライター効果
  const visibleChars = Math.floor(animFrame * 0.8);
  const displayHeadline = headline.slice(
    0,
    Math.min(visibleChars, headline.length)
  );
  const isComplete = visibleChars >= headline.length;

  // メタ情報のフェードイン
  const metaFade = interpolate(animFrame, [30, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <CardContainer width={500} startFrame={startFrame} glowColor={sentimentColor}>
      {/* サイドバー */}
      <div style={{ display: "flex" }}>
        <div
          style={{
            width: 4,
            background: sentimentColor,
          }}
        />

        <div style={{ flex: 1, padding: 20 }}>
          {/* カテゴリー */}
          {category && (
            <div
              style={{
                display: "inline-block",
                background: `${sentimentColor}30`,
                color: sentimentColor,
                fontSize: 12,
                fontWeight: 600,
                padding: "4px 10px",
                borderRadius: 4,
                marginBottom: 12,
                opacity: metaFade,
              }}
            >
              {category}
            </div>
          )}

          {/* ヘッドライン */}
          <div
            style={{
              color: COLORS.white,
              fontSize: 20,
              fontWeight: 600,
              lineHeight: 1.5,
              marginBottom: 16,
              minHeight: 60,
            }}
          >
            {displayHeadline}
            {!isComplete && (
              <span
                style={{
                  color: COLORS.secondary,
                  opacity: Math.sin(animFrame * 0.3) > 0 ? 1 : 0,
                }}
              >
                |
              </span>
            )}
          </div>

          {/* ソースと時間 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              opacity: metaFade,
            }}
          >
            {source && (
              <div
                style={{
                  color: "rgba(255, 255, 255, 0.6)",
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span>📰</span>
                {source}
              </div>
            )}
            {time && (
              <div
                style={{
                  color: "rgba(255, 255, 255, 0.5)",
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span>🕐</span>
                {time}
              </div>
            )}
          </div>
        </div>
      </div>
    </CardContainer>
  );
};

// ============================================
// マルチカードグリッド
// ============================================
interface CardGridProps {
  children: React.ReactNode;
  columns?: number;
  gap?: number;
  startFrame?: number;
}

export const CardGrid: React.FC<CardGridProps> = ({
  children,
  columns = 3,
  gap = 24,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap,
        opacity: fadeIn,
      }}
    >
      {children}
    </div>
  );
};

// ============================================
// コンパクトスタットカード
// ============================================
interface CompactStatCardProps {
  label: string;
  value: string | number;
  change?: number;
  icon?: string;
  color?: string;
  startFrame?: number;
}

export const CompactStatCard: React.FC<CompactStatCardProps> = ({
  label,
  value,
  change,
  icon,
  color = COLORS.secondary,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const animFrame = Math.max(0, frame - startFrame);

  const valueProgress = interpolate(animFrame, [5, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const displayValue =
    typeof value === "number"
      ? (value * valueProgress).toLocaleString(undefined, {
          maximumFractionDigits: 2,
        })
      : value;

  return (
    <CardContainer
      width="100%"
      startFrame={startFrame}
      hoverEffect={false}
      glowColor={color}
    >
      <div style={{ padding: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 10,
          }}
        >
          {icon && <span style={{ fontSize: 18 }}>{icon}</span>}
          <span
            style={{
              color: "rgba(255, 255, 255, 0.6)",
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            {label}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 10,
          }}
        >
          <span
            style={{
              color: COLORS.white,
              fontSize: 24,
              fontWeight: 700,
              fontFamily:
                typeof value === "number" ? "monospace" : "inherit",
            }}
          >
            {displayValue}
          </span>

          {change !== undefined && (
            <span
              style={{
                color: change >= 0 ? COLORS.positive : COLORS.negative,
                fontSize: 14,
                fontWeight: 600,
                fontFamily: "monospace",
              }}
            >
              {change >= 0 ? "+" : ""}
              {change.toFixed(2)}%
            </span>
          )}
        </div>
      </div>
    </CardContainer>
  );
};

// ============================================
// エクスポート
// ============================================
export default {
  StockCard,
  IndexCard,
  NewsHeadlineCard,
  CardGrid,
  CompactStatCard,
};
