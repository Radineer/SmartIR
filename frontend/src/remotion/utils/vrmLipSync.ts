/**
 * VRM リップシンクユーティリティ
 *
 * フレームベースのリップシンク計算を提供します。
 * Remotionの決定論的レンダリングに対応しています。
 */

import type { VRM } from "@pixiv/three-vrm";

// ========================================
// 型定義
// ========================================

/** 母音タイプ */
export type Vowel = "a" | "i" | "u" | "e" | "o" | "n";

/** リップシンク設定 */
export interface LipSyncConfig {
  /** 感度（0-2、デフォルト: 1.0） */
  sensitivity: number;
  /** スムージング（0-1、デフォルト: 0.3） */
  smoothing: number;
  /** 最小しきい値（これ以下の音声強度では口を閉じる） */
  threshold: number;
  /** 母音の切り替え速度（フレーム数） */
  vowelCycleSpeed: number;
  /** ランダム性（0-1） */
  randomness: number;
}

/** リップシンク状態 */
export interface LipSyncState {
  /** 現在の母音 */
  vowel: Vowel;
  /** 口の開き具合（0-1） */
  weight: number;
  /** VRMのBlendShapeプリセット名 */
  presetName: string;
}

/** 音素解析結果 */
export interface PhonemeResult {
  vowel: Vowel;
  weight: number;
}

// ========================================
// 定数
// ========================================

/** デフォルトのリップシンク設定 */
export const DEFAULT_LIP_SYNC_CONFIG: LipSyncConfig = {
  sensitivity: 1.0,
  smoothing: 0.3,
  threshold: 0.05,
  vowelCycleSpeed: 4,
  randomness: 0.2,
};

/** 母音からVRM BlendShapeプリセットへのマッピング */
export const VOWEL_TO_PRESET: Record<Vowel, string> = {
  a: "aa",
  i: "ih",
  u: "ou",
  e: "ee",
  o: "oh",
  n: "neutral",
};

/** 日本語の文字から母音へのマッピング */
export const JAPANESE_CHAR_TO_VOWEL: Record<string, Vowel> = {
  // あ行
  あ: "a", い: "i", う: "u", え: "e", お: "o",
  ア: "a", イ: "i", ウ: "u", エ: "e", オ: "o",
  // か行
  か: "a", き: "i", く: "u", け: "e", こ: "o",
  カ: "a", キ: "i", ク: "u", ケ: "e", コ: "o",
  // さ行
  さ: "a", し: "i", す: "u", せ: "e", そ: "o",
  サ: "a", シ: "i", ス: "u", セ: "e", ソ: "o",
  // た行
  た: "a", ち: "i", つ: "u", て: "e", と: "o",
  タ: "a", チ: "i", ツ: "u", テ: "e", ト: "o",
  // な行
  な: "a", に: "i", ぬ: "u", ね: "e", の: "o",
  ナ: "a", ニ: "i", ヌ: "u", ネ: "e", ノ: "o",
  // は行
  は: "a", ひ: "i", ふ: "u", へ: "e", ほ: "o",
  ハ: "a", ヒ: "i", フ: "u", ヘ: "e", ホ: "o",
  // ま行
  ま: "a", み: "i", む: "u", め: "e", も: "o",
  マ: "a", ミ: "i", ム: "u", メ: "e", モ: "o",
  // や行
  や: "a", ゆ: "u", よ: "o",
  ヤ: "a", ユ: "u", ヨ: "o",
  // ら行
  ら: "a", り: "i", る: "u", れ: "e", ろ: "o",
  ラ: "a", リ: "i", ル: "u", レ: "e", ロ: "o",
  // わ行
  わ: "a", を: "o",
  ワ: "a", ヲ: "o",
  // ん
  ん: "n", ン: "n",
  // が行
  が: "a", ぎ: "i", ぐ: "u", げ: "e", ご: "o",
  ガ: "a", ギ: "i", グ: "u", ゲ: "e", ゴ: "o",
  // ざ行
  ざ: "a", じ: "i", ず: "u", ぜ: "e", ぞ: "o",
  ザ: "a", ジ: "i", ズ: "u", ゼ: "e", ゾ: "o",
  // だ行
  だ: "a", ぢ: "i", づ: "u", で: "e", ど: "o",
  ダ: "a", ヂ: "i", ヅ: "u", デ: "e", ド: "o",
  // ば行
  ば: "a", び: "i", ぶ: "u", べ: "e", ぼ: "o",
  バ: "a", ビ: "i", ブ: "u", ベ: "e", ボ: "o",
  // ぱ行
  ぱ: "a", ぴ: "i", ぷ: "u", ぺ: "e", ぽ: "o",
  パ: "a", ピ: "i", プ: "u", ペ: "e", ポ: "o",
};

// ========================================
// リップシンク計算関数
// ========================================

/**
 * 疑似ランダム値を生成（シード付き）
 */
function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

/**
 * フレーム番号と音声強度からリップシンク状態を計算
 *
 * @param frame - 現在のフレーム番号
 * @param audioIntensity - 音声の強度（0-1）
 * @param isSpeaking - 話している状態か
 * @param config - リップシンク設定
 * @returns リップシンク状態
 */
export function calculateLipSync(
  frame: number,
  audioIntensity: number,
  isSpeaking: boolean,
  config: Partial<LipSyncConfig> = {}
): LipSyncState {
  const fullConfig = { ...DEFAULT_LIP_SYNC_CONFIG, ...config };
  const {
    sensitivity,
    threshold,
    vowelCycleSpeed,
    randomness,
  } = fullConfig;

  // 話していない場合は口を閉じる
  if (!isSpeaking) {
    return {
      vowel: "n",
      weight: 0,
      presetName: VOWEL_TO_PRESET.n,
    };
  }

  // 音声強度がしきい値以下の場合
  const adjustedIntensity = audioIntensity * sensitivity;
  if (adjustedIntensity < threshold) {
    return {
      vowel: "n",
      weight: 0,
      presetName: VOWEL_TO_PRESET.n,
    };
  }

  // 母音の選択（フレームベースでサイクル）
  const vowels: Vowel[] = ["a", "i", "u", "e", "o"];

  // ランダム性を加えた母音選択
  const baseIndex = Math.floor(frame / vowelCycleSpeed);
  const randomOffset = Math.floor(seededRandom(frame * 0.1) * randomness * vowels.length);
  const vowelIndex = (baseIndex + randomOffset) % vowels.length;
  const vowel = vowels[vowelIndex];

  // 重みの計算（音声強度に基づく）
  const weight = Math.min(adjustedIntensity * 1.2, 1.0);

  return {
    vowel,
    weight,
    presetName: VOWEL_TO_PRESET[vowel],
  };
}

/**
 * テキストに基づいてリップシンク状態を計算
 * スクリプトのテキストから適切な母音を推定
 *
 * @param frame - 現在のフレーム番号
 * @param text - 発話テキスト
 * @param startFrame - テキストの開始フレーム
 * @param durationFrames - テキストの継続フレーム数
 * @param fps - フレームレート
 * @returns リップシンク状態
 */
export function calculateLipSyncFromText(
  frame: number,
  text: string,
  startFrame: number,
  durationFrames: number,
  fps: number
): LipSyncState {
  const relativeFrame = frame - startFrame;

  // 範囲外の場合
  if (relativeFrame < 0 || relativeFrame >= durationFrames) {
    return {
      vowel: "n",
      weight: 0,
      presetName: VOWEL_TO_PRESET.n,
    };
  }

  // テキストから文字を抽出
  const characters = text.split("");
  const charPerFrame = characters.length / durationFrames;
  const currentCharIndex = Math.min(
    Math.floor(relativeFrame * charPerFrame),
    characters.length - 1
  );

  // 現在の文字から母音を取得
  const currentChar = characters[currentCharIndex];
  const vowel = JAPANESE_CHAR_TO_VOWEL[currentChar] || "a";

  // 重みは発話中は常に1（テキストベースなので）
  const weight = 0.8;

  return {
    vowel,
    weight,
    presetName: VOWEL_TO_PRESET[vowel],
  };
}

// ========================================
// VRM適用関数
// ========================================

/**
 * リップシンク状態をVRMに適用
 *
 * @param vrm - VRMインスタンス
 * @param state - リップシンク状態
 * @param blend - ブレンド係数（0-1、前のフレームとのスムージング用）
 */
export function applyLipSyncToVRM(
  vrm: VRM,
  state: LipSyncState,
  blend: number = 1.0
): void {
  if (!vrm.expressionManager) return;

  // 全ての口の表情をリセット
  const mouthPresets = ["aa", "ih", "ou", "ee", "oh"];
  for (const preset of mouthPresets) {
    const currentValue = vrm.expressionManager.getValue(preset) || 0;
    if (preset === state.presetName) {
      // 目標の表情へブレンド
      const targetValue = state.weight;
      const blendedValue = currentValue * (1 - blend) + targetValue * blend;
      vrm.expressionManager.setValue(preset, blendedValue);
    } else {
      // 他の表情を減衰
      vrm.expressionManager.setValue(preset, currentValue * (1 - blend));
    }
  }
}

// ========================================
// リップシンクシーケンス
// ========================================

/**
 * リップシンクシーケンスを事前計算
 * 長い動画で効率的にリップシンクを行うために使用
 */
export class LipSyncSequence {
  private states: LipSyncState[];
  private startFrame: number;
  private endFrame: number;

  constructor(
    startFrame: number,
    durationFrames: number,
    options: {
      text?: string;
      audioIntensities?: number[];
      config?: Partial<LipSyncConfig>;
      fps?: number;
    } = {}
  ) {
    this.startFrame = startFrame;
    this.endFrame = startFrame + durationFrames;
    this.states = [];

    const { text, audioIntensities, config, fps = 30 } = options;

    // 事前計算
    for (let i = 0; i < durationFrames; i++) {
      const frame = startFrame + i;

      if (text) {
        // テキストベース
        this.states.push(
          calculateLipSyncFromText(frame, text, startFrame, durationFrames, fps)
        );
      } else if (audioIntensities && audioIntensities[i] !== undefined) {
        // 音声強度ベース
        this.states.push(
          calculateLipSync(frame, audioIntensities[i], true, config)
        );
      } else {
        // デフォルト（サイクル）
        this.states.push(
          calculateLipSync(frame, 0.7, true, config)
        );
      }
    }
  }

  /**
   * 指定フレームのリップシンク状態を取得
   */
  getState(frame: number): LipSyncState {
    if (frame < this.startFrame || frame >= this.endFrame) {
      return {
        vowel: "n",
        weight: 0,
        presetName: VOWEL_TO_PRESET.n,
      };
    }

    const index = frame - this.startFrame;
    return this.states[index] || {
      vowel: "n",
      weight: 0,
      presetName: VOWEL_TO_PRESET.n,
    };
  }
}

// ========================================
// フック用ヘルパー
// ========================================

/**
 * Remotionのフレームに基づいたリップシンクヘルパー
 * useCallback等でメモ化して使用することを推奨
 */
export function createLipSyncHelper(
  config: Partial<LipSyncConfig> = {}
) {
  const fullConfig = { ...DEFAULT_LIP_SYNC_CONFIG, ...config };

  return {
    /**
     * フレームと音声強度からリップシンク状態を取得
     */
    getState(
      frame: number,
      audioIntensity: number,
      isSpeaking: boolean
    ): LipSyncState {
      return calculateLipSync(frame, audioIntensity, isSpeaking, fullConfig);
    },

    /**
     * VRMに直接適用
     */
    applyToVRM(
      vrm: VRM,
      frame: number,
      audioIntensity: number,
      isSpeaking: boolean,
      blend: number = 0.5
    ): void {
      const state = calculateLipSync(frame, audioIntensity, isSpeaking, fullConfig);
      applyLipSyncToVRM(vrm, state, blend);
    },
  };
}

export default {
  calculateLipSync,
  calculateLipSyncFromText,
  applyLipSyncToVRM,
  createLipSyncHelper,
  LipSyncSequence,
  VOWEL_TO_PRESET,
  DEFAULT_LIP_SYNC_CONFIG,
};
