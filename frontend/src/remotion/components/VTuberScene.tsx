import React, { useMemo } from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig, OffthreadVideo, Loop } from "remotion";
import { Img, staticFile } from "remotion";

interface VTuberSceneProps {
  /** キャラクター画像パス（staticFile経由） */
  characterImage?: string;
  /** 表情タイプ */
  expression?: "neutral" | "happy" | "thinking" | "surprised" | "concerned" | "confident";
  /** 話している状態かどうか */
  isSpeaking?: boolean;
  /** 強調モード（ポイント説明時など） */
  isEmphasizing?: boolean;
  /** アニメーションフェーズ */
  animationPhase?: "entrance" | "active" | "exit";
  /** 音声の強度（0-1、リップシンク用） */
  audioIntensity?: number;
  /** 現在のセグメントの開始フレーム（リップシンク用） */
  segmentStartFrame?: number;
  /** 現在のセグメントの継続フレーム数（リップシンク用） */
  segmentDurationFrames?: number;
  /** アニメーション動画を使用するか（Midjourney生成アニメ） */
  useAnimatedVideo?: boolean;
  /** アニメーション動画パス */
  animatedVideoPath?: string;
}

// 表情に応じた画像パスマッピング
const expressionImages: Record<string, string> = {
  neutral: "/images/iris/iris-normal.png",
  happy: "/images/iris/iris-happy.png",
  thinking: "/images/iris/iris-thinking.png",
  surprised: "/images/iris/iris-normal.png",
  speaking: "/images/iris/iris-speaking.png",
  concerned: "/images/iris/iris-thinking.png",
  confident: "/images/iris/iris-happy.png",
  analysis: "/images/iris/iris-analysis.png",
};

// 口の形状（リップシンク用）
const mouthShapes = {
  closed: "/images/iris/iris-mouth-closed.png",
  half: "/images/iris/iris-mouth-half.png",
  open: "/images/iris/iris-mouth-open.png",
};

// 母音に対応する口の形状パターン（日本語向け）
// A=開、I=半開、U=半開、E=半開、O=開、N=閉
type MouthShape = "closed" | "half" | "open";

// 自然なリップシンクのための音素シーケンス生成
const generateLipSyncPattern = (frame: number, intensity: number): MouthShape => {
  // 音声強度に応じたパターン変化速度
  const speed = 4 + (1 - intensity) * 4; // 強度が高いほど速く
  const phase = Math.floor(frame / speed);

  // 自然な発話パターン（開→半開→閉の繰り返しではなく、ランダム性を持たせる）
  const patterns: MouthShape[][] = [
    ["closed", "half", "open", "half", "closed"],           // 基本パターン
    ["closed", "open", "half", "open", "closed"],           // 強調パターン
    ["half", "open", "half", "closed", "half"],             // 連続発話
    ["closed", "half", "half", "open", "closed"],           // ゆっくり
    ["open", "half", "closed", "half", "open"],             // 活発
  ];

  // フレームベースでパターンを選択
  const patternIndex = Math.floor(frame / 30) % patterns.length;
  const pattern = patterns[patternIndex];

  return pattern[phase % pattern.length];
};

// まばたきのタイミングを計算（平均3〜5秒に1回）
const shouldBlink = (frame: number, fps: number): boolean => {
  // まばたきの周期を計算（疑似ランダム）
  const blinkCycle = Math.floor(fps * (3 + (Math.sin(frame * 0.01) + 1) * 1)); // 3〜5秒周期
  const frameInCycle = frame % blinkCycle;
  // まばたきは3フレーム続く
  return frameInCycle >= 0 && frameInCycle < 3;
};

// まばたきの目の開き具合（0=閉じ、1=開き）
const getBlinkProgress = (frame: number, fps: number): number => {
  const blinkCycle = Math.floor(fps * (3 + (Math.sin(frame * 0.01) + 1) * 1));
  const frameInCycle = frame % blinkCycle;

  if (frameInCycle < 3) {
    // まばたき中：0→1→0
    if (frameInCycle === 0) return 0.3;
    if (frameInCycle === 1) return 0;
    return 0.3;
  }
  return 1; // 目を開いている
};

export const VTuberScene: React.FC<VTuberSceneProps> = ({
  characterImage,
  expression = "neutral",
  isSpeaking = false,
  isEmphasizing = false,
  animationPhase = "active",
  audioIntensity = 0.5,
  segmentStartFrame,
  segmentDurationFrames,
  useAnimatedVideo = false, // 改良された口パクシステムを使用
  animatedVideoPath = "/images/iris/iris-animated.mp4",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // === 1. 呼吸アニメーション（常に動く） ===
  // ゆっくりした呼吸で上下に揺れる
  const breathPhase = frame * 0.08;
  const breathingY = Math.sin(breathPhase) * 6;
  const breathingScale = 1 + Math.sin(breathPhase) * 0.008;

  // === 2. アイドル時の体の揺れ（常に動く） ===
  const idleSwayX = Math.sin(frame * 0.025) * 4;
  const idleSwayRotate = Math.sin(frame * 0.03) * 1.5;

  // === 3. 話している時のアニメーション ===
  // 話し中は活発に動く
  const speakingBounceY = isSpeaking
    ? Math.sin(frame * 0.2) * 8 + Math.sin(frame * 0.35) * 4
    : 0;

  const speakingSwayX = isSpeaking
    ? Math.sin(frame * 0.15) * 10 + Math.sin(frame * 0.08) * 5
    : 0;

  const speakingRotate = isSpeaking
    ? Math.sin(frame * 0.12) * 3 + Math.sin(frame * 0.07) * 1.5
    : 0;

  // 音声強度に応じたスケール（話すと少し大きくなる）
  const speakingScale = isSpeaking
    ? 1 + Math.sin(frame * 0.25) * 0.02 * audioIntensity
    : 1;

  // === 4. 頭の動き（うなずき・傾き） ===
  // 話している時に小さくうなずく
  const headNodY = isSpeaking
    ? Math.sin(frame * 0.18) * 3
    : 0;

  const headTilt = isSpeaking
    ? Math.sin(frame * 0.1) * 2
    : Math.sin(frame * 0.04) * 0.8;

  // === 5. 表情に応じた動き ===
  let expressionBounce = 0;
  let expressionScale = 1;
  let expressionRotate = 0;

  switch (expression) {
    case "happy":
      // 嬉しい時は弾む
      expressionBounce = Math.sin(frame * 0.2) * 5;
      expressionScale = 1.02 + Math.sin(frame * 0.15) * 0.01;
      break;
    case "thinking":
      // 考え中は傾く
      expressionRotate = 5 + Math.sin(frame * 0.05) * 2;
      expressionBounce = Math.sin(frame * 0.08) * 2;
      break;
    case "surprised":
      // 驚きはジャンプ
      const surpriseFrame = frame % 20;
      expressionBounce = surpriseFrame < 10 ? -15 * (1 - surpriseFrame / 10) : 0;
      expressionScale = 1.05;
      break;
    case "concerned":
      // 心配は小さく揺れる
      expressionBounce = Math.sin(frame * 0.1) * 3;
      expressionRotate = Math.sin(frame * 0.08) * 2;
      break;
    case "confident":
      // 自信は大きく堂々と
      expressionScale = 1.03;
      expressionBounce = Math.sin(frame * 0.12) * 4;
      break;
  }

  // === 6. 強調時のアニメーション ===
  const emphasisPulse = isEmphasizing
    ? Math.sin(frame * 0.3) * 0.05
    : 0;

  const emphasisBounce = isEmphasizing
    ? Math.abs(Math.sin(frame * 0.25)) * -10
    : 0;

  // === 7. 登場・退場アニメーション ===
  const entranceFrames = 40;
  const exitStartFrame = durationInFrames - 50;

  let phaseTranslateX = 0;
  let phaseOpacity = 1;
  let phaseScale = 1;
  let phaseRotate = 0;

  if (animationPhase === "entrance" || frame < entranceFrames) {
    const progress = spring({
      frame,
      fps,
      config: { damping: 12, stiffness: 80 },
    });
    phaseTranslateX = interpolate(progress, [0, 1], [400, 0]);
    phaseOpacity = progress;
    phaseScale = 0.7 + progress * 0.3;
    phaseRotate = interpolate(progress, [0, 1], [15, 0]);
  }

  if (animationPhase === "exit" || frame > exitStartFrame) {
    const exitProgress = interpolate(
      frame,
      [exitStartFrame, durationInFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    // 手を振りながら退場
    const waveMotion = Math.sin(frame * 0.4) * 15;
    phaseTranslateX = exitProgress * 150 + waveMotion;
    phaseOpacity = 1 - exitProgress;
    phaseScale = 1 - exitProgress * 0.3;
    phaseRotate = waveMotion * 0.3;
  }

  // === 8. 高度なリップシンクシステム ===
  // 口の形状を音声強度とフレームに基づいて決定
  const currentMouthShape = useMemo((): MouthShape => {
    if (!isSpeaking) return "closed";

    // 音声強度に基づいてリップシンクパターンを生成
    return generateLipSyncPattern(frame, audioIntensity);
  }, [isSpeaking, frame, audioIntensity]);

  // ベース画像（表情）と口の形状画像を分離
  const baseImage = useMemo(() => {
    if (characterImage) return characterImage;
    return expressionImages[expression] || expressionImages.neutral;
  }, [characterImage, expression]);

  // まばたき状態
  const blinkProgress = getBlinkProgress(frame, fps);
  const isBlinking = blinkProgress < 1;

  // 口の形状に応じた画像を選択（3段階リップシンク）
  const currentImage = useMemo(() => {
    if (characterImage) return characterImage;

    if (isSpeaking) {
      // 3段階の口パク（閉じ→半開き→全開）
      return mouthShapes[currentMouthShape];
    }

    return expressionImages[expression] || expressionImages.neutral;
  }, [characterImage, expression, isSpeaking, currentMouthShape]);

  // === 最終的なトランスフォーム値の計算 ===
  const finalTranslateX =
    idleSwayX +
    speakingSwayX +
    phaseTranslateX;

  const finalTranslateY =
    breathingY +
    speakingBounceY +
    headNodY +
    expressionBounce +
    emphasisBounce;

  const finalScale =
    breathingScale *
    speakingScale *
    expressionScale *
    phaseScale *
    (1 + emphasisPulse);

  const finalRotate =
    idleSwayRotate +
    speakingRotate +
    headTilt +
    expressionRotate +
    phaseRotate;

  // === 表情フィルター ===
  const getExpressionFilter = () => {
    switch (expression) {
      case "happy":
        return "brightness(1.1) saturate(1.1)";
      case "thinking":
        return "brightness(0.95)";
      case "surprised":
        return "brightness(1.15) contrast(1.05)";
      case "concerned":
        return "brightness(0.92) saturate(0.9)";
      case "confident":
        return "brightness(1.12) saturate(1.1)";
      default:
        return "brightness(1)";
    }
  };

  // === 話し中のビジュアルインジケーター ===
  const renderSpeakingGlow = () => {
    if (!isSpeaking) return null;

    const glowIntensity = 0.3 + audioIntensity * 0.4;
    const glowPulse = Math.sin(frame * 0.15) * 0.1;

    return (
      <div
        style={{
          position: "absolute",
          inset: -20,
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(100, 180, 255, ${glowIntensity + glowPulse}) 0%, transparent 70%)`,
          pointerEvents: "none",
          filter: "blur(20px)",
        }}
      />
    );
  };

  // === 表情パーティクル ===
  const renderExpressionParticles = () => {
    if (expression === "happy" && isSpeaking) {
      return (
        <>
          {[0, 1, 2].map((i) => {
            const particleY = interpolate(
              (frame + i * 15) % 50,
              [0, 50],
              [0, -50]
            );
            const particleOpacity = interpolate(
              (frame + i * 15) % 50,
              [0, 25, 50],
              [0, 1, 0]
            );
            const particleX = Math.sin(frame * 0.1 + i * 2) * 30;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  top: "15%",
                  left: `${40 + i * 15}%`,
                  transform: `translate(${particleX}px, ${particleY}px)`,
                  opacity: particleOpacity,
                  fontSize: 20,
                  pointerEvents: "none",
                }}
              >
                ✨
              </div>
            );
          })}
        </>
      );
    }

    if (expression === "thinking") {
      return (
        <div
          style={{
            position: "absolute",
            top: "5%",
            right: "15%",
            display: "flex",
            gap: 10,
          }}
        >
          {[0, 1, 2].map((i) => {
            const dotOpacity = interpolate(
              Math.sin(frame * 0.08 + i * 1.2),
              [-1, 1],
              [0.3, 1]
            );
            return (
              <div
                key={i}
                style={{
                  width: 12 - i * 2,
                  height: 12 - i * 2,
                  borderRadius: "50%",
                  backgroundColor: "#87CEEB",
                  opacity: dotOpacity,
                  boxShadow: "0 0 10px rgba(135, 206, 235, 0.6)",
                }}
              />
            );
          })}
        </div>
      );
    }

    if (expression === "concerned") {
      const sweatY = interpolate((frame % 40), [0, 40], [0, 15]);
      const sweatOpacity = interpolate((frame % 40), [0, 20, 40], [0, 1, 0]);
      return (
        <div
          style={{
            position: "absolute",
            top: "8%",
            right: "25%",
            transform: `translateY(${sweatY}px)`,
            opacity: sweatOpacity,
          }}
        >
          <div
            style={{
              width: 10,
              height: 16,
              borderRadius: "0 0 50% 50%",
              background: "linear-gradient(180deg, rgba(100,180,255,0.8) 0%, rgba(150,210,255,0.4) 100%)",
            }}
          />
        </div>
      );
    }

    if (expression === "confident") {
      return (
        <>
          {[0, 1].map((i) => {
            const starRotate = frame * 3 + i * 90;
            const starPulse = interpolate(
              Math.sin(frame * 0.1 + i * 2),
              [-1, 1],
              [0.5, 1]
            );
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  top: `${5 + i * 8}%`,
                  right: `${15 + i * 12}%`,
                  fontSize: 22 - i * 6,
                  opacity: starPulse,
                  transform: `rotate(${starRotate}deg)`,
                  color: "#FFD700",
                  textShadow: "0 0 15px rgba(255, 215, 0, 0.8)",
                }}
              >
                ★
              </div>
            );
          })}
        </>
      );
    }

    return null;
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* キャラクター背景グラデーション（白背景をブレンド） */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          right: 0,
          width: "120%",
          height: "110%",
          background: `
            radial-gradient(ellipse 80% 90% at 50% 60%,
              rgba(255, 255, 255, 0.95) 0%,
              rgba(200, 210, 230, 0.8) 30%,
              rgba(102, 126, 234, 0.4) 60%,
              transparent 80%
            )
          `,
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      {/* 話し中のグロー効果 */}
      {renderSpeakingGlow()}

      {/* キャラクター画像コンテナ */}
      <div
        style={{
          position: "relative",
          transform: `
            translateX(${finalTranslateX}px)
            translateY(${finalTranslateY}px)
            scale(${finalScale})
            rotate(${finalRotate}deg)
          `,
          transformOrigin: "center bottom",
          opacity: phaseOpacity,
          filter: getExpressionFilter(),
          transition: "filter 0.2s ease",
          zIndex: 1,
        }}
      >
        {/* メインキャラクター */}
        <div style={{ position: "relative" }}>
          {/* 発話中: 口パク全身画像を高速切り替え / 非発話時: 表情差分 or アニメ動画 */}
          {isSpeaking ? (
            <Img
              src={staticFile(mouthShapes[currentMouthShape])}
              style={{
                maxHeight: "100%",
                maxWidth: "100%",
                objectFit: "contain",
                filter: "drop-shadow(0 10px 30px rgba(0,0,0,0.3))",
              }}
            />
          ) : useAnimatedVideo ? (
            <Loop durationInFrames={Math.ceil(5.208 * fps)}>
              <OffthreadVideo
                src={staticFile(animatedVideoPath)}
                style={{
                  maxHeight: "100%",
                  maxWidth: "100%",
                  objectFit: "contain",
                  filter: "drop-shadow(0 10px 30px rgba(0,0,0,0.3))",
                }}
                muted
              />
            </Loop>
          ) : (
            <Img
              src={staticFile(currentImage)}
              style={{
                maxHeight: "100%",
                maxWidth: "100%",
                objectFit: "contain",
                filter: "drop-shadow(0 10px 30px rgba(0,0,0,0.3))",
              }}
            />
          )}
        </div>

        {/* 表情パーティクル */}
        {renderExpressionParticles()}
      </div>

      {/* 下部フェードアウト（自然なブレンド） */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "15%",
          background: "linear-gradient(to top, rgba(15, 15, 26, 1) 0%, transparent 100%)",
          pointerEvents: "none",
          zIndex: 2,
        }}
      />
    </div>
  );
};
