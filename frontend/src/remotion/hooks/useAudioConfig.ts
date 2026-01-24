import { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { AUDIO_VOLUME, SoundEffectEvent } from "../components/AudioManager";

// オーディオ設定の型
export interface AudioConfig {
  bgmUrl: string;
  opEndFrame: number;
  edStartFrame: number;
  isNarrating: boolean;
  soundEffects: SoundEffectEvent[];
}

// スクリプトセグメントの型
interface ScriptSegment {
  text: string;
  startFrame: number;
  durationFrames: number;
  expression?: "neutral" | "happy" | "thinking" | "surprised";
  marketType?: "nikkei" | "topix" | "dowjones" | "usdjpy";
}

// タイミング設定の型
interface TimingConfig {
  opDuration: number;
  edDuration: number;
  totalDuration: number;
}

/**
 * 動画のオーディオ設定を生成するフック
 * スクリプトの内容に基づいて、適切な効果音イベントを自動生成
 */
export const useAudioConfig = (
  script: ScriptSegment[],
  timing: TimingConfig,
  bgmUrl?: string
): AudioConfig => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // ED開始フレーム
  const edStartFrame = durationInFrames - timing.edDuration;

  // 現在ナレーション中かどうかを判定
  const isNarrating = useMemo(() => {
    const currentSegment = script.find(
      (s) =>
        frame >= timing.opDuration + s.startFrame &&
        frame < timing.opDuration + s.startFrame + s.durationFrames
    );
    return !!currentSegment;
  }, [frame, script, timing.opDuration]);

  // 効果音イベントを自動生成
  const soundEffects = useMemo(() => {
    const events: SoundEffectEvent[] = [];

    // OP登場音（OPの30フレーム目）
    events.push({
      type: "op_appear",
      frame: 30,
      volume: AUDIO_VOLUME.SE_OP,
    });

    // 各スクリプトセグメントの解析
    let previousMarketType: string | undefined;

    script.forEach((segment, index) => {
      const absoluteStartFrame = timing.opDuration + segment.startFrame;

      // 最初のセグメント開始時に場面転換音
      if (index === 0) {
        events.push({
          type: "transition",
          frame: timing.opDuration,
          volume: AUDIO_VOLUME.SE_TRANSITION,
        });
      }

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
        segment.text.includes("！") ||
        segment.text.includes("注目")
      ) {
        events.push({
          type: "emphasis",
          frame: absoluteStartFrame + 15, // セグメント開始から少し後
          volume: AUDIO_VOLUME.SE_EMPHASIS,
        });
      }
    });

    // ED終了チャイム
    events.push({
      type: "ed_chime",
      frame: edStartFrame + 15,
      volume: AUDIO_VOLUME.SE_ED,
    });

    return events;
  }, [script, timing.opDuration, edStartFrame]);

  return {
    bgmUrl: bgmUrl || "/audio/bgm/business-calm.mp3",
    opEndFrame: timing.opDuration,
    edStartFrame,
    isNarrating,
    soundEffects,
  };
};

/**
 * シーンの切り替えタイミングを検出するフック
 */
export const useSceneTransition = (
  script: ScriptSegment[],
  opDuration: number
): {
  isTransitioning: boolean;
  transitionFrame: number | null;
} => {
  const frame = useCurrentFrame();

  return useMemo(() => {
    // 各セグメントの開始フレームで場面転換
    for (const segment of script) {
      const absoluteStartFrame = opDuration + segment.startFrame;
      // 転換の前後5フレームを転換中とみなす
      if (Math.abs(frame - absoluteStartFrame) <= 5) {
        return {
          isTransitioning: true,
          transitionFrame: absoluteStartFrame,
        };
      }
    }
    return {
      isTransitioning: false,
      transitionFrame: null,
    };
  }, [frame, script, opDuration]);
};

/**
 * マーカーベースの効果音タイミングを生成するユーティリティ
 * スクリプトにマーカーを含めることで、特定位置に効果音を配置可能
 */
export const generateSoundEffectsFromMarkers = (
  script: Array<ScriptSegment & { soundMarkers?: SoundEffectEvent[] }>,
  opDuration: number
): SoundEffectEvent[] => {
  const events: SoundEffectEvent[] = [];

  script.forEach((segment) => {
    if (segment.soundMarkers) {
      segment.soundMarkers.forEach((marker) => {
        events.push({
          ...marker,
          frame: opDuration + segment.startFrame + marker.frame,
        });
      });
    }
  });

  return events;
};

export default useAudioConfig;
