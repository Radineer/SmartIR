"use client";

import React, { useEffect, useRef, useState, useMemo, useCallback, Suspense } from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring, staticFile, delayRender, continueRender } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useFrame, useThree } from "@react-three/fiber";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { calculateLipSyncFromText, type LipSyncState, VOWEL_TO_PRESET } from "../utils/vrmLipSync";

// ========================================
// 型定義
// ========================================

/** 表情タイプ */
export type VRMExpressionType =
  | "neutral"
  | "happy"
  | "angry"
  | "sad"
  | "surprised"
  | "thinking";

/** リップシンク用の母音タイプ */
export type VowelType = "a" | "i" | "u" | "e" | "o" | "n";

/** VRMCharacterのProps */
export interface VRMCharacterProps {
  /** VRMモデルのURL */
  modelUrl: string;
  /** 表情 */
  expression?: VRMExpressionType;
  /** 話している状態か */
  isSpeaking?: boolean;
  /** 強調モード */
  isEmphasizing?: boolean;
  /** 音声の強度（0-1） */
  audioIntensity?: number;
  /** カメラ位置 */
  cameraPosition?: [number, number, number];
  /** モデルの回転（Y軸） */
  rotation?: number;
  /** モデルのスケール */
  scale?: number;
  /** モデルの位置 */
  position?: [number, number, number];
  /** 現在の発話テキスト（テキストベースリップシンク用） */
  currentText?: string;
  /** セグメント開始フレーム */
  segmentStartFrame?: number;
  /** セグメント継続フレーム数 */
  segmentDurationFrames?: number;
}

// ========================================
// VRM表情マッピング
// ========================================

/** 表情タイプからVRM BlendShapePresetへのマッピング */
const EXPRESSION_MAPPING: Record<VRMExpressionType, string> = {
  neutral: "neutral",
  happy: "happy",
  angry: "angry",
  sad: "sad",
  surprised: "surprised",
  thinking: "neutral", // VRMにはthinkingがないのでneutralを使用
};

/** 母音からVRM BlendShapePresetへのマッピング */
const VOWEL_MAPPING: Record<VowelType, string> = {
  a: "aa",
  i: "ih",
  u: "ou",
  e: "ee",
  o: "oh",
  n: "neutral",
};

// ========================================
// リップシンクユーティリティ
// ========================================

/**
 * フレームに基づいて母音を決定する
 * 話し中は音声の強度に応じて母音を変化させる
 */
function getVowelFromFrame(
  frame: number,
  audioIntensity: number,
  isSpeaking: boolean
): VowelType {
  if (!isSpeaking) return "n";

  // 音声強度が低い場合は口を閉じる
  if (audioIntensity < 0.1) return "n";

  // フレームに基づいて母音をサイクル
  const vowels: VowelType[] = ["a", "i", "u", "e", "o"];
  const cycleSpeed = 3 + audioIntensity * 4; // 音声強度に応じて速度を変える
  const vowelIndex = Math.floor(frame / cycleSpeed) % vowels.length;

  return vowels[vowelIndex];
}

/**
 * リップシンクの重みを計算
 */
function calculateLipSyncWeight(
  audioIntensity: number,
  isSpeaking: boolean
): number {
  if (!isSpeaking) return 0;
  // 口を大きく開ける（最低0.5、最大1.0）
  return Math.min(0.5 + audioIntensity * 0.5, 1.0);
}

// ========================================
// ボディアニメーションユーティリティ
// ========================================

interface BodyAnimationState {
  /** 呼吸による胸の動き */
  breathingOffset: number;
  /** 左右の揺れ */
  swayX: number;
  /** 上下の揺れ */
  swayY: number;
  /** 頭の傾き */
  headTilt: number;
  /** 肩の回転 */
  shoulderRotation: number;
}

/**
 * フレームに基づいてボディアニメーションの状態を計算
 */
function calculateBodyAnimation(
  frame: number,
  fps: number,
  isSpeaking: boolean,
  isEmphasizing: boolean,
  expression: VRMExpressionType
): BodyAnimationState {
  const time = frame / fps;

  // 呼吸アニメーション（常に適用）— 大きめに
  const breathingCycle = Math.sin(time * 1.8) * 0.5 + 0.5;
  const breathingOffset = breathingCycle * 0.025;

  // 左右の揺れ — 大きく
  let swayX = Math.sin(time * 0.4) * 0.04 + Math.sin(time * 0.7) * 0.02;
  if (isSpeaking) {
    swayX += Math.sin(time * 2.0) * 0.06 + Math.sin(time * 3.2) * 0.03;
  }
  if (isEmphasizing) {
    swayX += Math.sin(time * 4) * 0.08;
  }

  // 上下の揺れ — 大きく
  let swayY = Math.sin(time * 0.6) * 0.02;
  if (isSpeaking) {
    swayY += Math.sin(time * 2.5) * 0.04 + Math.sin(time * 1.7) * 0.02;
  }

  // 頭の傾き — 大きく
  let headTilt = Math.sin(time * 0.3) * 0.06 + Math.sin(time * 0.7) * 0.03;
  if (expression === "thinking") {
    headTilt += 0.15;
  }
  if (expression === "happy") {
    headTilt += Math.sin(time * 3) * 0.05;
  }
  if (isSpeaking) {
    headTilt += Math.sin(time * 1.8) * 0.08;
  }

  // 肩の回転 — 大きく
  let shoulderRotation = Math.sin(time * 0.5) * 0.01;
  if (isSpeaking) {
    shoulderRotation += Math.sin(time * 1.5) * 0.06;
  }
  if (isEmphasizing) {
    shoulderRotation += Math.sin(time * 3) * 0.1;
  }

  return {
    breathingOffset,
    swayX,
    swayY,
    headTilt,
    shoulderRotation,
  };
}

// ========================================
// まばたきユーティリティ
// ========================================

/**
 * まばたきの重みを計算
 * 3-5秒ごとにランダムにまばたき
 */
function calculateBlinkWeight(frame: number, fps: number): number {
  const time = frame / fps;
  const blinkInterval = 4; // 4秒ごと
  const blinkDuration = 0.15; // まばたきの長さ

  // 疑似ランダムなまばたきタイミング
  const blinkPhase = time % blinkInterval;

  if (blinkPhase < blinkDuration) {
    // まばたき中
    const progress = blinkPhase / blinkDuration;
    // 閉じて開く動き
    if (progress < 0.5) {
      return progress * 2; // 閉じる
    } else {
      return (1 - progress) * 2; // 開く
    }
  }

  return 0;
}

// ========================================
// VRMモデルコンポーネント（Three.js内部）
// ========================================

interface VRMModelProps {
  modelUrl: string;
  expression: VRMExpressionType;
  isSpeaking: boolean;
  isEmphasizing: boolean;
  audioIntensity: number;
  rotation: number;
  scale: number;
  position: [number, number, number];
  currentText?: string;
  segmentStartFrame?: number;
  segmentDurationFrames?: number;
}

const VRMModel: React.FC<VRMModelProps> = ({
  modelUrl,
  expression,
  isSpeaking,
  isEmphasizing,
  audioIntensity,
  rotation,
  scale,
  position,
  currentText,
  segmentStartFrame,
  segmentDurationFrames,
}) => {
  const vrmRef = useRef<VRM | null>(null);
  const [vrm, setVrm] = useState<VRM | null>(null);
  const [handle] = useState(() => delayRender("Loading VRM model"));
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // staticFile()でRemotionサーバー上の正しいURLを解決
  const resolvedModelUrl = useMemo(() => {
    if (modelUrl.startsWith("/")) {
      try {
        return staticFile(modelUrl.slice(1));
      } catch {
        return modelUrl;
      }
    }
    return modelUrl;
  }, [modelUrl]);

  const fallbackUrl = useMemo(() => {
    try {
      return staticFile("models/vrm/AvatarSample_A.vrm");
    } catch {
      return "/models/vrm/AvatarSample_A.vrm";
    }
  }, []);

  // VRMモデルの読み込み（delayRenderでフレームレンダリングを待機）
  useEffect(() => {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    const loadModel = (url: string, isFallback = false) => {
      loader.load(
        url,
        (gltf) => {
          const loadedVrm = gltf.userData.vrm as VRM;
          if (loadedVrm) {
            VRMUtils.removeUnnecessaryVertices(gltf.scene);
            VRMUtils.removeUnnecessaryJoints(gltf.scene);
            loadedVrm.scene.rotation.y = Math.PI;
            vrmRef.current = loadedVrm;
            setVrm(loadedVrm);
            continueRender(handle);
          } else {
            continueRender(handle);
          }
        },
        undefined,
        (error) => {
          console.error(`VRM loading error (${url}):`, error);
          if (!isFallback && url !== fallbackUrl) {
            console.warn(`Falling back to ${fallbackUrl}`);
            loadModel(fallbackUrl, true);
          } else {
            // フォールバックも失敗した場合はレンダリングを続行
            continueRender(handle);
          }
        }
      );
    };

    loadModel(resolvedModelUrl);

    return () => {
      if (vrmRef.current) {
        VRMUtils.deepDispose(vrmRef.current.scene);
      }
    };
  }, [resolvedModelUrl, fallbackUrl, handle]);

  // フレームごとの更新（Remotionのフレームに同期）
  useFrame(() => {
    if (!vrm) return;

    const deltaTime = 1 / fps;

    // === 表情の更新 ===
    if (vrm.expressionManager) {
      // すべての表情をリセット
      vrm.expressionManager.resetValues();

      // 基本表情を設定（強めに適用）
      const expressionName = EXPRESSION_MAPPING[expression];
      if (expressionName !== "neutral") {
        vrm.expressionManager.setValue(expressionName, 1.0);
      }
      // 追加: happyの時は口角も上げる
      if (expression === "happy") {
        vrm.expressionManager.setValue("relaxed", 0.3);
      }

      // リップシンク（テキストベース優先、フォールバックはフレームベース）
      if (isSpeaking) {
        if (currentText && segmentStartFrame !== undefined && segmentDurationFrames) {
          // テキストベースリップシンク: 日本語文字→母音マッピング
          const lipState = calculateLipSyncFromText(
            frame,
            currentText,
            segmentStartFrame,
            segmentDurationFrames,
            fps
          );
          vrm.expressionManager.setValue(lipState.presetName, lipState.weight);
        } else {
          // フォールバック: フレームベースサイクル
          const vowel = getVowelFromFrame(frame, audioIntensity, isSpeaking);
          const lipWeight = calculateLipSyncWeight(audioIntensity, isSpeaking);
          const vowelPreset = VOWEL_MAPPING[vowel];
          vrm.expressionManager.setValue(vowelPreset, lipWeight);
        }
      }

      // まばたき
      const blinkWeight = calculateBlinkWeight(frame, fps);
      vrm.expressionManager.setValue("blink", blinkWeight);

      // 表情の更新を適用
      vrm.expressionManager.update();
    }

    // === ボディアニメーションの更新 ===
    if (vrm.humanoid) {
      const bodyAnim = calculateBodyAnimation(
        frame,
        fps,
        isSpeaking,
        isEmphasizing,
        expression
      );

      // 背骨の動き（呼吸）
      const spine = vrm.humanoid.getNormalizedBoneNode("spine");
      if (spine) {
        spine.rotation.x = bodyAnim.breathingOffset;
        spine.rotation.z = bodyAnim.swayX;
      }

      // 胸の動き
      const chest = vrm.humanoid.getNormalizedBoneNode("chest");
      if (chest) {
        chest.rotation.x = bodyAnim.breathingOffset * 0.5;
      }

      // 頭の動き
      const head = vrm.humanoid.getNormalizedBoneNode("head");
      if (head) {
        head.rotation.z = bodyAnim.headTilt;
        head.rotation.y = bodyAnim.swayX * 2;
      }

      // 首の動き
      const neck = vrm.humanoid.getNormalizedBoneNode("neck");
      if (neck) {
        neck.rotation.x = bodyAnim.swayY;
      }

      // 腕をTポーズから自然な位置に下ろす + 話し中の動き
      const leftUpperArm = vrm.humanoid.getNormalizedBoneNode("leftUpperArm");
      const rightUpperArm = vrm.humanoid.getNormalizedBoneNode("rightUpperArm");
      const leftLowerArm = vrm.humanoid.getNormalizedBoneNode("leftLowerArm");
      const rightLowerArm = vrm.humanoid.getNormalizedBoneNode("rightLowerArm");

      // 上腕を下ろす（Z軸回転で体の横に）
      if (leftUpperArm) {
        leftUpperArm.rotation.z = 1.1 + bodyAnim.shoulderRotation;
        leftUpperArm.rotation.x = 0.1;
      }
      if (rightUpperArm) {
        rightUpperArm.rotation.z = -1.1 - bodyAnim.shoulderRotation;
        rightUpperArm.rotation.x = 0.1;
      }
      // 前腕を少し曲げる
      if (leftLowerArm) {
        leftLowerArm.rotation.z = 0.15;
      }
      if (rightLowerArm) {
        rightLowerArm.rotation.z = -0.15;
      }

      // 旧コード互換（使われないがコンパイル通すため）
      const leftShoulder = leftUpperArm;
      const rightShoulder = rightUpperArm;
      if (leftShoulder) {
        // already set above
      }
      if (rightShoulder) {
        rightShoulder.rotation.z = -bodyAnim.shoulderRotation;
      }

      // ヒューマノイドの更新
      vrm.humanoid.update();
    }

    // SpringBoneの更新
    if (vrm.springBoneManager) {
      vrm.springBoneManager.update(deltaTime);
    }

    // VRM全体の更新
    vrm.update(deltaTime);
  });

  if (!vrm) {
    return null;
  }

  return (
    <primitive
      object={vrm.scene}
      scale={scale}
      position={position}
      rotation={[0, rotation, 0]}
    />
  );
};

// ========================================
// カメラ設定コンポーネント
// ========================================

interface CameraSetupProps {
  position: [number, number, number];
}

const CameraSetup: React.FC<CameraSetupProps> = ({ position }) => {
  const { camera } = useThree();

  useEffect(() => {
    camera.position.set(...position);
    camera.lookAt(0, 1.0, 0); // 上半身にフォーカス
  }, [camera, position]);

  return null;
};

// ========================================
// 照明設定コンポーネント
// ========================================

const Lighting: React.FC = () => {
  return (
    <>
      {/* 環境光 — 明るめ */}
      <ambientLight intensity={0.8} />

      {/* メインキーライト — 右上から強め */}
      <directionalLight
        position={[2, 3, 2]}
        intensity={1.4}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />

      {/* フィルライト — 左から */}
      <directionalLight position={[-3, 2, 1]} intensity={0.6} color="#b4c7ff" />

      {/* リムライト — 後ろから強めに輪郭を出す */}
      <directionalLight position={[0, 2, -3]} intensity={0.8} color="#8b5cf6" />

      {/* 正面フェイスライト — 顔を明るく */}
      <pointLight position={[0, 1.5, 2.0]} intensity={0.6} />

      {/* 下からのアップライト — 立体感 */}
      <pointLight position={[0, 0.3, 1.5]} intensity={0.2} color="#6366f1" />
    </>
  );
};

// ========================================
// ローディングフォールバック
// ========================================

const LoadingFallback: React.FC = () => {
  return (
    <mesh>
      <boxGeometry args={[0.5, 0.5, 0.5]} />
      <meshStandardMaterial color="#888888" />
    </mesh>
  );
};

// ========================================
// メインコンポーネント
// ========================================

export const VRMCharacter: React.FC<VRMCharacterProps> = ({
  modelUrl,
  expression = "neutral",
  isSpeaking = false,
  isEmphasizing = false,
  audioIntensity = 0.5,
  cameraPosition = [0, 1.3, 1.8],
  rotation = 0,
  scale = 1,
  position = [0, 0, 0],
  currentText,
  segmentStartFrame,
  segmentDurationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps, width: videoWidth, height } = useVideoConfig();

  // キャラクターコンテナはフル幅（親がサイズを制御）
  const canvasWidth = videoWidth;
  const canvasHeight = height;

  // 入場アニメーション
  const entranceProgress = spring({
    frame,
    fps,
    config: {
      damping: 20,
      stiffness: 80,
    },
  });

  const entranceScale = interpolate(entranceProgress, [0, 1], [0.8, 1]);
  const entranceOpacity = entranceProgress;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        opacity: entranceOpacity,
      }}
    >
      <ThreeCanvas
        width={canvasWidth}
        height={canvasHeight}
        camera={{
          fov: 30,
          near: 0.1,
          far: 100,
          position: cameraPosition,
        }}
        gl={{
          antialias: true,
          alpha: true,
          preserveDrawingBuffer: true,
        }}
        style={{
          background: "transparent",
        }}
      >
        <CameraSetup position={cameraPosition} />
        <Lighting />

        <Suspense fallback={<LoadingFallback />}>
          <VRMModel
            modelUrl={modelUrl}
            expression={expression}
            isSpeaking={isSpeaking}
            isEmphasizing={isEmphasizing}
            audioIntensity={audioIntensity}
            rotation={rotation}
            scale={scale * entranceScale}
            position={position}
            currentText={currentText}
            segmentStartFrame={segmentStartFrame}
            segmentDurationFrames={segmentDurationFrames}
          />
        </Suspense>
      </ThreeCanvas>
    </div>
  );
};

// ========================================
// VRMシーンラッパー（IRAnalysis互換）
// ========================================

interface VRMSceneProps {
  /** VRMモデルのURL（デフォルト: /models/vrm/iris.vrm） */
  vrmModelUrl?: string;
  /** フォールバック用の静止画（VRM読み込み失敗時） */
  characterImage?: string;
  /** 表情タイプ */
  expression?: "neutral" | "happy" | "thinking" | "surprised" | "angry" | "sad";
  /** 話している状態かどうか */
  isSpeaking?: boolean;
  /** 強調モード */
  isEmphasizing?: boolean;
  /** アニメーションフェーズ */
  animationPhase?: "entrance" | "active" | "exit";
  /** 音声の強度（0-1） */
  audioIntensity?: number;
  /** VRMを使用するかどうか */
  useVRM?: boolean;
  /** 現在の発話テキスト（テキストベースリップシンク用） */
  currentText?: string;
  /** セグメント開始フレーム */
  segmentStartFrame?: number;
  /** セグメント継続フレーム数 */
  segmentDurationFrames?: number;
}

/**
 * VTuberSceneの代替として使用可能なVRMシーンコンポーネント
 * 既存のVTuberSceneと同じインターフェースを持ちながら、
 * VRMモデルを使用した3Dアニメーションを提供
 */
export const VRMScene: React.FC<VRMSceneProps> = ({
  vrmModelUrl = "/models/vrm/iris.vrm",
  expression = "neutral",
  isSpeaking = false,
  isEmphasizing = false,
  audioIntensity = 0.5,
  useVRM = true,
  currentText,
  segmentStartFrame,
  segmentDurationFrames,
}) => {
  // VRMが無効な場合は空を返す（VTuberSceneにフォールバック）
  if (!useVRM) {
    return null;
  }

  // expressionをVRMExpressionTypeに変換
  const vrmExpression: VRMExpressionType =
    expression === "thinking" ? "thinking" : expression;

  return (
    <VRMCharacter
      modelUrl={vrmModelUrl}
      expression={vrmExpression}
      isSpeaking={isSpeaking}
      isEmphasizing={isEmphasizing}
      audioIntensity={audioIntensity}
      cameraPosition={[0, 1.1, 1.8]}
      scale={1.0}
      position={[0, 0, 0]}
      currentText={currentText}
      segmentStartFrame={segmentStartFrame}
      segmentDurationFrames={segmentDurationFrames}
    />
  );
};

export default VRMCharacter;
