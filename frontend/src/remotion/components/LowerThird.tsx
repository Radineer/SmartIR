import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
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
  overlay: "rgba(30, 27, 75, 0.95)",
};

// ============================================
// スピーカー表示（メイン）
// ============================================
interface SpeakerLowerThirdProps {
  name: string;
  title?: string;
  subtitle?: string;
  avatarUrl?: string;
  startFrame?: number;
  durationFrames?: number;
  position?: "left" | "right";
}

export const SpeakerLowerThird: React.FC<SpeakerLowerThirdProps> = ({
  name,
  title = "AI-IR Insight",
  subtitle,
  avatarUrl,
  startFrame = 0,
  durationFrames = 180,
  position = "left",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  if (animFrame < 0 || animFrame > durationFrames) return null;

  // 入場アニメーション
  const slideIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 18, stiffness: 90 },
  });

  // 退場アニメーション
  const isExiting = animFrame > durationFrames - 30;
  const slideOut = isExiting
    ? interpolate(
        animFrame,
        [durationFrames - 30, durationFrames],
        [0, 1],
        { extrapolateRight: "clamp" }
      )
    : 0;

  // ラインのアニメーション
  const lineExpand = interpolate(animFrame, [10, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // テキストのスタガード表示
  const nameOpacity = interpolate(animFrame, [15, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleOpacity = interpolate(animFrame, [25, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const positionStyle =
    position === "left"
      ? { left: 60, right: "auto" }
      : { right: 60, left: "auto" };

  return (
    <div
      style={{
        position: "absolute",
        bottom: 120,
        ...positionStyle,
        transform: `translateX(${interpolate(slideIn, [0, 1], [position === "left" ? -100 : 100, 0]) + (position === "left" ? -1 : 1) * slideOut * 100}px)`,
        opacity: interpolate(slideIn, [0, 1], [0, 1]) * (1 - slideOut),
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          gap: 0,
        }}
      >
        {/* アバター（オプション） */}
        {avatarUrl && (
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: "12px 0 0 12px",
              overflow: "hidden",
              border: `2px solid ${COLORS.secondary}`,
              borderRight: "none",
            }}
          >
            <img
              src={avatarUrl}
              alt={name}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          </div>
        )}

        {/* メインコンテンツ */}
        <div
          style={{
            background: COLORS.overlay,
            backdropFilter: "blur(20px)",
            borderRadius: avatarUrl ? "0 12px 12px 0" : 12,
            border: `1px solid rgba(129, 140, 248, 0.3)`,
            overflow: "hidden",
            boxShadow: `
              0 8px 32px rgba(0, 0, 0, 0.4),
              0 0 20px ${COLORS.primary}30
            `,
          }}
        >
          {/* 上部のアクセントライン */}
          <div
            style={{
              height: 3,
              background: `linear-gradient(90deg, ${COLORS.primary} 0%, ${COLORS.secondary} 100%)`,
              transform: `scaleX(${lineExpand})`,
              transformOrigin: "left",
            }}
          />

          <div style={{ padding: "16px 28px" }}>
            {/* 名前 */}
            <div
              style={{
                color: COLORS.white,
                fontSize: 26,
                fontWeight: 700,
                marginBottom: 4,
                opacity: nameOpacity,
                transform: `translateY(${interpolate(nameOpacity, [0, 1], [10, 0])}px)`,
              }}
            >
              {name}
            </div>

            {/* タイトル/役職 */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                opacity: titleOpacity,
                transform: `translateY(${interpolate(titleOpacity, [0, 1], [10, 0])}px)`,
              }}
            >
              <span
                style={{
                  color: COLORS.secondary,
                  fontSize: 14,
                  fontWeight: 600,
                  letterSpacing: "0.03em",
                }}
              >
                {title}
              </span>

              {subtitle && (
                <>
                  <span
                    style={{
                      color: "rgba(255, 255, 255, 0.3)",
                      fontSize: 14,
                    }}
                  >
                    |
                  </span>
                  <span
                    style={{
                      color: "rgba(255, 255, 255, 0.6)",
                      fontSize: 14,
                    }}
                  >
                    {subtitle}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// トピック表示
// ============================================
interface TopicLowerThirdProps {
  topic: string;
  subtitle?: string;
  number?: number;
  startFrame?: number;
  durationFrames?: number;
}

export const TopicLowerThird: React.FC<TopicLowerThirdProps> = ({
  topic,
  subtitle,
  number,
  startFrame = 0,
  durationFrames = 150,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  if (animFrame < 0 || animFrame > durationFrames) return null;

  // アニメーション
  const slideIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 18, stiffness: 100 },
  });

  const isExiting = animFrame > durationFrames - 25;
  const fadeOut = isExiting
    ? interpolate(
        animFrame,
        [durationFrames - 25, durationFrames],
        [1, 0],
        { extrapolateRight: "clamp" }
      )
    : 1;

  // 背景のスケール
  const bgScale = interpolate(animFrame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });

  // テキストのフェードイン
  const textFade = interpolate(animFrame, [10, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 120,
        left: 60,
        opacity: fadeOut,
        transform: `translateY(${interpolate(slideIn, [0, 1], [50, 0])}px)`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
        }}
      >
        {/* 番号バッジ */}
        {number !== undefined && (
          <div
            style={{
              width: 60,
              background: `linear-gradient(135deg, ${COLORS.primary} 0%, ${COLORS.accent} 100%)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "12px 0 0 12px",
              transform: `scaleY(${bgScale})`,
            }}
          >
            <span
              style={{
                color: COLORS.white,
                fontSize: 28,
                fontWeight: 700,
                opacity: textFade,
              }}
            >
              {number}
            </span>
          </div>
        )}

        {/* メインコンテンツ */}
        <div
          style={{
            background: COLORS.overlay,
            backdropFilter: "blur(20px)",
            borderRadius: number !== undefined ? "0 12px 12px 0" : 12,
            border: `1px solid rgba(129, 140, 248, 0.3)`,
            borderLeft: number !== undefined ? "none" : undefined,
            padding: "18px 32px",
            transform: `scaleX(${bgScale})`,
            transformOrigin: "left",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
          }}
        >
          {/* トピック */}
          <div
            style={{
              color: COLORS.white,
              fontSize: 24,
              fontWeight: 600,
              opacity: textFade,
              transform: `translateX(${interpolate(textFade, [0, 1], [20, 0])}px)`,
            }}
          >
            {topic}
          </div>

          {/* サブタイトル */}
          {subtitle && (
            <div
              style={{
                color: COLORS.secondary,
                fontSize: 14,
                marginTop: 6,
                opacity: interpolate(animFrame, [20, 40], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
              }}
            >
              {subtitle}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================
// ソース表示
// ============================================
interface SourceLowerThirdProps {
  source: string;
  url?: string;
  date?: string;
  startFrame?: number;
  durationFrames?: number;
}

export const SourceLowerThird: React.FC<SourceLowerThirdProps> = ({
  source,
  url,
  date,
  startFrame = 0,
  durationFrames = 120,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  if (animFrame < 0 || animFrame > durationFrames) return null;

  // アニメーション
  const slideIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 100 },
  });

  const isExiting = animFrame > durationFrames - 20;
  const fadeOut = isExiting
    ? interpolate(
        animFrame,
        [durationFrames - 20, durationFrames],
        [1, 0],
        { extrapolateRight: "clamp" }
      )
    : 1;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        right: 60,
        opacity: interpolate(slideIn, [0, 1], [0, 1]) * fadeOut,
        transform: `translateX(${interpolate(slideIn, [0, 1], [30, 0])}px)`,
      }}
    >
      <div
        style={{
          background: "rgba(0, 0, 0, 0.6)",
          backdropFilter: "blur(10px)",
          borderRadius: 8,
          padding: "10px 18px",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        {/* ソースアイコン */}
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: COLORS.secondary,
            boxShadow: `0 0 8px ${COLORS.secondary}`,
          }}
        />

        {/* ソース名 */}
        <span
          style={{
            color: COLORS.white,
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          出典: {source}
        </span>

        {/* 日付 */}
        {date && (
          <span
            style={{
              color: "rgba(255, 255, 255, 0.5)",
              fontSize: 12,
            }}
          >
            {date}
          </span>
        )}
      </div>
    </div>
  );
};

// ============================================
// ティッカー表示（画面上部）
// ============================================
interface HeaderTickerProps {
  items: Array<{
    label: string;
    value: string | number;
    change?: number;
  }>;
  startFrame?: number;
}

export const HeaderTicker: React.FC<HeaderTickerProps> = ({
  items,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // スライドダウン
  const slideDown = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 50,
        background: COLORS.overlay,
        backdropFilter: "blur(10px)",
        borderBottom: `1px solid rgba(129, 140, 248, 0.2)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 40,
        transform: `translateY(${interpolate(slideDown, [0, 1], [-50, 0])}px)`,
        opacity: slideDown,
      }}
    >
      {items.map((item, index) => {
        const itemDelay = index * 5;
        const itemFade = interpolate(
          animFrame - itemDelay - 10,
          [0, 15],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        const changeColor =
          item.change !== undefined
            ? item.change >= 0
              ? COLORS.positive
              : COLORS.negative
            : COLORS.white;

        return (
          <div
            key={index}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              opacity: itemFade,
            }}
          >
            {/* ラベル */}
            <span
              style={{
                color: "rgba(255, 255, 255, 0.6)",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {item.label}
            </span>

            {/* 値 */}
            <span
              style={{
                color: COLORS.white,
                fontSize: 15,
                fontWeight: 600,
                fontFamily: "monospace",
              }}
            >
              {typeof item.value === "number"
                ? item.value.toLocaleString()
                : item.value}
            </span>

            {/* 変動 */}
            {item.change !== undefined && (
              <span
                style={{
                  color: changeColor,
                  fontSize: 13,
                  fontWeight: 600,
                  fontFamily: "monospace",
                }}
              >
                {item.change >= 0 ? "+" : ""}
                {item.change.toFixed(2)}%
              </span>
            )}

            {/* 区切り */}
            {index < items.length - 1 && (
              <span
                style={{
                  color: "rgba(255, 255, 255, 0.2)",
                  marginLeft: 30,
                }}
              >
                |
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ============================================
// ブランドウォーターマーク
// ============================================
interface BrandWatermarkProps {
  text?: string;
  position?: "top-right" | "bottom-right" | "top-left" | "bottom-left";
  startFrame?: number;
}

export const BrandWatermark: React.FC<BrandWatermarkProps> = ({
  text = "SmartIR",
  position = "bottom-right",
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 60 },
  });

  const positionStyle = {
    "top-right": { top: 60, right: 60 },
    "bottom-right": { bottom: 40, right: 60 },
    "top-left": { top: 60, left: 60 },
    "bottom-left": { bottom: 40, left: 60 },
  }[position];

  return (
    <div
      style={{
        position: "absolute",
        ...positionStyle,
        display: "flex",
        alignItems: "center",
        gap: 12,
        opacity: fadeIn * 0.7,
      }}
    >
      {/* ロゴマーク */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 8,
          background: `linear-gradient(135deg, ${COLORS.primary} 0%, ${COLORS.secondary} 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 12px ${COLORS.primary}40`,
        }}
      >
        <span
          style={{
            color: COLORS.white,
            fontSize: 18,
            fontWeight: 700,
          }}
        >
          S
        </span>
      </div>

      {/* ブランド名 */}
      <span
        style={{
          color: COLORS.white,
          fontSize: 18,
          fontWeight: 600,
          letterSpacing: "0.05em",
        }}
      >
        {text}
      </span>
    </div>
  );
};

// ============================================
// プログレスバー
// ============================================
interface ProgressBarProps {
  progress: number; // 0-1
  label?: string;
  showPercentage?: boolean;
  startFrame?: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  label,
  showPercentage = true,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 100 },
  });

  const barProgress = interpolate(animFrame, [10, 50], [0, progress], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 20,
        left: 60,
        right: 60,
        opacity: fadeIn,
      }}
    >
      {/* ラベルとパーセンテージ */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        {label && (
          <span
            style={{
              color: "rgba(255, 255, 255, 0.7)",
              fontSize: 13,
            }}
          >
            {label}
          </span>
        )}
        {showPercentage && (
          <span
            style={{
              color: COLORS.secondary,
              fontSize: 13,
              fontWeight: 600,
              fontFamily: "monospace",
            }}
          >
            {Math.round(barProgress * 100)}%
          </span>
        )}
      </div>

      {/* バー */}
      <div
        style={{
          height: 6,
          background: "rgba(255, 255, 255, 0.1)",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${barProgress * 100}%`,
            background: `linear-gradient(90deg, ${COLORS.primary} 0%, ${COLORS.secondary} 100%)`,
            borderRadius: 3,
            boxShadow: `0 0 10px ${COLORS.secondary}60`,
          }}
        />
      </div>
    </div>
  );
};

// ============================================
// エクスポート
// ============================================
export default {
  SpeakerLowerThird,
  TopicLowerThird,
  SourceLowerThird,
  HeaderTicker,
  BrandWatermark,
  ProgressBar,
};
