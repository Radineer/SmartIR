import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

// チャートデータの型
interface ChartData {
  label: string;
  price: number;
  previousClose: number;
  change: number;
  changePercent: number;
  dataPoints: number[]; // 正規化された値（0-1）
}

// モックデータ
const MARKET_DATA: Record<string, ChartData> = {
  nikkei: {
    label: "日経平均株価",
    price: 39850,
    previousClose: 39565,
    change: 285,
    changePercent: 0.72,
    dataPoints: [0.25, 0.3, 0.32, 0.38, 0.42, 0.45, 0.5, 0.52, 0.55, 0.6, 0.58, 0.65, 0.7, 0.72, 0.75, 0.78, 0.8, 0.82, 0.85, 0.88],
  },
  topix: {
    label: "TOPIX",
    price: 2785,
    previousClose: 2767,
    change: 18,
    changePercent: 0.65,
    dataPoints: [0.2, 0.25, 0.28, 0.32, 0.35, 0.4, 0.45, 0.48, 0.52, 0.55, 0.58, 0.62, 0.65, 0.68, 0.72, 0.75, 0.78, 0.82, 0.85, 0.88],
  },
  dowjones: {
    label: "NYダウ",
    price: 42850,
    previousClose: 42650,
    change: 200,
    changePercent: 0.47,
    dataPoints: [0.2, 0.25, 0.3, 0.32, 0.38, 0.42, 0.48, 0.52, 0.55, 0.58, 0.62, 0.65, 0.68, 0.72, 0.75, 0.78, 0.82, 0.85, 0.88, 0.9],
  },
  usdjpy: {
    label: "USD/JPY",
    price: 157.25,
    previousClose: 156.80,
    change: 0.45,
    changePercent: 0.29,
    dataPoints: [0.4, 0.42, 0.45, 0.48, 0.5, 0.52, 0.55, 0.58, 0.6, 0.62, 0.65, 0.63, 0.68, 0.7, 0.72, 0.75, 0.73, 0.78, 0.8, 0.82],
  },
  nasdaq: {
    label: "NASDAQ",
    price: 19250,
    previousClose: 19080,
    change: 170,
    changePercent: 0.89,
    dataPoints: [0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.58, 0.65, 0.7, 0.75, 0.72, 0.78, 0.82, 0.85, 0.88, 0.9, 0.92, 0.95],
  },
  sp500: {
    label: "S&P 500",
    price: 5920,
    previousClose: 5890,
    change: 30,
    changePercent: 0.51,
    dataPoints: [0.35, 0.38, 0.42, 0.45, 0.48, 0.52, 0.55, 0.58, 0.6, 0.62, 0.65, 0.68, 0.7, 0.72, 0.75, 0.78, 0.8, 0.82, 0.84, 0.86],
  },
};

interface MarketChartProps {
  marketType?: "nikkei" | "topix" | "dowjones" | "usdjpy" | "nasdaq" | "sp500";
  startFrame?: number; // アニメーション開始フレーム（Sequence内での相対位置）
}

// US市場かどうかを判定
const isUSMarket = (marketType: string): boolean => {
  return ["dowjones", "nasdaq", "sp500"].includes(marketType);
};

// 価格をフォーマットする関数
const formatPrice = (price: number, marketType: string): string => {
  if (marketType === "usdjpy") {
    return `¥${price.toFixed(2)}`;
  }
  if (isUSMarket(marketType)) {
    return `$${price.toLocaleString("en-US")}`;
  }
  return `${price.toLocaleString("ja-JP")}円`;
};

// 変化をフォーマットする関数
const formatChange = (change: number, changePercent: number, marketType: string): string => {
  const sign = change >= 0 ? "+" : "";
  if (marketType === "usdjpy") {
    return `${sign}${change.toFixed(2)} (${sign}${changePercent.toFixed(2)}%)`;
  }
  if (isUSMarket(marketType)) {
    return `${sign}$${change.toLocaleString("en-US")} (${sign}${changePercent.toFixed(2)}%)`;
  }
  return `${sign}${change.toLocaleString("ja-JP")}円 (${sign}${changePercent.toFixed(2)}%)`;
};

// SVGパスを生成する関数
const generateChartPath = (
  dataPoints: number[],
  width: number,
  height: number,
  padding: number
): string => {
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;
  const stepX = chartWidth / (dataPoints.length - 1);

  const points = dataPoints.map((value, index) => {
    const x = padding + index * stepX;
    const y = padding + chartHeight * (1 - value);
    return { x, y };
  });

  // スムーズな曲線を生成（ベジェ曲線）
  let path = `M ${points[0].x} ${points[0].y}`;

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const cp1x = prev.x + stepX * 0.5;
    const cp1y = prev.y;
    const cp2x = curr.x - stepX * 0.5;
    const cp2y = curr.y;
    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${curr.x} ${curr.y}`;
  }

  return path;
};

// グリッド線を生成
const GridLines: React.FC<{
  width: number;
  height: number;
  padding: number;
}> = ({ width, height, padding }) => {
  const gridLines = [];
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;

  // 水平グリッド線
  for (let i = 0; i <= 4; i++) {
    const y = padding + (chartHeight / 4) * i;
    gridLines.push(
      <line
        key={`h-${i}`}
        x1={padding}
        y1={y}
        x2={width - padding}
        y2={y}
        stroke="rgba(255, 255, 255, 0.1)"
        strokeWidth={1}
        strokeDasharray={i === 4 ? "none" : "4 4"}
      />
    );
  }

  // 垂直グリッド線
  for (let i = 0; i <= 4; i++) {
    const x = padding + (chartWidth / 4) * i;
    gridLines.push(
      <line
        key={`v-${i}`}
        x1={x}
        y1={padding}
        x2={x}
        y2={height - padding}
        stroke="rgba(255, 255, 255, 0.05)"
        strokeWidth={1}
        strokeDasharray="4 4"
      />
    );
  }

  return <>{gridLines}</>;
};

export const MarketChart: React.FC<MarketChartProps> = ({
  marketType = "nikkei",
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const data = MARKET_DATA[marketType];
  const isPositive = data.change >= 0;

  // チャートの色
  const chartColor = isPositive ? "#22c55e" : "#ef4444"; // green-500 / red-500
  const chartGradientId = `chartGradient-${marketType}`;
  const chartGlowId = `chartGlow-${marketType}`;

  // チャートサイズ（大きめに設定）
  const chartWidth = 640;
  const chartHeight = 400;
  const padding = 30;

  // アニメーション
  const animationFrame = Math.max(0, frame - startFrame);

  // ライン描画のプログレス（0〜1）
  const lineProgress = interpolate(animationFrame, [0, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // フェードインアニメーション
  const fadeIn = spring({
    frame: animationFrame,
    fps,
    config: {
      damping: 20,
      stiffness: 80,
    },
  });

  // スケールアニメーション
  const scaleIn = spring({
    frame: animationFrame,
    fps,
    config: {
      damping: 15,
      stiffness: 100,
    },
  });

  // 価格カウントアップアニメーション
  const priceProgress = interpolate(animationFrame, [20, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const displayPrice = data.previousClose + (data.change * priceProgress);

  // パスの生成
  const chartPath = generateChartPath(data.dataPoints, chartWidth, chartHeight, padding);

  // パスの長さを推定（アニメーション用）
  const estimatedPathLength = 1000;

  return (
    <div
      style={{
        width: chartWidth + 100,
        height: chartHeight + 140,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeIn,
        transform: `scale(${interpolate(scaleIn, [0, 1], [0.9, 1])})`,
      }}
    >
      {/* Glassスタイルのコンテナ */}
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(20px)",
          borderRadius: 24,
          border: "1px solid rgba(255, 255, 255, 0.1)",
          boxShadow: `
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.1)
          `,
          padding: 32,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* ヘッダー */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 16,
          }}
        >
          {/* ラベル */}
          <div>
            <p
              style={{
                margin: 0,
                color: "rgba(255, 255, 255, 0.6)",
                fontSize: 18,
                fontWeight: 500,
                letterSpacing: "0.05em",
              }}
            >
              {data.label}
            </p>
            {/* 価格 */}
            <p
              style={{
                margin: "6px 0 0 0",
                color: "white",
                fontSize: 42,
                fontWeight: "bold",
                fontFamily: "monospace",
                letterSpacing: "-0.02em",
              }}
            >
              {formatPrice(displayPrice, marketType)}
            </p>
          </div>

          {/* 変化率 */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              opacity: priceProgress,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                color: chartColor,
                fontSize: 22,
                fontWeight: 600,
                fontFamily: "monospace",
              }}
            >
              {/* 矢印 */}
              <svg
                width={20}
                height={20}
                viewBox="0 0 16 16"
                style={{
                  transform: isPositive ? "rotate(0deg)" : "rotate(180deg)",
                }}
              >
                <path
                  d="M8 3 L13 10 L10 10 L10 13 L6 13 L6 10 L3 10 Z"
                  fill={chartColor}
                />
              </svg>
              {formatChange(data.change, data.changePercent, marketType)}
            </div>
            <p
              style={{
                margin: "6px 0 0 0",
                color: "rgba(255, 255, 255, 0.4)",
                fontSize: 14,
              }}
            >
              前日比
            </p>
          </div>
        </div>

        {/* チャート */}
        <div
          style={{
            flex: 1,
            position: "relative",
          }}
        >
          <svg
            width={chartWidth}
            height={chartHeight}
            style={{
              overflow: "visible",
            }}
          >
            {/* グラデーション定義 */}
            <defs>
              <linearGradient id={chartGradientId} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
                <stop offset="100%" stopColor={chartColor} stopOpacity={0} />
              </linearGradient>
              <filter id={chartGlowId} x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* グリッド */}
            <GridLines width={chartWidth} height={chartHeight} padding={padding} />

            {/* 塗りつぶしエリア */}
            <path
              d={`${chartPath} L ${chartWidth - padding} ${chartHeight - padding} L ${padding} ${chartHeight - padding} Z`}
              fill={`url(#${chartGradientId})`}
              opacity={lineProgress}
            />

            {/* チャートライン */}
            <path
              d={chartPath}
              fill="none"
              stroke={chartColor}
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
              filter={`url(#${chartGlowId})`}
              strokeDasharray={estimatedPathLength}
              strokeDashoffset={estimatedPathLength * (1 - lineProgress)}
              style={{
                transition: "none",
              }}
            />

            {/* 終点のドット */}
            {lineProgress > 0.95 && (
              <>
                {/* グロー */}
                <circle
                  cx={chartWidth - padding}
                  cy={padding + (chartHeight - padding * 2) * (1 - data.dataPoints[data.dataPoints.length - 1])}
                  r={12}
                  fill={chartColor}
                  opacity={0.3}
                />
                {/* ドット */}
                <circle
                  cx={chartWidth - padding}
                  cy={padding + (chartHeight - padding * 2) * (1 - data.dataPoints[data.dataPoints.length - 1])}
                  r={6}
                  fill={chartColor}
                  stroke="white"
                  strokeWidth={2}
                />
              </>
            )}
          </svg>
        </div>

        {/* 時間軸ラベル */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 12,
            paddingLeft: padding,
            paddingRight: padding,
          }}
        >
          {["9:00", "10:30", "12:00", "13:30", "15:00"].map((time, index) => (
            <span
              key={index}
              style={{
                color: "rgba(255, 255, 255, 0.3)",
                fontSize: 13,
                fontFamily: "monospace",
              }}
            >
              {time}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MarketChart;
