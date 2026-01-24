import React, { useMemo } from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  Audio,
  interpolate,
  spring,
  useVideoConfig,
  Sequence,
  staticFile,
} from "remotion";
import { z } from "zod";
import { VTuberScene } from "../components/VTuberScene";
import { VRMScene } from "../components/VRMCharacter";
import { OpeningScene } from "../components/OpeningScene";
import { EndingScene } from "../components/EndingScene";
import { MarketChart } from "../components/MarketChart";
import { AIAnalysis, AIAnalysisData } from "../components/AIAnalysis";
import {
  AudioManager,
  AUDIO_VOLUME,
  SoundEffectEvent,
} from "../components/AudioManager";

// タイミング定数
const TIMING = {
  OP_START: 0,
  OP_DURATION: 150, // 0〜5秒（150フレーム）
  MAIN_START: 150, // 5秒〜
  ED_DURATION: 240, // 最後の8秒（240フレーム）
  TOTAL_DURATION: 1800, // 60秒
} as const;

// AI分析インサイトのスキーマ
const aiInsightSchema = z.object({
  text: z.string(),
  priority: z.enum(["high", "medium", "low"]),
});

// AI分析データのスキーマ
const aiAnalysisDataSchema = z.object({
  sentiment: z.enum(["bullish", "neutral", "bearish"]),
  sentimentScore: z.number().min(0).max(100),
  overallScore: z.number().min(0).max(100),
  fundamentalScore: z.number().min(0).max(100),
  technicalScore: z.number().min(0).max(100),
  newsSentimentScore: z.number().min(0).max(100),
  insights: z.array(aiInsightSchema),
  riskLevel: z.enum(["low", "medium", "high"]),
  riskMessage: z.string().optional(),
  irisOpinion: z.string(),
});

// スクリプトセグメントのスキーマ
const scriptSegmentSchema = z.object({
  text: z.string(),
  startFrame: z.number(),
  durationFrames: z.number(),
  expression: z.enum(["neutral", "happy", "thinking", "surprised", "ai_analysis", "concerned", "confident"]).optional(),
  marketType: z.enum(["nikkei", "topix", "dowjones", "nasdaq", "sp500", "usdjpy"]).optional(),
  /** AI分析表示時のデータ（expression: "ai_analysis"の場合に使用） */
  aiAnalysisData: aiAnalysisDataSchema.optional(),
  /** AI分析で表示するセクション */
  aiVisibleSections: z.array(z.enum(["sentiment", "scores", "insights", "risk", "prediction"])).optional(),
});

// 動画プロパティのスキーマ
export const videoPropsSchema = z.object({
  title: z.string(),
  companyName: z.string(),
  script: z.array(scriptSegmentSchema),
  audioUrl: z.string().optional(),
  bgmUrl: z.string().optional(),
  characterImage: z.string().optional(),
  /** VRMモデルを使用するかどうか */
  useVRM: z.boolean().optional(),
  /** VRMモデルのURL */
  vrmModelUrl: z.string().optional(),
});

type VideoProps = z.infer<typeof videoPropsSchema>;
type ScriptSegment = z.infer<typeof scriptSegmentSchema>;

// 字幕コンポーネント - 画面下部に大きく配置
const Subtitle: React.FC<{
  text: string;
  isActive: boolean;
}> = ({ text, isActive }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = spring({
    frame: isActive ? frame : 0,
    fps,
    config: {
      damping: 20,
      stiffness: 100,
    },
  });

  if (!text) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        left: 40,
        right: 40,
        opacity: isActive ? opacity : 0,
        display: "flex",
        justifyContent: "center",
        zIndex: 50,
      }}
    >
      {/* 字幕背景 - より大きく、コントラスト強化 */}
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.92)",
          borderRadius: 12,
          padding: "20px 40px",
          backdropFilter: "blur(16px)",
          border: "2px solid rgba(255, 255, 255, 0.15)",
          boxShadow: "0 8px 40px rgba(0, 0, 0, 0.5)",
          maxWidth: "85%",
        }}
      >
        {/* 字幕テキスト - フォントサイズ32px */}
        <p
          style={{
            margin: 0,
            color: "white",
            fontSize: 32,
            fontWeight: 600,
            lineHeight: 1.5,
            textShadow: "0 2px 8px rgba(0,0,0,0.5)",
            letterSpacing: "0.03em",
            textAlign: "center",
          }}
        >
          {text}
        </p>
      </div>
    </div>
  );
};

// ローワーサードバー（セクション名表示）
const LowerThirdBar: React.FC<{
  sectionName: string;
  isActive: boolean;
}> = ({ sectionName, isActive }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideIn = spring({
    frame: isActive ? frame : 0,
    fps,
    config: {
      damping: 25,
      stiffness: 120,
    },
  });

  const translateX = interpolate(slideIn, [0, 1], [-300, 0]);

  if (!sectionName || !isActive) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 140,
        left: 0,
        transform: `translateX(${translateX}px)`,
        opacity: slideIn,
        zIndex: 40,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
        }}
      >
        {/* アクセントバー */}
        <div
          style={{
            width: 6,
            backgroundColor: "#667eea",
            borderRadius: "0 3px 3px 0",
          }}
        />
        {/* セクション名 */}
        <div
          style={{
            background: "linear-gradient(90deg, rgba(102, 126, 234, 0.9) 0%, rgba(118, 75, 162, 0.85) 100%)",
            padding: "12px 32px 12px 20px",
            borderRadius: "0 8px 8px 0",
            backdropFilter: "blur(10px)",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
          }}
        >
          <p
            style={{
              margin: 0,
              color: "white",
              fontSize: 20,
              fontWeight: 600,
              letterSpacing: "0.05em",
              textShadow: "0 1px 3px rgba(0,0,0,0.3)",
            }}
          >
            {sectionName}
          </p>
        </div>
      </div>
    </div>
  );
};

// インフォグラフィック（チャートがない時のビジュアル）
const SectorInfoGraphic: React.FC<{
  text: string;
  startFrame: number;
}> = ({ text, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const animFrame = Math.max(0, frame - startFrame);

  const fadeIn = spring({
    frame: animFrame,
    fps,
    config: { damping: 20, stiffness: 80 },
  });

  // テキストからキーワードを抽出してビジュアル化
  const keywords = [
    { label: "業績", value: 85, color: "#22c55e" },
    { label: "成長性", value: 72, color: "#3b82f6" },
    { label: "安定性", value: 68, color: "#8b5cf6" },
    { label: "配当", value: 55, color: "#f59e0b" },
  ];

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeIn,
        padding: 40,
      }}
    >
      {/* ガラスモーフィズムコンテナ */}
      <div
        style={{
          width: "100%",
          maxWidth: 800,
          background: "rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(20px)",
          borderRadius: 24,
          border: "1px solid rgba(255, 255, 255, 0.1)",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
          padding: 40,
        }}
      >
        {/* タイトル */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 32,
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg width={28} height={28} viewBox="0 0 24 24" fill="none">
              <path
                d="M3 13h2v8H3v-8zm6-6h2v14H9V7zm6 3h2v11h-2V10zm6-7h2v18h-2V3z"
                fill="white"
              />
            </svg>
          </div>
          <h3
            style={{
              margin: 0,
              color: "white",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            セクター分析
          </h3>
        </div>

        {/* バーチャート */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {keywords.map((item, index) => {
            const barProgress = interpolate(
              animFrame,
              [10 + index * 8, 40 + index * 8],
              [0, item.value],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );

            return (
              <div key={item.label}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 8,
                  }}
                >
                  <span
                    style={{
                      color: "rgba(255, 255, 255, 0.8)",
                      fontSize: 18,
                      fontWeight: 500,
                    }}
                  >
                    {item.label}
                  </span>
                  <span
                    style={{
                      color: item.color,
                      fontSize: 18,
                      fontWeight: 700,
                      fontFamily: "monospace",
                    }}
                  >
                    {Math.round(barProgress)}%
                  </span>
                </div>
                <div
                  style={{
                    height: 12,
                    backgroundColor: "rgba(255, 255, 255, 0.1)",
                    borderRadius: 6,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${barProgress}%`,
                      height: "100%",
                      backgroundColor: item.color,
                      borderRadius: 6,
                      boxShadow: `0 0 12px ${item.color}50`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// タイトルコンポーネント
const Title: React.FC<{
  companyName: string;
  title: string;
}> = ({ companyName, title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideIn = spring({
    frame,
    fps,
    config: {
      damping: 20,
      stiffness: 80,
    },
  });

  const translateX = interpolate(slideIn, [0, 1], [-100, 0]);

  return (
    <div
      style={{
        position: "absolute",
        top: 40,
        left: 60,
        transform: `translateX(${translateX}px)`,
        opacity: slideIn,
      }}
    >
      {/* 会社名 */}
      <h1
        style={{
          margin: 0,
          color: "white",
          fontSize: 48,
          fontWeight: "bold",
          textShadow: "0 4px 12px rgba(0,0,0,0.4)",
        }}
      >
        {companyName}
      </h1>
      {/* タイトル */}
      <p
        style={{
          margin: "8px 0 0 0",
          color: "rgba(255, 255, 255, 0.8)",
          fontSize: 24,
          fontWeight: 500,
        }}
      >
        {title}
      </p>
    </div>
  );
};

// セクション名を取得するヘルパー関数
const getSectionName = (segment: ScriptSegment | undefined): string => {
  if (!segment) return "";

  // marketTypeに基づいてセクション名を決定
  if (segment.marketType) {
    const marketNames: Record<string, string> = {
      nikkei: "日経平均",
      topix: "TOPIX",
      dowjones: "NYダウ",
      nasdaq: "NASDAQ",
      sp500: "S&P 500",
      usdjpy: "為替 USD/JPY",
    };
    return marketNames[segment.marketType] || "市況";
  }

  // AI分析モードの場合
  if (segment.expression === "ai_analysis") {
    return "AI分析";
  }

  // テキストの内容からセクション名を推測
  const text = segment.text;
  if (text.includes("セクター") || text.includes("業種")) return "セクター分析";
  if (text.includes("決算") || text.includes("業績")) return "業績分析";
  if (text.includes("配当")) return "配当情報";
  if (text.includes("今後") || text.includes("見通し")) return "今後の見通し";
  if (text.includes("まとめ")) return "まとめ";

  return "分析レポート";
};

// 本編コンテンツコンポーネント
const MainContent: React.FC<{
  title: string;
  companyName: string;
  script: ScriptSegment[];
  audioUrl?: string;
  characterImage: string;
  useVRM?: boolean;
  vrmModelUrl?: string;
}> = ({
  title,
  companyName,
  script,
  audioUrl,
  characterImage,
  useVRM = false,
  vrmModelUrl,
}) => {
  const frame = useCurrentFrame();
  const { fps, width: videoWidth } = useVideoConfig();

  // スクリプトのstartFrameは本編開始からの相対位置
  const currentSegment = script.find(
    (s) => frame >= s.startFrame && frame < s.startFrame + s.durationFrames
  );

  // 前のセグメントを取得（チャート切り替えのアニメーション用）
  const currentSegmentIndex = currentSegment
    ? script.findIndex((s) => s === currentSegment)
    : -1;

  const isSpeaking = !!currentSegment;
  const currentExpression = currentSegment?.expression || "neutral";
  const currentMarketType = currentSegment?.marketType;

  // AI分析表示判定
  const isAIAnalysisMode = currentExpression === "ai_analysis";
  const aiAnalysisData = currentSegment?.aiAnalysisData;
  const aiVisibleSections = currentSegment?.aiVisibleSections;

  // AI分析のアニメーション開始フレーム
  const aiAnalysisStartFrame = currentSegment
    ? frame - currentSegment.startFrame
    : 0;

  // 直前のセグメントとmarketTypeが変わったかどうかを判定
  const previousSegment =
    currentSegmentIndex > 0 ? script[currentSegmentIndex - 1] : null;
  const isNewChart =
    currentMarketType && currentMarketType !== previousSegment?.marketType;

  // チャートのアニメーション開始フレーム（セグメント開始時からリセット）
  const chartStartFrame = currentSegment
    ? frame - currentSegment.startFrame
    : 0;

  // チャートのフェードイン/アウト
  const chartOpacity = spring({
    frame: currentMarketType ? chartStartFrame : 30,
    fps,
    config: {
      damping: 20,
      stiffness: 80,
    },
    durationInFrames: 30,
  });

  // セクション名を取得
  const sectionName = getSectionName(currentSegment);

  // チャートもAI分析もない場合はインフォグラフィックを表示
  const showInfoGraphic = !currentMarketType && !isAIAnalysisMode && isSpeaking;

  // レイアウト定数 - 画面幅1920pxを基準
  const characterWidth = Math.round(videoWidth * 0.30); // キャラクター: 30% = 576px
  const mainContentWidth = Math.round(videoWidth * 0.65); // メインコンテンツ: 65% = 1248px
  const characterRight = 20; // 右端からの距離

  return (
    <>
      {/* 背景グラデーション */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `
            radial-gradient(ellipse at 30% 20%, rgba(102, 126, 234, 0.4) 0%, transparent 50%),
            radial-gradient(ellipse at 70% 80%, rgba(118, 75, 162, 0.3) 0%, transparent 50%),
            linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%)
          `,
        }}
      />

      {/* 装飾パーティクル */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          overflow: "hidden",
          opacity: 0.3,
        }}
      >
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              width: 200,
              height: 200,
              borderRadius: "50%",
              background: `radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)`,
              left: `${20 + i * 20}%`,
              top: `${30 + Math.sin(i) * 20}%`,
              transform: `translateY(${Math.sin(frame * 0.02 + i) * 20}px)`,
            }}
          />
        ))}
      </div>

      {/* タイトル */}
      <Title companyName={companyName} title={title} />

      {/* メインコンテンツエリア（画面中央〜左） */}
      <div
        style={{
          position: "absolute",
          left: 40,
          top: 130,
          width: mainContentWidth,
          bottom: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* 市況チャート（中央に大きく配置） - AI分析モード時は非表示 */}
        {currentMarketType && !isAIAnalysisMode && (
          <div
            style={{
              opacity: chartOpacity,
              transform: `scale(1.4)`, // チャートを1.4倍に拡大
              transformOrigin: "center center",
            }}
          >
            <MarketChart
              marketType={currentMarketType}
              startFrame={isNewChart ? 0 : chartStartFrame}
            />
          </div>
        )}

        {/* AI分析表示 */}
        {isAIAnalysisMode && aiAnalysisData && (
          <div
            style={{
              width: "100%",
              height: "100%",
            }}
          >
            <AIAnalysis
              data={aiAnalysisData as AIAnalysisData}
              startFrame={aiAnalysisStartFrame}
              visibleSections={aiVisibleSections as ("sentiment" | "scores" | "insights" | "risk" | "prediction")[]}
            />
          </div>
        )}

        {/* インフォグラフィック（チャートもAI分析もない時に表示） */}
        {showInfoGraphic && (
          <SectorInfoGraphic
            text={currentSegment?.text || ""}
            startFrame={chartStartFrame}
          />
        )}
      </div>

      {/* VTuberキャラクター（右側に小さく配置 - 30%幅） */}
      <div
        style={{
          position: "absolute",
          right: characterRight,
          bottom: 0,
          width: characterWidth,
          height: useVRM ? "100%" : "70%",
          zIndex: 30,
        }}
      >
        {useVRM ? (
          <VRMScene
            vrmModelUrl={vrmModelUrl || "/models/vrm/AvatarSample_A.vrm"}
            expression={
              // AI分析モード時はthinking表情を使用
              (isAIAnalysisMode ? "thinking" : currentExpression) as "neutral" | "happy" | "thinking" | "surprised"
            }
            isSpeaking={isSpeaking}
            audioIntensity={isSpeaking ? 0.7 : 0}
          />
        ) : (
          <VTuberScene
            characterImage={characterImage}
            expression={
              // AI分析モード時はthinking表情を使用
              (isAIAnalysisMode ? "thinking" : currentExpression) as "neutral" | "happy" | "thinking" | "surprised" | "concerned" | "confident"
            }
            isSpeaking={isSpeaking}
            audioIntensity={isSpeaking ? 0.7 : 0.3}
            segmentStartFrame={currentSegment?.startFrame}
            segmentDurationFrames={currentSegment?.durationFrames}
          />
        )}
      </div>

      {/* ローワーサードバー（セクション名表示） */}
      <LowerThirdBar sectionName={sectionName} isActive={isSpeaking} />

      {/* 字幕 */}
      <Subtitle text={currentSegment?.text || ""} isActive={isSpeaking} />

      {/* ナレーション音声 */}
      {audioUrl && <Audio src={staticFile(audioUrl)} />}
    </>
  );
};

// メインコンポジション
export const IRAnalysisVideo: React.FC<VideoProps> = ({
  title,
  companyName,
  script,
  audioUrl,
  bgmUrl,
  characterImage = "/images/iris/iris-normal.png",
  useVRM = false,
  vrmModelUrl = "/models/vrm/AvatarSample_A.vrm",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // ED開始フレーム（最後の90フレーム）
  const edStart = durationInFrames - TIMING.ED_DURATION;
  // 本編の長さ
  const mainDuration = edStart - TIMING.OP_DURATION;

  // 現在ナレーション中かどうかを判定
  const isNarrating = useMemo(() => {
    const currentSegment = script.find(
      (s) =>
        frame >= TIMING.OP_DURATION + s.startFrame &&
        frame < TIMING.OP_DURATION + s.startFrame + s.durationFrames
    );
    return !!currentSegment;
  }, [frame, script]);

  // 効果音イベントを自動生成
  const soundEffects = useMemo(() => {
    const events: SoundEffectEvent[] = [];

    // OP登場音（OPの30フレーム目）
    events.push({
      type: "op_appear",
      frame: 30,
      volume: AUDIO_VOLUME.SE_OP,
    });

    // 本編開始時の場面転換音
    events.push({
      type: "transition",
      frame: TIMING.OP_DURATION,
      volume: AUDIO_VOLUME.SE_TRANSITION,
    });

    // 各スクリプトセグメントの解析
    let previousMarketType: string | undefined;

    script.forEach((segment) => {
      const absoluteStartFrame = TIMING.OP_DURATION + segment.startFrame;

      // グラフ表示時（marketTypeが変更された時）
      if (segment.marketType && segment.marketType !== previousMarketType) {
        events.push({
          type: "graph_display",
          frame: absoluteStartFrame,
          volume: AUDIO_VOLUME.SE_GRAPH,
        });
        previousMarketType = segment.marketType;
      }

      // 強調表現を含むセグメント
      if (
        segment.expression === "surprised" ||
        segment.text.includes("!") ||
        segment.text.includes("！") ||
        segment.text.includes("注目")
      ) {
        events.push({
          type: "emphasis",
          frame: absoluteStartFrame + 15,
          volume: AUDIO_VOLUME.SE_EMPHASIS,
        });
      }

      // AI分析表示時の効果音
      if (segment.expression === "ai_analysis" && segment.aiAnalysisData) {
        // AI分析開始時のトランジション音
        events.push({
          type: "graph_display",
          frame: absoluteStartFrame,
          volume: AUDIO_VOLUME.SE_GRAPH,
        });
      }
    });

    // ED終了チャイム
    events.push({
      type: "ed_chime",
      frame: edStart + 15,
      volume: AUDIO_VOLUME.SE_ED,
    });

    return events;
  }, [script, edStart]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#0f0f1a" }}>
      {/* AudioManager: BGM + 効果音の統合管理 */}
      <AudioManager
        bgmUrl={bgmUrl}
        opEndFrame={TIMING.OP_DURATION}
        edStartFrame={edStart}
        isNarrating={isNarrating}
        soundEffects={soundEffects}
        loopBgm={true}
      />

      {/* OP: 0〜90フレーム（0〜3秒） */}
      <Sequence from={TIMING.OP_START} durationInFrames={TIMING.OP_DURATION}>
        <OpeningScene
          durationFrames={TIMING.OP_DURATION}
          characterImage={characterImage}
          title={title}
          date={new Date().toLocaleDateString("ja-JP", { year: "numeric", month: "long", day: "numeric" })}
        />
      </Sequence>

      {/* 本編: 90フレーム〜ED開始まで */}
      <Sequence from={TIMING.OP_DURATION} durationInFrames={mainDuration}>
        <MainContent
          title={title}
          companyName={companyName}
          script={script}
          audioUrl={audioUrl}
          characterImage={characterImage}
          useVRM={useVRM}
          vrmModelUrl={vrmModelUrl}
        />
      </Sequence>

      {/* ED: 最後の90フレーム */}
      <Sequence from={edStart} durationInFrames={TIMING.ED_DURATION}>
        <EndingScene
          durationFrames={TIMING.ED_DURATION}
          characterImage={characterImage}
        />
      </Sequence>

      {/* フレームカウンター（デバッグ用） */}
      {process.env.NODE_ENV === "development" && (
        <div
          style={{
            position: "absolute",
            bottom: 10,
            right: 10,
            color: "rgba(255,255,255,0.3)",
            fontSize: 12,
            fontFamily: "monospace",
            zIndex: 100,
          }}
        >
          Frame: {frame} / {durationInFrames} |
          {frame < TIMING.OP_DURATION
            ? " [OP]"
            : frame >= edStart
              ? " [ED]"
              : " [MAIN]"}
        </div>
      )}
    </AbsoluteFill>
  );
};
