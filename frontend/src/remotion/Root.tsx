import { Composition } from "remotion";
import { IRAnalysisVideo, videoPropsSchema } from "./compositions/IRAnalysis";
import { TradingChallengeVideo, tradingChallengePropsSchema } from "./compositions/TradingChallenge";
import marketCommentaryScript from "../data/market-commentary-script.json";
import audioSegmentsData from "../../public/audio/market-comment-full-segments.json";

// 30fps
const FPS = 30;

// 実際の音声長に基づくフレーム計算
const OP_FRAMES = 5 * FPS; // 5秒 = 150フレーム
const AUDIO_DURATION = audioSegmentsData.total_duration;
const MAIN_CONTENT_FRAMES = Math.ceil(AUDIO_DURATION * FPS);
const ED_FRAMES = 8 * FPS; // 8秒 = 240フレーム
const TOTAL_FRAMES = OP_FRAMES + MAIN_CONTENT_FRAMES + ED_FRAMES;

// 秒をフレームに変換するヘルパー
const secondsToFrames = (seconds: number): number => Math.round(seconds * FPS);

// AI分析データの型定義（IRAnalysisのスキーマと一致）
interface AIAnalysisData {
  sentiment: "bullish" | "neutral" | "bearish";
  sentimentScore: number;
  overallScore: number;
  fundamentalScore: number;
  technicalScore: number;
  newsSentimentScore: number;
  insights: { text: string; priority: "high" | "medium" | "low" }[];
  riskLevel: "low" | "medium" | "high";
  riskMessage?: string;
  irisOpinion: string;
}

// セグメントのスクリプト形式の型定義
interface ScriptSegment {
  text: string;
  startFrame: number;
  durationFrames: number;
  expression: "happy" | "neutral" | "thinking" | "concerned" | "confident" | "surprised" | "ai_analysis";
  marketType?: "nikkei" | "topix" | "usdjpy" | "dowjones" | "nasdaq" | "sp500";
  aiAnalysisData?: AIAnalysisData;
}

// 音声セグメントデータからスクリプトセグメントを構築（実際の音声タイミングを使用）
const buildScriptSegments = (): ScriptSegment[] => {
  const segments: ScriptSegment[] = [];

  // expressionの型変換
  const normalizeExpression = (expr: string): ScriptSegment["expression"] => {
    const validExpressions = ["happy", "neutral", "thinking", "concerned", "confident", "surprised", "ai_analysis"];
    return validExpressions.includes(expr) ? (expr as ScriptSegment["expression"]) : "neutral";
  };

  // 音声セグメントIDからexpressionとmarketTypeを取得するマッピング
  const segmentMetadata: Record<string, { expression: string; marketType?: ScriptSegment["marketType"]; aiAnalysisData?: AIAnalysisData }> = {
    "opening": { expression: "happy" },
    "market_summary_nikkei": { expression: "neutral", marketType: "nikkei" },
    "market_summary_topix": { expression: "neutral", marketType: "topix" },
    "market_summary_weekly_comparison": { expression: "happy", marketType: "nikkei" },
    "sector_analysis_top_sectors": { expression: "happy" },
    "sector_analysis_bottom_sectors": { expression: "concerned" },
    "sector_analysis_sector_background": { expression: "neutral" },
    "individual_stocks_stock_1": { expression: "happy", marketType: "nikkei" },
    "individual_stocks_stock_2": { expression: "neutral", marketType: "nikkei" },
    "individual_stocks_ai_comment": { expression: "thinking" },
    "overseas_forex_us_market": { expression: "neutral", marketType: "dowjones" },
    "overseas_forex_forex": { expression: "neutral", marketType: "usdjpy" },
    "overseas_forex_outlook": { expression: "thinking" },
    "ai_analysis_sentiment": {
      expression: "ai_analysis",
      aiAnalysisData: {
        sentiment: "neutral",
        sentimentScore: 52,
        overallScore: 65,
        fundamentalScore: 62,
        technicalScore: 68,
        newsSentimentScore: 58,
        insights: [
          { text: "AI・半導体セクターが市場を牽引", priority: "high" },
          { text: "FOMCは年内2回利下げ見通し維持で安心感", priority: "high" },
          { text: "年度末リバランス売りに警戒", priority: "medium" },
        ],
        riskLevel: "medium",
        riskMessage: "年度末需給・中国経済回復遅れ・AIバブル懸念に注意",
        irisOpinion: "4月の新年度入りに向けてセンチメント改善を見込んでいます。日本企業の業績は円安効果で上振れ余地があり、海外投資家の日本株回帰も期待できますね。ただし、3月末までは波乱含みです。",
      }
    },
    "ai_analysis_risk_factors": { expression: "concerned" },
    "ai_analysis_iris_view": { expression: "confident" },
    "ending_summary": { expression: "neutral" },
    "ending_next_preview": { expression: "happy" },
    "ending_subscribe": { expression: "happy" },
  };

  // 実際の音声セグメントからスクリプトセグメントを構築
  for (const audioSeg of audioSegmentsData.segments) {
    const metadata = segmentMetadata[audioSeg.id] || { expression: "neutral" };
    const startFrame = OP_FRAMES + secondsToFrames(audioSeg.start);
    const durationFrames = secondsToFrames(audioSeg.duration);

    const scriptSegment: ScriptSegment = {
      text: audioSeg.text,
      startFrame,
      durationFrames,
      expression: normalizeExpression(metadata.expression),
    };

    if (metadata.marketType) {
      scriptSegment.marketType = metadata.marketType;
    }

    if (metadata.aiAnalysisData) {
      scriptSegment.aiAnalysisData = metadata.aiAnalysisData;
    }

    segments.push(scriptSegment);
  }

  return segments;
};

// スクリプトセグメントを構築
const SCRIPT_SEGMENTS = buildScriptSegments();

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="IRAnalysis"
        component={IRAnalysisVideo}
        schema={videoPropsSchema}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{
          title: "2026年3月19日 市況コメント",
          companyName: "AI-IR Insight",
          script: SCRIPT_SEGMENTS,
          audioUrl: "/audio/market-comment-full.wav",
          characterImage: "/images/iris/iris-normal.png",
          bgmUrl: "/audio/bgm/business-calm.mp3",
          useVRM: true,
          vrmModelUrl: "/models/vrm/iris.vrm",
        }}
      />
      <Composition
        id="TradingChallenge"
        component={TradingChallengeVideo}
        schema={tradingChallengePropsSchema}
        durationInFrames={Math.round(22.44 * FPS)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={{
          day: 2,
          date: "2026-03-25",
          nav: 102287,
          dailyReturn: 2.38,
          cumulativeReturn: 2.29,
          maxDrawdown: 0,
          positions: [
            { name: "ソフトバンクG", ticker: "9984.T", pnl: 1058, pnlPct: 7.06 },
            { name: "第一生命", ticker: "8750.T", pnl: 536, pnlPct: 3.57 },
            { name: "三井住友FG", ticker: "8316.T", pnl: 451, pnlPct: 3.01 },
            { name: "オリックス", ticker: "8591.T", pnl: 225, pnlPct: 1.50 },
            { name: "KDDI", ticker: "9433.T", pnl: 217, pnlPct: 1.45 },
            { name: "アサヒ", ticker: "2502.T", pnl: -109, pnlPct: -0.73 },
          ],
          characterVideoUrl: "video-frames/iris_omnihuman.mp4",
          audioUrl: "audio/iris_day2_voice.wav",
          script: [
            { text: "みなさん、こんにちは！イリスです！", startFrame: 0, durationFrames: 85 },
            { text: "AIトレーディングチャレンジ Day2のご報告です！", startFrame: 85, durationFrames: 95 },
            { text: "本日のNAVは10万2287円、+2.38%！", startFrame: 180, durationFrames: 90 },
            { text: "ソフトバンクGが+1,058円のトップ！", startFrame: 270, durationFrames: 85 },
            { text: "6銘柄中5銘柄がプラスです", startFrame: 355, durationFrames: 80 },
            { text: "データは嘘をつきませんから！", startFrame: 435, durationFrames: 80 },
            { text: "明日もお楽しみに！バイバイ！", startFrame: 515, durationFrames: 100 },
          ],
        }}
      />
    </>
  );
};
