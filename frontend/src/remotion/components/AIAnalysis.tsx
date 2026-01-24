import React, { useMemo } from "react";
import {
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";

// ==============================
// 型定義
// ==============================

/** センチメント種別 */
type SentimentType = "bullish" | "neutral" | "bearish";

/** リスクレベル */
type RiskLevel = "low" | "medium" | "high";

/** インサイトの重要度 */
type InsightPriority = "high" | "medium" | "low";

/** キーインサイトのデータ */
interface KeyInsight {
  text: string;
  priority: InsightPriority;
}

/** AI分析データ */
export interface AIAnalysisData {
  /** センチメント（強気/中立/弱気） */
  sentiment: SentimentType;
  /** センチメントスコア（0-100、50が中立） */
  sentimentScore: number;
  /** 総合AIスコア（0-100） */
  overallScore: number;
  /** ファンダメンタル評価（0-100） */
  fundamentalScore: number;
  /** テクニカル評価（0-100） */
  technicalScore: number;
  /** ニュースセンチメント（0-100） */
  newsSentimentScore: number;
  /** キーインサイト */
  insights: KeyInsight[];
  /** リスクレベル */
  riskLevel: RiskLevel;
  /** リスク警告メッセージ */
  riskMessage?: string;
  /** イリスの見解（AI予測テキスト） */
  irisOpinion: string;
}

/** AIAnalysisコンポーネントのプロパティ */
interface AIAnalysisProps {
  /** 分析データ */
  data: AIAnalysisData;
  /** アニメーション開始フレーム */
  startFrame?: number;
  /** 表示セクション（省略時は全て表示） */
  visibleSections?: (
    | "sentiment"
    | "scores"
    | "insights"
    | "risk"
    | "prediction"
  )[];
}

// ==============================
// 定数
// ==============================

const COLORS = {
  bullish: "#22c55e", // green-500
  neutral: "#f59e0b", // amber-500
  bearish: "#ef4444", // red-500
  highPriority: "#ef4444",
  mediumPriority: "#f59e0b",
  lowPriority: "#3b82f6",
  riskLow: "#22c55e",
  riskMedium: "#f59e0b",
  riskHigh: "#ef4444",
  accent: "#667eea",
  accentSecondary: "#764ba2",
};

const SENTIMENT_LABELS: Record<SentimentType, string> = {
  bullish: "強気",
  neutral: "中立",
  bearish: "弱気",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "低リスク",
  medium: "中リスク",
  high: "高リスク",
};

// ==============================
// ユーティリティ関数
// ==============================

const getSentimentColor = (sentiment: SentimentType): string => {
  return COLORS[sentiment];
};

const getRiskColor = (level: RiskLevel): string => {
  const riskColors: Record<RiskLevel, string> = {
    low: COLORS.riskLow,
    medium: COLORS.riskMedium,
    high: COLORS.riskHigh,
  };
  return riskColors[level];
};

const getPriorityColor = (priority: InsightPriority): string => {
  const priorityColors: Record<InsightPriority, string> = {
    high: COLORS.highPriority,
    medium: COLORS.mediumPriority,
    low: COLORS.lowPriority,
  };
  return priorityColors[priority];
};

// ==============================
// サブコンポーネント: Glassコンテナ
// ==============================

const GlassContainer: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  opacity?: number;
}> = ({ children, style = {}, opacity = 1 }) => (
  <div
    style={{
      background: "rgba(255, 255, 255, 0.05)",
      backdropFilter: "blur(20px)",
      borderRadius: 20,
      border: "1px solid rgba(255, 255, 255, 0.1)",
      boxShadow: `
        0 8px 32px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.1)
      `,
      padding: 24,
      opacity,
      ...style,
    }}
  >
    {children}
  </div>
);

// ==============================
// サブコンポーネント: センチメントゲージ
// ==============================

const SentimentGauge: React.FC<{
  sentiment: SentimentType;
  score: number;
  animationProgress: number;
}> = ({ sentiment, score, animationProgress }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ゲージの角度計算（-90度〜90度、0が中央）
  // score: 0=bearish(-90deg), 50=neutral(0deg), 100=bullish(90deg)
  const targetAngle = interpolate(score, [0, 100], [-90, 90]);
  const currentAngle = interpolate(animationProgress, [0, 1], [0, targetAngle]);

  // 針のアニメーション（オーバーシュート付きspring）
  const needleSpring = spring({
    frame,
    fps,
    config: {
      damping: 12,
      stiffness: 60,
    },
  });

  const needleAngle = currentAngle * needleSpring;

  // グローエフェクト
  const glowIntensity = interpolate(
    Math.sin(frame * 0.08),
    [-1, 1],
    [0.5, 1]
  );

  const sentimentColor = getSentimentColor(sentiment);

  return (
    <GlassContainer
      style={{ width: 280, height: 200 }}
      opacity={animationProgress}
    >
      {/* ヘッダー */}
      <div
        style={{
          marginBottom: 12,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: sentimentColor,
            boxShadow: `0 0 ${8 * glowIntensity}px ${sentimentColor}`,
          }}
        />
        <span
          style={{
            color: "rgba(255, 255, 255, 0.6)",
            fontSize: 14,
            fontWeight: 500,
            letterSpacing: "0.05em",
          }}
        >
          センチメント分析
        </span>
      </div>

      {/* ゲージ */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: 100,
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-end",
        }}
      >
        <svg width={200} height={110} viewBox="0 0 200 110">
          {/* 背景アーク */}
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={COLORS.bearish} />
              <stop offset="50%" stopColor={COLORS.neutral} />
              <stop offset="100%" stopColor={COLORS.bullish} />
            </linearGradient>
          </defs>

          {/* アーク背景 */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="rgba(255, 255, 255, 0.1)"
            strokeWidth={12}
            strokeLinecap="round"
          />

          {/* カラフルなアーク */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth={8}
            strokeLinecap="round"
            opacity={0.7}
          />

          {/* 針 */}
          <g transform={`rotate(${needleAngle}, 100, 100)`}>
            {/* 針のグロー */}
            <line
              x1={100}
              y1={100}
              x2={100}
              y2={35}
              stroke={sentimentColor}
              strokeWidth={6}
              strokeLinecap="round"
              opacity={0.3}
              filter="blur(4px)"
            />
            {/* 針本体 */}
            <line
              x1={100}
              y1={100}
              x2={100}
              y2={40}
              stroke="white"
              strokeWidth={3}
              strokeLinecap="round"
            />
            {/* 針の先端 */}
            <circle cx={100} cy={40} r={4} fill={sentimentColor} />
          </g>

          {/* 中心点 */}
          <circle cx={100} cy={100} r={8} fill="white" />
          <circle cx={100} cy={100} r={5} fill={sentimentColor} />

          {/* ラベル */}
          <text x={20} y={108} fill="rgba(255,255,255,0.5)" fontSize={10} textAnchor="middle">
            弱気
          </text>
          <text x={100} y={25} fill="rgba(255,255,255,0.5)" fontSize={10} textAnchor="middle">
            中立
          </text>
          <text x={180} y={108} fill="rgba(255,255,255,0.5)" fontSize={10} textAnchor="middle">
            強気
          </text>
        </svg>
      </div>

      {/* センチメントラベル */}
      <div
        style={{
          textAlign: "center",
          marginTop: 8,
        }}
      >
        <span
          style={{
            color: sentimentColor,
            fontSize: 24,
            fontWeight: "bold",
            textShadow: `0 0 ${12 * glowIntensity}px ${sentimentColor}`,
          }}
        >
          {SENTIMENT_LABELS[sentiment]}
        </span>
      </div>
    </GlassContainer>
  );
};

// ==============================
// サブコンポーネント: AIスコア表示
// ==============================

interface ScoreItemProps {
  label: string;
  score: number;
  animationProgress: number;
  delay: number;
  color?: string;
}

const ScoreItem: React.FC<ScoreItemProps> = ({
  label,
  score,
  animationProgress,
  delay,
  color = COLORS.accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 遅延付きアニメーション
  const delayedProgress = Math.max(0, animationProgress - delay);
  const normalizedProgress = Math.min(1, delayedProgress / (1 - delay));

  // スコアのカウントアップ
  const displayScore = Math.round(score * normalizedProgress);

  // プログレスバーの幅
  const barWidth = interpolate(normalizedProgress, [0, 1], [0, score]);

  // グローエフェクト
  const glowIntensity = interpolate(
    Math.sin(frame * 0.1),
    [-1, 1],
    [0.6, 1]
  );

  return (
    <div
      style={{
        marginBottom: 16,
        opacity: normalizedProgress,
        transform: `translateX(${interpolate(normalizedProgress, [0, 1], [-20, 0])}px)`,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <span
          style={{
            color: "rgba(255, 255, 255, 0.7)",
            fontSize: 14,
          }}
        >
          {label}
        </span>
        <span
          style={{
            color: "white",
            fontSize: 18,
            fontWeight: "bold",
            fontFamily: "monospace",
          }}
        >
          {displayScore}
        </span>
      </div>
      {/* プログレスバー */}
      <div
        style={{
          width: "100%",
          height: 8,
          backgroundColor: "rgba(255, 255, 255, 0.1)",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${barWidth}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${color}, ${color}dd)`,
            borderRadius: 4,
            boxShadow: `0 0 ${8 * glowIntensity}px ${color}`,
            transition: "width 0.1s ease-out",
          }}
        />
      </div>
    </div>
  );
};

const AIScores: React.FC<{
  overallScore: number;
  fundamentalScore: number;
  technicalScore: number;
  newsSentimentScore: number;
  animationProgress: number;
}> = ({
  overallScore,
  fundamentalScore,
  technicalScore,
  newsSentimentScore,
  animationProgress,
}) => {
  const frame = useCurrentFrame();

  // 総合スコアのグローエフェクト
  const glowIntensity = interpolate(
    Math.sin(frame * 0.08),
    [-1, 1],
    [0.5, 1]
  );

  // スコアに応じた色
  const getScoreColor = (score: number): string => {
    if (score >= 70) return COLORS.bullish;
    if (score >= 40) return COLORS.neutral;
    return COLORS.bearish;
  };

  const overallColor = getScoreColor(overallScore);

  return (
    <GlassContainer
      style={{ width: 280, flex: 1 }}
      opacity={animationProgress}
    >
      {/* ヘッダー */}
      <div
        style={{
          marginBottom: 20,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
            fill={COLORS.accent}
          />
        </svg>
        <span
          style={{
            color: "rgba(255, 255, 255, 0.6)",
            fontSize: 14,
            fontWeight: 500,
            letterSpacing: "0.05em",
          }}
        >
          AIスコア
        </span>
      </div>

      {/* 総合スコア（大きく表示） */}
      <div
        style={{
          textAlign: "center",
          marginBottom: 24,
        }}
      >
        <div
          style={{
            fontSize: 56,
            fontWeight: "bold",
            fontFamily: "monospace",
            color: overallColor,
            textShadow: `0 0 ${20 * glowIntensity}px ${overallColor}`,
            lineHeight: 1,
          }}
        >
          {Math.round(overallScore * animationProgress)}
        </div>
        <div
          style={{
            color: "rgba(255, 255, 255, 0.5)",
            fontSize: 12,
            marginTop: 4,
          }}
        >
          総合スコア
        </div>
      </div>

      {/* 個別スコア */}
      <ScoreItem
        label="ファンダメンタル"
        score={fundamentalScore}
        animationProgress={animationProgress}
        delay={0.1}
        color="#3b82f6"
      />
      <ScoreItem
        label="テクニカル"
        score={technicalScore}
        animationProgress={animationProgress}
        delay={0.2}
        color="#8b5cf6"
      />
      <ScoreItem
        label="ニュースセンチメント"
        score={newsSentimentScore}
        animationProgress={animationProgress}
        delay={0.3}
        color="#06b6d4"
      />
    </GlassContainer>
  );
};

// ==============================
// サブコンポーネント: キーインサイト
// ==============================

const KeyInsights: React.FC<{
  insights: KeyInsight[];
  animationProgress: number;
}> = ({ insights, animationProgress }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <GlassContainer
      style={{ flex: 1, minHeight: 200 }}
      opacity={animationProgress}
    >
      {/* ヘッダー */}
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
          <path
            d="M9 21H15M12 3C8.68629 3 6 5.68629 6 9C6 11.5 7.5 13.5 9.5 14.5V17C9.5 17.5523 9.94772 18 10.5 18H13.5C14.0523 18 14.5 17.5523 14.5 17V14.5C16.5 13.5 18 11.5 18 9C18 5.68629 15.3137 3 12 3Z"
            stroke={COLORS.accent}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span
          style={{
            color: "rgba(255, 255, 255, 0.6)",
            fontSize: 14,
            fontWeight: 500,
            letterSpacing: "0.05em",
          }}
        >
          注目ポイント
        </span>
      </div>

      {/* インサイトリスト */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {insights.map((insight, index) => {
          // 各アイテムの遅延アニメーション
          const itemDelay = 0.15 * index;
          const itemProgress = Math.max(0, animationProgress - itemDelay);
          const normalizedProgress = Math.min(1, itemProgress / (1 - itemDelay));

          const priorityColor = getPriorityColor(insight.priority);

          // フェードイン + スライドイン
          const slideX = interpolate(normalizedProgress, [0, 1], [-30, 0]);

          return (
            <div
              key={index}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
                opacity: normalizedProgress,
                transform: `translateX(${slideX}px)`,
              }}
            >
              {/* 優先度インジケーター */}
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  backgroundColor: priorityColor,
                  marginTop: 8,
                  boxShadow: `0 0 8px ${priorityColor}`,
                  flexShrink: 0,
                }}
              />
              {/* テキスト */}
              <p
                style={{
                  margin: 0,
                  color: "rgba(255, 255, 255, 0.85)",
                  fontSize: 15,
                  lineHeight: 1.5,
                }}
              >
                {insight.text}
              </p>
            </div>
          );
        })}
      </div>
    </GlassContainer>
  );
};

// ==============================
// サブコンポーネント: リスク警告
// ==============================

const RiskWarning: React.FC<{
  level: RiskLevel;
  message?: string;
  animationProgress: number;
}> = ({ level, message, animationProgress }) => {
  const frame = useCurrentFrame();

  const riskColor = getRiskColor(level);

  // パルスアニメーション（高リスク時）
  const pulseOpacity =
    level === "high"
      ? interpolate(Math.sin(frame * 0.15), [-1, 1], [0.6, 1])
      : 1;

  // インジケーターの位置
  const indicatorPosition: Record<RiskLevel, number> = {
    low: 0,
    medium: 1,
    high: 2,
  };

  return (
    <GlassContainer
      style={{
        width: 280,
        borderColor:
          level === "high" ? `rgba(239, 68, 68, 0.3)` : "rgba(255, 255, 255, 0.1)",
      }}
      opacity={animationProgress}
    >
      {/* ヘッダー */}
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <svg
          width={16}
          height={16}
          viewBox="0 0 24 24"
          fill="none"
          style={{ opacity: pulseOpacity }}
        >
          <path
            d="M12 9V13M12 17H12.01M5.07183 19H18.9282C20.4678 19 21.4301 17.3333 20.6603 16L13.7321 4C12.9623 2.66667 11.0377 2.66667 10.2679 4L3.33975 16C2.56995 17.3333 3.53223 19 5.07183 19Z"
            stroke={riskColor}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span
          style={{
            color: "rgba(255, 255, 255, 0.6)",
            fontSize: 14,
            fontWeight: 500,
            letterSpacing: "0.05em",
          }}
        >
          リスク警告
        </span>
      </div>

      {/* リスクレベルインジケーター */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        {(["low", "medium", "high"] as RiskLevel[]).map((l, index) => {
          const isActive = indicatorPosition[level] >= index;
          const color = getRiskColor(l);

          return (
            <div
              key={l}
              style={{
                flex: 1,
                height: 8,
                backgroundColor: isActive
                  ? color
                  : "rgba(255, 255, 255, 0.1)",
                marginRight: index < 2 ? 4 : 0,
                borderRadius: 4,
                opacity: isActive ? pulseOpacity : 0.5,
                boxShadow: isActive ? `0 0 8px ${color}` : "none",
                transition: "all 0.3s ease",
              }}
            />
          );
        })}
      </div>

      {/* リスクレベルラベル */}
      <div
        style={{
          textAlign: "center",
          marginBottom: message ? 12 : 0,
        }}
      >
        <span
          style={{
            color: riskColor,
            fontSize: 20,
            fontWeight: "bold",
            opacity: pulseOpacity,
          }}
        >
          {RISK_LABELS[level]}
        </span>
      </div>

      {/* 警告メッセージ */}
      {message && (
        <p
          style={{
            margin: 0,
            color: "rgba(255, 255, 255, 0.7)",
            fontSize: 13,
            lineHeight: 1.5,
            textAlign: "center",
          }}
        >
          {message}
        </p>
      )}
    </GlassContainer>
  );
};

// ==============================
// サブコンポーネント: AI予測（イリスの見解）
// ==============================

const IrisPrediction: React.FC<{
  opinion: string;
  animationProgress: number;
}> = ({ opinion, animationProgress }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // タイプライターエフェクト
  const charsToShow = Math.floor(
    opinion.length * interpolate(animationProgress, [0.2, 1], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );

  const displayText = opinion.slice(0, charsToShow);

  // カーソル点滅
  const cursorOpacity = interpolate(
    Math.sin(frame * 0.2),
    [-1, 1],
    [0, 1]
  );

  // グローエフェクト
  const glowIntensity = interpolate(
    Math.sin(frame * 0.05),
    [-1, 1],
    [0.5, 1]
  );

  return (
    <GlassContainer
      style={{
        flex: 1,
        background: `
          linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%),
          rgba(255, 255, 255, 0.03)
        `,
      }}
      opacity={animationProgress}
    >
      {/* ヘッダー */}
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        {/* イリスアイコン */}
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accentSecondary})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: `0 0 ${12 * glowIntensity}px ${COLORS.accent}`,
          }}
        >
          <svg width={18} height={18} viewBox="0 0 24 24" fill="white">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
          </svg>
        </div>
        <div>
          <span
            style={{
              color: "white",
              fontSize: 16,
              fontWeight: 600,
              display: "block",
            }}
          >
            イリスの見解
          </span>
          <span
            style={{
              color: "rgba(255, 255, 255, 0.5)",
              fontSize: 11,
            }}
          >
            AI分析レポート
          </span>
        </div>
      </div>

      {/* 見解テキスト（タイプライター風） */}
      <div
        style={{
          position: "relative",
          minHeight: 80,
        }}
      >
        <p
          style={{
            margin: 0,
            color: "rgba(255, 255, 255, 0.9)",
            fontSize: 16,
            lineHeight: 1.7,
            letterSpacing: "0.02em",
          }}
        >
          {displayText}
          {/* カーソル */}
          {charsToShow < opinion.length && (
            <span
              style={{
                display: "inline-block",
                width: 2,
                height: 18,
                backgroundColor: COLORS.accent,
                marginLeft: 2,
                opacity: cursorOpacity,
                verticalAlign: "text-bottom",
              }}
            />
          )}
        </p>
      </div>

      {/* 装飾ライン */}
      <div
        style={{
          marginTop: 16,
          height: 2,
          background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accentSecondary}, transparent)`,
          borderRadius: 1,
          opacity: 0.5,
        }}
      />
    </GlassContainer>
  );
};

// ==============================
// メインコンポーネント: AIAnalysis
// ==============================

export const AIAnalysis: React.FC<AIAnalysisProps> = ({
  data,
  startFrame = 0,
  visibleSections = ["sentiment", "scores", "insights", "risk", "prediction"],
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // アニメーション進行度の計算
  const animationFrame = Math.max(0, frame - startFrame);

  // 全体のフェードイン
  const fadeIn = spring({
    frame: animationFrame,
    fps,
    config: {
      damping: 20,
      stiffness: 80,
    },
  });

  // セクション別の進行度（遅延を付けて順番に表示）
  const sectionProgress = useMemo(() => {
    const baseProgress = interpolate(animationFrame, [0, 90], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

    return {
      sentiment: Math.min(1, baseProgress * 1.5),
      scores: Math.min(1, Math.max(0, (baseProgress - 0.1) * 1.5)),
      insights: Math.min(1, Math.max(0, (baseProgress - 0.2) * 1.5)),
      risk: Math.min(1, Math.max(0, (baseProgress - 0.3) * 1.5)),
      prediction: Math.min(1, Math.max(0, (baseProgress - 0.4) * 1.3)),
    };
  }, [animationFrame]);

  const shouldShow = (section: string) => visibleSections.includes(section as typeof visibleSections[number]);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        padding: 40,
        display: "flex",
        flexDirection: "column",
        gap: 20,
        opacity: fadeIn,
      }}
    >
      {/* 上段: センチメント + スコア */}
      <div style={{ display: "flex", gap: 20 }}>
        {shouldShow("sentiment") && (
          <SentimentGauge
            sentiment={data.sentiment}
            score={data.sentimentScore}
            animationProgress={sectionProgress.sentiment}
          />
        )}
        {shouldShow("scores") && (
          <AIScores
            overallScore={data.overallScore}
            fundamentalScore={data.fundamentalScore}
            technicalScore={data.technicalScore}
            newsSentimentScore={data.newsSentimentScore}
            animationProgress={sectionProgress.scores}
          />
        )}
      </div>

      {/* 中段: インサイト + リスク */}
      <div style={{ display: "flex", gap: 20, flex: 1 }}>
        {shouldShow("insights") && (
          <KeyInsights
            insights={data.insights}
            animationProgress={sectionProgress.insights}
          />
        )}
        {shouldShow("risk") && (
          <RiskWarning
            level={data.riskLevel}
            message={data.riskMessage}
            animationProgress={sectionProgress.risk}
          />
        )}
      </div>

      {/* 下段: イリスの見解 */}
      {shouldShow("prediction") && (
        <IrisPrediction
          opinion={data.irisOpinion}
          animationProgress={sectionProgress.prediction}
        />
      )}
    </div>
  );
};

// ==============================
// デフォルトエクスポート
// ==============================

export default AIAnalysis;
