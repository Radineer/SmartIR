import React from "react";
import {
  Audio,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Sequence,
  staticFile,
} from "remotion";

// 効果音の種類
export type SoundEffectType =
  | "op_appear"      // OP登場音（シャキーン）
  | "transition"     // 場面転換音（シュッ）
  | "emphasis"       // 強調音（ポン）
  | "graph_display"  // グラフ表示音（ピロリン）
  | "ed_chime";      // ED終了音（チャイム）

// 効果音ファイルパスのマッピング
const SE_FILE_MAP: Record<SoundEffectType, string> = {
  op_appear: "/audio/se/op-appear.mp3",
  transition: "/audio/se/transition.mp3",
  emphasis: "/audio/se/emphasis.mp3",
  graph_display: "/audio/se/graph-display.mp3",
  ed_chime: "/audio/se/ed-chime.mp3",
};

// デフォルト音量設定
export const AUDIO_VOLUME = {
  BGM_DEFAULT: 0.25,        // BGM基本音量
  BGM_NARRATION: 0.15,      // ナレーション中のBGM音量
  BGM_OP: 0.4,              // OP中のBGM音量
  BGM_ED: 0.35,             // ED中のBGM音量
  NARRATION: 1.0,           // ナレーション音量
  SE_OP: 0.7,               // OP効果音音量
  SE_TRANSITION: 0.5,       // 場面転換音音量
  SE_EMPHASIS: 0.6,         // 強調音音量
  SE_GRAPH: 0.5,            // グラフ表示音音量
  SE_ED: 0.65,              // ED効果音音量
} as const;

// 効果音イベントの型
export interface SoundEffectEvent {
  type: SoundEffectType;
  frame: number;
  volume?: number;
}

// BGMマネージャーのProps
interface BGMManagerProps {
  /** BGMファイルのパス */
  bgmUrl?: string;
  /** OP終了フレーム */
  opEndFrame: number;
  /** ED開始フレーム */
  edStartFrame: number;
  /** ナレーション中かどうかを判定する関数 */
  isNarrating?: boolean;
  /** ループ再生するかどうか */
  loop?: boolean;
}

/**
 * BGMの音量制御コンポーネント
 * - OP中: フェードイン後、高め音量
 * - 本編中: ナレーションがある場合は音量を下げる
 * - ED中: 少し音量を上げてからフェードアウト
 */
export const BGMManager: React.FC<BGMManagerProps> = ({
  bgmUrl,
  opEndFrame,
  edStartFrame,
  isNarrating = false,
  loop = true,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  if (!bgmUrl) return null;

  // BGM音量計算
  const bgmVolume = (() => {
    // フェードイン/アウトの長さ
    const fadeFrames = 30;

    if (frame < fadeFrames) {
      // 開始時フェードイン
      return interpolate(frame, [0, fadeFrames], [0, AUDIO_VOLUME.BGM_OP], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    } else if (frame < opEndFrame) {
      // OP中: 高め音量
      return AUDIO_VOLUME.BGM_OP;
    } else if (frame < opEndFrame + fadeFrames) {
      // OP→本編への音量変更
      const targetVolume = isNarrating
        ? AUDIO_VOLUME.BGM_NARRATION
        : AUDIO_VOLUME.BGM_DEFAULT;
      return interpolate(
        frame,
        [opEndFrame, opEndFrame + fadeFrames],
        [AUDIO_VOLUME.BGM_OP, targetVolume],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
    } else if (frame < edStartFrame) {
      // 本編中: ナレーションに応じて音量調整
      const baseVolume = isNarrating
        ? AUDIO_VOLUME.BGM_NARRATION
        : AUDIO_VOLUME.BGM_DEFAULT;
      return baseVolume;
    } else if (frame < edStartFrame + fadeFrames) {
      // ED開始: 音量を少し上げる
      const currentVolume = isNarrating
        ? AUDIO_VOLUME.BGM_NARRATION
        : AUDIO_VOLUME.BGM_DEFAULT;
      return interpolate(
        frame,
        [edStartFrame, edStartFrame + fadeFrames],
        [currentVolume, AUDIO_VOLUME.BGM_ED],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
    } else if (frame >= durationInFrames - fadeFrames) {
      // 終了フェードアウト
      return interpolate(
        frame,
        [durationInFrames - fadeFrames, durationInFrames],
        [AUDIO_VOLUME.BGM_ED, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
    } else {
      // ED中
      return AUDIO_VOLUME.BGM_ED;
    }
  })();

  return (
    <Audio
      src={staticFile(bgmUrl)}
      volume={bgmVolume}
      loop={loop}
    />
  );
};

// 効果音コンポーネントのProps
interface SoundEffectProps {
  /** 効果音の種類 */
  type: SoundEffectType;
  /** 音量（0.0〜1.0） */
  volume?: number;
}

/**
 * 単一の効果音を再生するコンポーネント
 */
export const SoundEffect: React.FC<SoundEffectProps> = ({
  type,
  volume,
}) => {
  // デフォルト音量の取得
  const defaultVolumes: Record<SoundEffectType, number> = {
    op_appear: AUDIO_VOLUME.SE_OP,
    transition: AUDIO_VOLUME.SE_TRANSITION,
    emphasis: AUDIO_VOLUME.SE_EMPHASIS,
    graph_display: AUDIO_VOLUME.SE_GRAPH,
    ed_chime: AUDIO_VOLUME.SE_ED,
  };

  const effectiveVolume = volume ?? defaultVolumes[type];
  const filePath = SE_FILE_MAP[type];

  return (
    <Audio
      src={staticFile(filePath)}
      volume={effectiveVolume}
    />
  );
};

// 効果音シーケンスコンポーネントのProps
interface SoundEffectSequenceProps {
  /** 効果音イベントのリスト */
  events: SoundEffectEvent[];
}

/**
 * 複数の効果音を適切なタイミングで再生するコンポーネント
 */
export const SoundEffectSequence: React.FC<SoundEffectSequenceProps> = ({
  events,
}) => {
  return (
    <>
      {events.map((event, index) => (
        <Sequence
          key={`se-${event.type}-${event.frame}-${index}`}
          from={event.frame}
          durationInFrames={90} // 効果音の最大長を想定
        >
          <SoundEffect type={event.type} volume={event.volume} />
        </Sequence>
      ))}
    </>
  );
};

// AudioManagerのProps
interface AudioManagerProps {
  /** BGMファイルのパス */
  bgmUrl?: string;
  /** OP終了フレーム */
  opEndFrame: number;
  /** ED開始フレーム */
  edStartFrame: number;
  /** ナレーション中かどうか */
  isNarrating?: boolean;
  /** 効果音イベントのリスト */
  soundEffects?: SoundEffectEvent[];
  /** BGMをループするか */
  loopBgm?: boolean;
}

/**
 * 音声全体を管理する統合コンポーネント
 * BGMの音量制御と効果音のタイミング再生を行う
 */
export const AudioManager: React.FC<AudioManagerProps> = ({
  bgmUrl,
  opEndFrame,
  edStartFrame,
  isNarrating = false,
  soundEffects = [],
  loopBgm = true,
}) => {
  return (
    <>
      {/* BGM */}
      <BGMManager
        bgmUrl={bgmUrl}
        opEndFrame={opEndFrame}
        edStartFrame={edStartFrame}
        isNarrating={isNarrating}
        loop={loopBgm}
      />

      {/* 効果音 */}
      <SoundEffectSequence events={soundEffects} />
    </>
  );
};

// ダイナミックBGM音量制御用のフック
export const useDynamicBGMVolume = (
  isNarrating: boolean,
  opEndFrame: number,
  edStartFrame: number
): number => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeFrames = 30;

  if (frame < fadeFrames) {
    return interpolate(frame, [0, fadeFrames], [0, AUDIO_VOLUME.BGM_OP], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else if (frame < opEndFrame) {
    return AUDIO_VOLUME.BGM_OP;
  } else if (frame < edStartFrame) {
    return isNarrating ? AUDIO_VOLUME.BGM_NARRATION : AUDIO_VOLUME.BGM_DEFAULT;
  } else if (frame >= durationInFrames - fadeFrames) {
    return interpolate(
      frame,
      [durationInFrames - fadeFrames, durationInFrames],
      [AUDIO_VOLUME.BGM_ED, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
  } else {
    return AUDIO_VOLUME.BGM_ED;
  }
};

export default AudioManager;
