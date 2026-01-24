import { useCallback, useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import type { VRM } from "@pixiv/three-vrm";
import type { VRMExpressionType, VowelType } from "../components/VRMCharacter";

// ========================================
// 型定義
// ========================================

/** アニメーション設定 */
export interface VRMAnimationConfig {
  /** 呼吸の速度（1.0が標準） */
  breathingSpeed: number;
  /** 呼吸の振幅 */
  breathingAmplitude: number;
  /** 揺れの速度 */
  swaySpeed: number;
  /** 揺れの振幅 */
  swayAmplitude: number;
  /** まばたきの間隔（秒） */
  blinkInterval: number;
  /** リップシンクの感度 */
  lipSyncSensitivity: number;
}

/** ボーンアニメーションの状態 */
export interface BoneAnimationState {
  spine: { x: number; y: number; z: number };
  chest: { x: number; y: number; z: number };
  neck: { x: number; y: number; z: number };
  head: { x: number; y: number; z: number };
  leftUpperArm: { x: number; y: number; z: number };
  rightUpperArm: { x: number; y: number; z: number };
  leftHand: { x: number; y: number; z: number };
  rightHand: { x: number; y: number; z: number };
}

/** 表情アニメーションの状態 */
export interface ExpressionAnimationState {
  baseExpression: string;
  baseWeight: number;
  blinkWeight: number;
  lipSyncVowel: string;
  lipSyncWeight: number;
}

/** アニメーションフックの戻り値 */
export interface VRMAnimationResult {
  /** ボーンアニメーションの状態 */
  boneState: BoneAnimationState;
  /** 表情アニメーションの状態 */
  expressionState: ExpressionAnimationState;
  /** VRMモデルにアニメーションを適用 */
  applyToVRM: (vrm: VRM) => void;
}

// ========================================
// デフォルト設定
// ========================================

const DEFAULT_CONFIG: VRMAnimationConfig = {
  breathingSpeed: 1.0,
  breathingAmplitude: 0.003,
  swaySpeed: 1.0,
  swayAmplitude: 0.01,
  blinkInterval: 4,
  lipSyncSensitivity: 1.0,
};

// ========================================
// ユーティリティ関数
// ========================================

/**
 * イージング関数（スムーズな動きのため）
 */
function easeInOutSine(x: number): number {
  return -(Math.cos(Math.PI * x) - 1) / 2;
}

/**
 * 時間に基づいてまばたきの重みを計算
 */
function calculateBlinkWeight(time: number, interval: number): number {
  const blinkDuration = 0.15;
  const phase = time % interval;

  if (phase < blinkDuration) {
    const progress = phase / blinkDuration;
    // 閉じて開く動き
    return progress < 0.5 ? easeInOutSine(progress * 2) : easeInOutSine((1 - progress) * 2);
  }

  return 0;
}

/**
 * 母音の重みを滑らかに計算
 */
function smoothLipSync(
  frame: number,
  audioIntensity: number,
  sensitivity: number
): { vowel: VowelType; weight: number } {
  const vowels: VowelType[] = ["a", "i", "u", "e", "o"];
  const adjustedIntensity = audioIntensity * sensitivity;

  if (adjustedIntensity < 0.1) {
    return { vowel: "n", weight: 0 };
  }

  // フレームに基づいて母音を決定
  const speed = 3 + adjustedIntensity * 4;
  const vowelIndex = Math.floor(frame / speed) % vowels.length;
  const weight = Math.min(adjustedIntensity * 1.2, 1.0);

  return { vowel: vowels[vowelIndex], weight };
}

// ========================================
// メインフック
// ========================================

/**
 * VRMアニメーションを制御するカスタムフック
 *
 * Remotionのフレームベースのレンダリングに対応し、
 * 決定論的なアニメーション状態を提供します。
 *
 * @example
 * ```tsx
 * const { boneState, expressionState, applyToVRM } = useVRMAnimation({
 *   expression: "happy",
 *   isSpeaking: true,
 *   audioIntensity: 0.7,
 * });
 *
 * // useFrame内でVRMに適用
 * useFrame(() => {
 *   if (vrm) {
 *     applyToVRM(vrm);
 *   }
 * });
 * ```
 */
export function useVRMAnimation(
  options: {
    expression?: VRMExpressionType;
    isSpeaking?: boolean;
    isEmphasizing?: boolean;
    audioIntensity?: number;
    config?: Partial<VRMAnimationConfig>;
  } = {}
): VRMAnimationResult {
  const {
    expression = "neutral",
    isSpeaking = false,
    isEmphasizing = false,
    audioIntensity = 0.5,
    config: customConfig = {},
  } = options;

  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const config = { ...DEFAULT_CONFIG, ...customConfig };

  // 時間計算
  const time = frame / fps;

  // ボーンアニメーションの計算
  const boneState = useMemo((): BoneAnimationState => {
    // 呼吸
    const breathPhase = Math.sin(time * 2 * config.breathingSpeed);
    const breathOffset = breathPhase * config.breathingAmplitude;

    // 揺れ
    let swayX = Math.sin(time * 0.5 * config.swaySpeed) * config.swayAmplitude;
    let swayY = Math.sin(time * 0.8 * config.swaySpeed) * config.swayAmplitude * 0.5;

    // 話し中の追加の動き
    if (isSpeaking) {
      swayX += Math.sin(time * 2.5) * config.swayAmplitude * 1.5;
      swayY += Math.sin(time * 3) * config.swayAmplitude * 0.8;
    }

    // 強調時の追加の動き
    if (isEmphasizing) {
      swayX += Math.sin(time * 4) * config.swayAmplitude * 2;
    }

    // 頭の動き
    let headTiltZ = Math.sin(time * 0.3) * 0.02;
    let headTiltY = Math.sin(time * 0.4) * 0.01;

    if (expression === "thinking") {
      headTiltZ += 0.1;
    }

    if (isSpeaking) {
      headTiltZ += Math.sin(time * 2) * 0.03;
      headTiltY += Math.sin(time * 1.5) * 0.02;
    }

    // 肩の動き
    let shoulderRotation = 0;
    if (isSpeaking) {
      shoulderRotation = Math.sin(time * 1.5) * 0.03;
    }
    if (isEmphasizing) {
      shoulderRotation += Math.sin(time * 3) * 0.05;
    }

    // 手の動き（強調時にジェスチャー）
    let handRotationL = 0;
    let handRotationR = 0;
    if (isEmphasizing) {
      handRotationL = Math.sin(time * 2) * 0.1;
      handRotationR = Math.sin(time * 2 + Math.PI) * 0.1;
    }

    return {
      spine: { x: breathOffset, y: 0, z: swayX },
      chest: { x: breathOffset * 0.5, y: 0, z: 0 },
      neck: { x: swayY, y: 0, z: 0 },
      head: { x: 0, y: headTiltY, z: headTiltZ },
      leftUpperArm: { x: 0, y: 0, z: shoulderRotation },
      rightUpperArm: { x: 0, y: 0, z: -shoulderRotation },
      leftHand: { x: handRotationL, y: 0, z: 0 },
      rightHand: { x: handRotationR, y: 0, z: 0 },
    };
  }, [time, isSpeaking, isEmphasizing, expression, config]);

  // 表情アニメーションの計算
  const expressionState = useMemo((): ExpressionAnimationState => {
    // 表情マッピング
    const expressionMapping: Record<VRMExpressionType, string> = {
      neutral: "neutral",
      happy: "happy",
      angry: "angry",
      sad: "sad",
      surprised: "surprised",
      thinking: "neutral",
    };

    const baseExpression = expressionMapping[expression];
    const baseWeight = expression !== "neutral" ? 1.0 : 0;

    // まばたき
    const blinkWeight = calculateBlinkWeight(time, config.blinkInterval);

    // リップシンク
    const lipSync = isSpeaking
      ? smoothLipSync(frame, audioIntensity, config.lipSyncSensitivity)
      : { vowel: "n" as VowelType, weight: 0 };

    // 母音からVRMプリセットへのマッピング
    const vowelMapping: Record<VowelType, string> = {
      a: "aa",
      i: "ih",
      u: "ou",
      e: "ee",
      o: "oh",
      n: "neutral",
    };

    return {
      baseExpression,
      baseWeight,
      blinkWeight,
      lipSyncVowel: vowelMapping[lipSync.vowel],
      lipSyncWeight: lipSync.weight,
    };
  }, [time, frame, expression, isSpeaking, audioIntensity, config]);

  // VRMへの適用関数
  const applyToVRM = useCallback(
    (vrm: VRM) => {
      // 表情の適用
      if (vrm.expressionManager) {
        vrm.expressionManager.resetValues();

        // 基本表情
        if (expressionState.baseWeight > 0) {
          vrm.expressionManager.setValue(
            expressionState.baseExpression,
            expressionState.baseWeight
          );
        }

        // まばたき
        if (expressionState.blinkWeight > 0) {
          vrm.expressionManager.setValue("blink", expressionState.blinkWeight);
        }

        // リップシンク
        if (expressionState.lipSyncWeight > 0) {
          vrm.expressionManager.setValue(
            expressionState.lipSyncVowel,
            expressionState.lipSyncWeight
          );
        }

        vrm.expressionManager.update();
      }

      // ボーンの適用
      if (vrm.humanoid) {
        const bones: Array<{
          name: string;
          state: { x: number; y: number; z: number };
        }> = [
          { name: "spine", state: boneState.spine },
          { name: "chest", state: boneState.chest },
          { name: "neck", state: boneState.neck },
          { name: "head", state: boneState.head },
          { name: "leftUpperArm", state: boneState.leftUpperArm },
          { name: "rightUpperArm", state: boneState.rightUpperArm },
          { name: "leftHand", state: boneState.leftHand },
          { name: "rightHand", state: boneState.rightHand },
        ];

        for (const { name, state } of bones) {
          const bone = vrm.humanoid.getNormalizedBoneNode(
            name as Parameters<typeof vrm.humanoid.getNormalizedBoneNode>[0]
          );
          if (bone) {
            bone.rotation.x = state.x;
            bone.rotation.y = state.y;
            bone.rotation.z = state.z;
          }
        }

        vrm.humanoid.update();
      }
    },
    [boneState, expressionState]
  );

  return {
    boneState,
    expressionState,
    applyToVRM,
  };
}

// ========================================
// 特殊アニメーション用フック
// ========================================

/**
 * 入場アニメーションを制御するフック
 */
export function useVRMEntrance(options: {
  duration?: number;
  delay?: number;
} = {}): {
  scale: number;
  opacity: number;
  translateX: number;
  isComplete: boolean;
} {
  const { duration = 40, delay = 0 } = options;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const effectiveFrame = Math.max(0, frame - delay);

  const progress = spring({
    frame: effectiveFrame,
    fps,
    config: {
      damping: 15,
      stiffness: 100,
    },
  });

  const bounceProgress = spring({
    frame: Math.max(0, effectiveFrame - 10),
    fps,
    config: {
      damping: 8,
      stiffness: 150,
    },
  });

  return {
    scale: interpolate(progress, [0, 1], [0.7, 1]) + bounceProgress * 0.05,
    opacity: progress,
    translateX: interpolate(progress, [0, 1], [100, 0]),
    isComplete: effectiveFrame > duration,
  };
}

/**
 * 退場アニメーションを制御するフック
 */
export function useVRMExit(options: {
  startFrame: number;
  duration?: number;
} = { startFrame: 0 }): {
  scale: number;
  opacity: number;
  translateX: number;
  isActive: boolean;
} {
  const { startFrame, duration = 50 } = options;
  const frame = useCurrentFrame();

  const isActive = frame >= startFrame;
  const exitFrame = Math.max(0, frame - startFrame);

  const progress = interpolate(exitFrame, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // 手を振る動き
  const waveMotion = isActive ? Math.sin(exitFrame * 0.3) * 15 : 0;

  return {
    scale: 1 - progress * 0.2,
    opacity: 1 - progress,
    translateX: progress * 100 + waveMotion,
    isActive,
  };
}

/**
 * ジェスチャーアニメーションを生成するフック
 */
export function useVRMGesture(options: {
  type: "point" | "wave" | "nod" | "shake";
  trigger?: boolean;
} = { type: "nod" }): {
  rightArmRotation: { x: number; y: number; z: number };
  leftArmRotation: { x: number; y: number; z: number };
  headRotation: { x: number; y: number; z: number };
} {
  const { type, trigger = true } = options;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const time = frame / fps;

  if (!trigger) {
    return {
      rightArmRotation: { x: 0, y: 0, z: 0 },
      leftArmRotation: { x: 0, y: 0, z: 0 },
      headRotation: { x: 0, y: 0, z: 0 },
    };
  }

  switch (type) {
    case "point":
      // 指さしジェスチャー
      return {
        rightArmRotation: {
          x: -0.5,
          y: 0,
          z: -0.3 + Math.sin(time * 3) * 0.05,
        },
        leftArmRotation: { x: 0, y: 0, z: 0 },
        headRotation: { x: 0, y: -0.1, z: 0 },
      };

    case "wave":
      // 手を振るジェスチャー
      return {
        rightArmRotation: {
          x: -0.8,
          y: 0,
          z: Math.sin(time * 8) * 0.3,
        },
        leftArmRotation: { x: 0, y: 0, z: 0 },
        headRotation: { x: 0, y: 0, z: Math.sin(time * 4) * 0.05 },
      };

    case "nod":
      // うなずきジェスチャー
      return {
        rightArmRotation: { x: 0, y: 0, z: 0 },
        leftArmRotation: { x: 0, y: 0, z: 0 },
        headRotation: {
          x: Math.sin(time * 6) * 0.1,
          y: 0,
          z: 0,
        },
      };

    case "shake":
      // 首を振るジェスチャー
      return {
        rightArmRotation: { x: 0, y: 0, z: 0 },
        leftArmRotation: { x: 0, y: 0, z: 0 },
        headRotation: {
          x: 0,
          y: Math.sin(time * 8) * 0.15,
          z: 0,
        },
      };

    default:
      return {
        rightArmRotation: { x: 0, y: 0, z: 0 },
        leftArmRotation: { x: 0, y: 0, z: 0 },
        headRotation: { x: 0, y: 0, z: 0 },
      };
  }
}

export default useVRMAnimation;
