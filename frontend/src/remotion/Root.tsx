import { Composition } from "remotion";
import { IRAnalysisVideo, videoPropsSchema } from "./compositions/IRAnalysis";
import marketCommentaryScript from "../data/market-commentary-script.json";
import audioSegmentsData from "../../public/audio/market-comment-full-segments.json";

// 30fps
const FPS = 30;

// 実際の音声長に基づくフレーム計算
const OP_FRAMES = 5 * FPS; // 5秒 = 150フレーム
const AUDIO_DURATION = audioSegmentsData.total_duration; // 373.909秒
const MAIN_CONTENT_FRAMES = Math.ceil(AUDIO_DURATION * FPS); // 約11217フレーム
const ED_FRAMES = 8 * FPS; // 8秒 = 240フレーム
const TOTAL_FRAMES = OP_FRAMES + MAIN_CONTENT_FRAMES + ED_FRAMES; // 約11607フレーム

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
        sentiment: "bullish",
        sentimentScore: 58,
        overallScore: 72,
        fundamentalScore: 68,
        technicalScore: 75,
        newsSentimentScore: 65,
        insights: [
          { text: "半導体セクターの上昇が市場を牽引", priority: "high" },
          { text: "銀行株が金利上昇期待で堅調", priority: "medium" },
          { text: "年初からの上昇トレンド継続", priority: "medium" },
        ],
        riskLevel: "medium",
        riskMessage: "中東情勢・中国経済・日銀政策に要注意",
        irisOpinion: "短期的には上昇トレンドが継続する可能性が高いと見ています。ただし、日経平均40,000円の大台は心理的な節目になりやすいので、この水準では一旦調整が入ることも想定しておくべきですね。",
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
          title: "2026年1月10日 市況コメント",
          companyName: "AI-IR Insight",
          script: SCRIPT_SEGMENTS,
          audioUrl: "/audio/market-comment-full.wav",
          characterImage: "/images/iris/iris-normal.png",
          bgmUrl: "/audio/bgm/business-calm.mp3",
          useVRM: false, // 2D版（高速レンダリング）※VRM版は --gl=angle オプション必要
          vrmModelUrl: "/models/vrm/AvatarSample_A.vrm",
        }}
      />
    </>
  );
};
