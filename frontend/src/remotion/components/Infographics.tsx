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
  // チャート用カラー
  chart: [
    "#4f46e5", // インディゴ
    "#06b6d4", // シアン
    "#8b5cf6", // パープル
    "#ec4899", // ピンク
    "#f59e0b", // アンバー
    "#10b981", // エメラルド
    "#6366f1", // インディゴライト
    "#14b8a6", // ティール
  ],
};

// ============================================
// 円グラフ（セクター構成比）
// ============================================
interface PieChartData {
  label: string;
  value: number;
  color?: string;
}

interface PieChartProps {
  data: PieChartData[];
  title?: string;
  size?: number;
  startFrame?: number;
  showLegend?: boolean;
  showValues?: boolean;
}

export const PieChart: React.FC<PieChartProps> = ({
  data,
  title,
  size = 300,
  startFrame = 0,
  showLegend = true,
  showValues = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  const total = data.reduce((sum, item) => sum + item.value, 0);
  const centerX = size / 2;
  const centerY = size / 2;
  const radius = size / 2 - 20;

  // アニメーション進捗
  const progress = interpolate(animFrame, [0, 60], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // フェードイン
  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  // パスを生成
  const generatePiePath = (
    startAngle: number,
    endAngle: number,
    animatedEndAngle: number
  ): string => {
    const actualEndAngle = startAngle + (endAngle - startAngle) * progress;

    if (actualEndAngle - startAngle >= 2 * Math.PI * 0.9999) {
      // 完全な円の場合
      return `
        M ${centerX} ${centerY - radius}
        A ${radius} ${radius} 0 1 1 ${centerX - 0.001} ${centerY - radius}
        A ${radius} ${radius} 0 1 1 ${centerX} ${centerY - radius}
      `;
    }

    const startX = centerX + radius * Math.cos(startAngle - Math.PI / 2);
    const startY = centerY + radius * Math.sin(startAngle - Math.PI / 2);
    const endX = centerX + radius * Math.cos(actualEndAngle - Math.PI / 2);
    const endY = centerY + radius * Math.sin(actualEndAngle - Math.PI / 2);
    const largeArcFlag = actualEndAngle - startAngle > Math.PI ? 1 : 0;

    return `
      M ${centerX} ${centerY}
      L ${startX} ${startY}
      A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY}
      Z
    `;
  };

  let currentAngle = 0;
  const segments = data.map((item, index) => {
    const angle = (item.value / total) * 2 * Math.PI;
    const startAngle = currentAngle;
    const endAngle = currentAngle + angle;
    currentAngle = endAngle;

    return {
      ...item,
      startAngle,
      endAngle,
      color: item.color || COLORS.chart[index % COLORS.chart.length],
      percentage: (item.value / total) * 100,
    };
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 20,
        opacity: fadeIn,
      }}
    >
      {/* タイトル */}
      {title && (
        <div
          style={{
            color: COLORS.white,
            fontSize: 24,
            fontWeight: 600,
            marginBottom: 10,
          }}
        >
          {title}
        </div>
      )}

      <div style={{ display: "flex", gap: 40, alignItems: "center" }}>
        {/* 円グラフ */}
        <div style={{ position: "relative" }}>
          <svg width={size} height={size}>
            <defs>
              {segments.map((segment, i) => (
                <filter
                  key={`shadow-${i}`}
                  id={`pie-shadow-${i}`}
                  x="-50%"
                  y="-50%"
                  width="200%"
                  height="200%"
                >
                  <feDropShadow
                    dx="0"
                    dy="2"
                    stdDeviation="4"
                    floodColor={segment.color}
                    floodOpacity="0.3"
                  />
                </filter>
              ))}
            </defs>

            {segments.map((segment, index) => (
              <path
                key={index}
                d={generatePiePath(
                  segment.startAngle,
                  segment.endAngle,
                  segment.endAngle
                )}
                fill={segment.color}
                filter={`url(#pie-shadow-${index})`}
                style={{
                  transition: "none",
                }}
              />
            ))}

            {/* 中央の穴（ドーナツ風） */}
            <circle
              cx={centerX}
              cy={centerY}
              r={radius * 0.5}
              fill={COLORS.dark}
            />

            {/* 中央のテキスト */}
            <text
              x={centerX}
              y={centerY - 10}
              textAnchor="middle"
              fill={COLORS.white}
              fontSize={16}
              fontWeight={500}
            >
              合計
            </text>
            <text
              x={centerX}
              y={centerY + 15}
              textAnchor="middle"
              fill={COLORS.secondary}
              fontSize={24}
              fontWeight={700}
            >
              {total.toLocaleString()}
            </text>
          </svg>
        </div>

        {/* 凡例 */}
        {showLegend && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {segments.map((segment, index) => {
              const itemDelay = index * 5;
              const itemProgress = interpolate(
                animFrame - itemDelay,
                [0, 20],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              );

              return (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    opacity: itemProgress,
                    transform: `translateX(${interpolate(itemProgress, [0, 1], [20, 0])}px)`,
                  }}
                >
                  {/* カラーボックス */}
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: 4,
                      backgroundColor: segment.color,
                      boxShadow: `0 2px 8px ${segment.color}40`,
                    }}
                  />

                  {/* ラベル */}
                  <span
                    style={{
                      color: COLORS.white,
                      fontSize: 16,
                      minWidth: 100,
                    }}
                  >
                    {segment.label}
                  </span>

                  {/* 値 */}
                  {showValues && (
                    <span
                      style={{
                        color: COLORS.secondary,
                        fontSize: 16,
                        fontWeight: 600,
                        fontFamily: "monospace",
                      }}
                    >
                      {segment.percentage.toFixed(1)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================
// 棒グラフ（ランキング）
// ============================================
interface BarChartData {
  label: string;
  value: number;
  color?: string;
  change?: number; // 変動率
}

interface BarChartProps {
  data: BarChartData[];
  title?: string;
  width?: number;
  barHeight?: number;
  startFrame?: number;
  showRank?: boolean;
  maxBars?: number;
}

export const BarChart: React.FC<BarChartProps> = ({
  data,
  title,
  width = 600,
  barHeight = 40,
  startFrame = 0,
  showRank = true,
  maxBars = 5,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // データを上位N件に絞り、値でソート
  const sortedData = [...data]
    .sort((a, b) => b.value - a.value)
    .slice(0, maxBars);
  const maxValue = Math.max(...sortedData.map((d) => d.value));

  // フェードイン
  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        width,
        opacity: fadeIn,
      }}
    >
      {/* タイトル */}
      {title && (
        <div
          style={{
            color: COLORS.white,
            fontSize: 24,
            fontWeight: 600,
            marginBottom: 10,
          }}
        >
          {title}
        </div>
      )}

      {/* バー */}
      {sortedData.map((item, index) => {
        const barDelay = index * 8;
        const barProgress = interpolate(
          animFrame - barDelay,
          [0, 40],
          [0, 1],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          }
        );

        const barWidth = (item.value / maxValue) * (width - 150) * barProgress;
        const color = item.color || COLORS.chart[index % COLORS.chart.length];

        return (
          <div
            key={index}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              opacity: barProgress,
            }}
          >
            {/* ランク */}
            {showRank && (
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background:
                    index < 3
                      ? `linear-gradient(135deg, ${COLORS.primary} 0%, ${COLORS.secondary} 100%)`
                      : "rgba(255, 255, 255, 0.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: COLORS.white,
                  fontSize: 16,
                  fontWeight: 700,
                }}
              >
                {index + 1}
              </div>
            )}

            {/* ラベル */}
            <div
              style={{
                width: 80,
                color: COLORS.white,
                fontSize: 14,
                fontWeight: 500,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {item.label}
            </div>

            {/* バー */}
            <div
              style={{
                flex: 1,
                height: barHeight,
                backgroundColor: "rgba(255, 255, 255, 0.05)",
                borderRadius: 8,
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div
                style={{
                  width: barWidth,
                  height: "100%",
                  background: `linear-gradient(90deg, ${color} 0%, ${color}99 100%)`,
                  borderRadius: 8,
                  boxShadow: `0 2px 12px ${color}40`,
                  position: "relative",
                }}
              >
                {/* 光沢効果 */}
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "50%",
                    background:
                      "linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%)",
                    borderRadius: "8px 8px 0 0",
                  }}
                />
              </div>
            </div>

            {/* 値 */}
            <div
              style={{
                minWidth: 80,
                textAlign: "right",
              }}
            >
              <span
                style={{
                  color: COLORS.white,
                  fontSize: 16,
                  fontWeight: 600,
                  fontFamily: "monospace",
                }}
              >
                {(item.value * barProgress).toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </span>
              {item.change !== undefined && (
                <span
                  style={{
                    marginLeft: 8,
                    color: item.change >= 0 ? COLORS.positive : COLORS.negative,
                    fontSize: 14,
                    fontFamily: "monospace",
                  }}
                >
                  {item.change >= 0 ? "+" : ""}
                  {item.change.toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ============================================
// 比較表
// ============================================
interface ComparisonTableData {
  metric: string;
  values: Array<{
    value: string | number;
    isHighlight?: boolean;
  }>;
}

interface ComparisonTableProps {
  headers: string[];
  data: ComparisonTableData[];
  title?: string;
  startFrame?: number;
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({
  headers,
  data,
  title,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // フェードイン
  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        opacity: fadeIn,
      }}
    >
      {/* タイトル */}
      {title && (
        <div
          style={{
            color: COLORS.white,
            fontSize: 24,
            fontWeight: 600,
            marginBottom: 10,
          }}
        >
          {title}
        </div>
      )}

      {/* テーブル */}
      <div
        style={{
          background: COLORS.overlay,
          backdropFilter: "blur(20px)",
          borderRadius: 16,
          border: "1px solid rgba(129, 140, 248, 0.2)",
          overflow: "hidden",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
        }}
      >
        {/* ヘッダー */}
        <div
          style={{
            display: "flex",
            background: `linear-gradient(90deg, ${COLORS.primary}40 0%, ${COLORS.secondary}40 100%)`,
            borderBottom: "1px solid rgba(129, 140, 248, 0.2)",
          }}
        >
          <div
            style={{
              flex: 1.5,
              padding: "16px 20px",
              color: "rgba(255, 255, 255, 0.7)",
              fontSize: 14,
              fontWeight: 600,
            }}
          />
          {headers.map((header, index) => (
            <div
              key={index}
              style={{
                flex: 1,
                padding: "16px 20px",
                color: COLORS.white,
                fontSize: 16,
                fontWeight: 600,
                textAlign: "center",
              }}
            >
              {header}
            </div>
          ))}
        </div>

        {/* 行 */}
        {data.map((row, rowIndex) => {
          const rowDelay = rowIndex * 5;
          const rowProgress = interpolate(
            animFrame - rowDelay - 10,
            [0, 20],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          return (
            <div
              key={rowIndex}
              style={{
                display: "flex",
                borderBottom:
                  rowIndex < data.length - 1
                    ? "1px solid rgba(255, 255, 255, 0.05)"
                    : "none",
                opacity: rowProgress,
                transform: `translateY(${interpolate(rowProgress, [0, 1], [10, 0])}px)`,
              }}
            >
              {/* 指標名 */}
              <div
                style={{
                  flex: 1.5,
                  padding: "14px 20px",
                  color: "rgba(255, 255, 255, 0.8)",
                  fontSize: 15,
                  fontWeight: 500,
                }}
              >
                {row.metric}
              </div>

              {/* 値 */}
              {row.values.map((cell, cellIndex) => (
                <div
                  key={cellIndex}
                  style={{
                    flex: 1,
                    padding: "14px 20px",
                    textAlign: "center",
                    color: cell.isHighlight ? COLORS.secondary : COLORS.white,
                    fontSize: 15,
                    fontWeight: cell.isHighlight ? 600 : 400,
                    fontFamily:
                      typeof cell.value === "number" ? "monospace" : "inherit",
                  }}
                >
                  {cell.value}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================
// フロー図
// ============================================
interface FlowNode {
  id: string;
  label: string;
  description?: string;
  icon?: string;
}

interface FlowConnection {
  from: string;
  to: string;
  label?: string;
}

interface FlowDiagramProps {
  nodes: FlowNode[];
  connections?: FlowConnection[];
  title?: string;
  startFrame?: number;
  direction?: "horizontal" | "vertical";
}

export const FlowDiagram: React.FC<FlowDiagramProps> = ({
  nodes,
  connections = [],
  title,
  startFrame = 0,
  direction = "horizontal",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // フェードイン
  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  const isHorizontal = direction === "horizontal";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        alignItems: "center",
        opacity: fadeIn,
      }}
    >
      {/* タイトル */}
      {title && (
        <div
          style={{
            color: COLORS.white,
            fontSize: 24,
            fontWeight: 600,
          }}
        >
          {title}
        </div>
      )}

      {/* フロー */}
      <div
        style={{
          display: "flex",
          flexDirection: isHorizontal ? "row" : "column",
          alignItems: "center",
          gap: 0,
        }}
      >
        {nodes.map((node, index) => {
          const nodeDelay = index * 15;
          const nodeProgress = spring({
            frame: Math.max(0, animFrame - nodeDelay),
            fps,
            config: { damping: 15, stiffness: 100 },
          });

          const showArrow = index < nodes.length - 1;
          const arrowDelay = nodeDelay + 10;
          const arrowProgress = interpolate(
            animFrame - arrowDelay,
            [0, 15],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          return (
            <React.Fragment key={node.id}>
              {/* ノード */}
              <div
                style={{
                  opacity: nodeProgress,
                  transform: `scale(${interpolate(nodeProgress, [0, 1], [0.8, 1])})`,
                }}
              >
                <div
                  style={{
                    background: COLORS.overlay,
                    backdropFilter: "blur(20px)",
                    borderRadius: 16,
                    border: "1px solid rgba(129, 140, 248, 0.3)",
                    padding: "20px 28px",
                    minWidth: 160,
                    textAlign: "center",
                    boxShadow: `
                      0 8px 32px rgba(0, 0, 0, 0.3),
                      0 0 0 1px rgba(129, 140, 248, 0.1)
                    `,
                  }}
                >
                  {/* アイコン */}
                  {node.icon && (
                    <div
                      style={{
                        fontSize: 32,
                        marginBottom: 8,
                      }}
                    >
                      {node.icon}
                    </div>
                  )}

                  {/* ラベル */}
                  <div
                    style={{
                      color: COLORS.white,
                      fontSize: 18,
                      fontWeight: 600,
                      marginBottom: node.description ? 8 : 0,
                    }}
                  >
                    {node.label}
                  </div>

                  {/* 説明 */}
                  {node.description && (
                    <div
                      style={{
                        color: "rgba(255, 255, 255, 0.6)",
                        fontSize: 13,
                        lineHeight: 1.4,
                      }}
                    >
                      {node.description}
                    </div>
                  )}
                </div>
              </div>

              {/* 矢印 */}
              {showArrow && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: isHorizontal ? "0 8px" : "8px 0",
                    opacity: arrowProgress,
                  }}
                >
                  <svg
                    width={isHorizontal ? 60 : 24}
                    height={isHorizontal ? 24 : 60}
                    viewBox={isHorizontal ? "0 0 60 24" : "0 0 24 60"}
                  >
                    {isHorizontal ? (
                      <>
                        <line
                          x1="0"
                          y1="12"
                          x2={40 * arrowProgress}
                          y2="12"
                          stroke={COLORS.secondary}
                          strokeWidth="2"
                          strokeDasharray="4 4"
                        />
                        <polygon
                          points="45,12 35,6 35,18"
                          fill={COLORS.secondary}
                          opacity={arrowProgress}
                        />
                      </>
                    ) : (
                      <>
                        <line
                          x1="12"
                          y1="0"
                          x2="12"
                          y2={40 * arrowProgress}
                          stroke={COLORS.secondary}
                          strokeWidth="2"
                          strokeDasharray="4 4"
                        />
                        <polygon
                          points="12,50 6,40 18,40"
                          fill={COLORS.secondary}
                          opacity={arrowProgress}
                        />
                      </>
                    )}
                  </svg>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

// ============================================
// 統計サマリーカード
// ============================================
interface StatItem {
  label: string;
  value: string | number;
  change?: number;
  icon?: string;
}

interface StatsSummaryProps {
  stats: StatItem[];
  title?: string;
  startFrame?: number;
  columns?: number;
}

export const StatsSummary: React.FC<StatsSummaryProps> = ({
  stats,
  title,
  startFrame = 0,
  columns = 4,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const animFrame = Math.max(0, frame - startFrame);

  // フェードイン
  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 20,
        opacity: fadeIn,
      }}
    >
      {/* タイトル */}
      {title && (
        <div
          style={{
            color: COLORS.white,
            fontSize: 24,
            fontWeight: 600,
          }}
        >
          {title}
        </div>
      )}

      {/* 統計グリッド */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap: 16,
        }}
      >
        {stats.map((stat, index) => {
          const itemDelay = index * 8;
          const itemProgress = spring({
            frame: Math.max(0, animFrame - itemDelay),
            fps,
            config: { damping: 15, stiffness: 100 },
          });

          return (
            <div
              key={index}
              style={{
                background: COLORS.overlay,
                backdropFilter: "blur(20px)",
                borderRadius: 12,
                border: "1px solid rgba(129, 140, 248, 0.2)",
                padding: "20px",
                opacity: itemProgress,
                transform: `translateY(${interpolate(itemProgress, [0, 1], [20, 0])}px)`,
              }}
            >
              {/* アイコンとラベル */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                {stat.icon && (
                  <span style={{ fontSize: 20 }}>{stat.icon}</span>
                )}
                <span
                  style={{
                    color: "rgba(255, 255, 255, 0.6)",
                    fontSize: 14,
                    fontWeight: 500,
                  }}
                >
                  {stat.label}
                </span>
              </div>

              {/* 値 */}
              <div
                style={{
                  color: COLORS.white,
                  fontSize: 28,
                  fontWeight: 700,
                  fontFamily:
                    typeof stat.value === "number" ? "monospace" : "inherit",
                }}
              >
                {stat.value}
              </div>

              {/* 変化率 */}
              {stat.change !== undefined && (
                <div
                  style={{
                    marginTop: 8,
                    color:
                      stat.change >= 0 ? COLORS.positive : COLORS.negative,
                    fontSize: 14,
                    fontWeight: 600,
                    fontFamily: "monospace",
                  }}
                >
                  {stat.change >= 0 ? "+" : ""}
                  {stat.change.toFixed(2)}%
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================
// エクスポート
// ============================================
export default {
  PieChart,
  BarChart,
  ComparisonTable,
  FlowDiagram,
  StatsSummary,
};
