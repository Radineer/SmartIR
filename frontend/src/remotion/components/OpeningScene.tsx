import React from "react";
import {
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
  Img,
  staticFile,
  Easing,
} from "remotion";

interface OpeningSceneProps {
  /** OP表示時間（フレーム数）- 5秒 = 150フレーム */
  durationFrames?: number;
  /** キャラクター画像パス */
  characterImage?: string;
  /** 本日の日付 */
  date?: string;
  /** 動画タイトル */
  title?: string;
}

// OP: 5秒 = 150フレーム
export const OpeningScene: React.FC<OpeningSceneProps> = ({
  durationFrames = 150,
  characterImage = "/images/iris/iris-normal.png",
  date,
  title = "本日のマーケット分析",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 今日の日付を取得（propsで渡されない場合）
  const displayDate = date || new Date().toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // === アニメーションタイミング ===
  // Phase 1: 背景フェードイン (0-20f)
  const bgOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Phase 2: ロゴ登場 (15-45f)
  const logoOpacity = interpolate(frame, [15, 35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const logoScale = spring({
    frame: Math.max(0, frame - 15),
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  // Phase 3: サブタイトル (40-70f)
  const subtitleOpacity = interpolate(frame, [40, 60], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleSlideX = interpolate(frame, [40, 70], [-80, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // Phase 4: キャラクター登場 (60-100f)
  const characterOpacity = interpolate(frame, [60, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const characterScale = spring({
    frame: Math.max(0, frame - 60),
    fps,
    config: { damping: 12, stiffness: 80 },
  });
  const characterFloat = frame >= 80
    ? Math.sin((frame - 80) * 0.08) * 10
    : 0;

  // Phase 5: 日付・タイトル (90-130f)
  const infoOpacity = interpolate(frame, [90, 110], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const infoSlideY = interpolate(frame, [90, 120], [30, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // 装飾ライン
  const lineWidth = interpolate(frame, [25, 60], [0, 500], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // 背景のパルス
  const bgPulse = interpolate(Math.sin(frame * 0.05), [-1, 1], [0.8, 1]);

  // コーナー装飾
  const cornerOpacity = interpolate(frame, [20, 40], [0, 0.8], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "#0a0a14",
        overflow: "hidden",
      }}
    >
      {/* 背景グラデーション */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: bgOpacity,
          background: `
            radial-gradient(ellipse at 50% 40%, rgba(102, 126, 234, ${0.5 * bgPulse}) 0%, transparent 55%),
            radial-gradient(ellipse at 80% 20%, rgba(118, 75, 162, 0.4) 0%, transparent 45%),
            radial-gradient(ellipse at 20% 70%, rgba(59, 130, 246, 0.35) 0%, transparent 50%),
            radial-gradient(ellipse at 90% 80%, rgba(236, 72, 153, 0.2) 0%, transparent 40%),
            linear-gradient(180deg, #12121f 0%, #0a0a14 50%, #050508 100%)
          `,
        }}
      />

      {/* グリッドオーバーレイ */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: bgOpacity * 0.5,
          backgroundImage: `
            linear-gradient(rgba(102, 126, 234, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(102, 126, 234, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
        }}
      />

      {/* フローティングパーティクル */}
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", opacity: bgOpacity }}>
        {[...Array(12)].map((_, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              width: 80 + i * 30,
              height: 80 + i * 30,
              borderRadius: "50%",
              background: `radial-gradient(circle, rgba(102, 126, 234, ${0.05 + (i % 3) * 0.02}) 0%, transparent 70%)`,
              left: `${5 + i * 8}%`,
              top: `${15 + Math.sin(i * 0.9) * 35}%`,
              transform: `translateY(${Math.sin(frame * 0.025 + i * 0.7) * 25}px)`,
              filter: "blur(2px)",
            }}
          />
        ))}
      </div>

      {/* ライトビーム */}
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", opacity: bgOpacity * 0.6 }}>
        {[
          { angle: -30, width: 150, delay: 0, color: "rgba(102, 126, 234, 0.15)" },
          { angle: -15, width: 80, delay: 10, color: "rgba(118, 75, 162, 0.12)" },
          { angle: 10, width: 120, delay: 5, color: "rgba(59, 130, 246, 0.1)" },
          { angle: 25, width: 100, delay: 15, color: "rgba(167, 139, 250, 0.12)" },
        ].map((beam, i) => {
          const beamOpacity = interpolate(
            Math.sin((frame - beam.delay) * 0.03),
            [-1, 1],
            [0.3, 1]
          );
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                top: "-50%",
                left: "50%",
                width: beam.width,
                height: "200%",
                background: `linear-gradient(180deg, ${beam.color}, transparent 80%)`,
                transform: `translateX(-50%) rotate(${beam.angle}deg)`,
                opacity: beamOpacity,
                filter: "blur(20px)",
              }}
            />
          );
        })}
      </div>

      {/* メインコンテンツ */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* ロゴ */}
        <div
          style={{
            opacity: logoOpacity,
            transform: `scale(${Math.min(logoScale, 1.1)})`,
            marginBottom: 20,
            textAlign: "center",
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: 82,
              fontWeight: "bold",
              color: "white",
              letterSpacing: "0.15em",
              textShadow: `
                0 0 30px rgba(102, 126, 234, 0.9),
                0 0 60px rgba(102, 126, 234, 0.5),
                0 4px 20px rgba(0, 0, 0, 0.8)
              `,
            }}
          >
            AI-IR Insight
          </h1>

          {/* 装飾ライン */}
          <div
            style={{
              width: lineWidth,
              height: 3,
              background: `linear-gradient(90deg,
                transparent,
                rgba(102, 126, 234, 0.9) 20%,
                rgba(167, 139, 250, 1) 50%,
                rgba(118, 75, 162, 0.9) 80%,
                transparent
              )`,
              margin: "25px auto 0",
              borderRadius: 2,
              boxShadow: "0 0 20px rgba(102, 126, 234, 0.5)",
            }}
          />
        </div>

        {/* サブタイトル */}
        <div
          style={{
            opacity: subtitleOpacity,
            transform: `translateX(${subtitleSlideX}px)`,
            marginTop: 15,
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 32,
              color: "rgba(255, 255, 255, 0.9)",
              fontWeight: 400,
              letterSpacing: "0.35em",
              textShadow: "0 2px 15px rgba(0, 0, 0, 0.5)",
            }}
          >
            AIが読み解く、市場の本質
          </p>
        </div>
      </div>

      {/* キャラクター */}
      <div
        style={{
          position: "absolute",
          right: 60,
          bottom: 0,
          width: 450,
          height: 650,
          opacity: characterOpacity,
          transform: `scale(${Math.min(characterScale, 1)}) translateY(${characterFloat}px)`,
          transformOrigin: "bottom center",
        }}
      >
        {/* 後光 */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            bottom: "20%",
            width: 400,
            height: 400,
            transform: "translateX(-50%)",
            background: `radial-gradient(circle, rgba(167, 139, 250, 0.3) 0%, rgba(102, 126, 234, 0.1) 40%, transparent 70%)`,
            filter: "blur(30px)",
          }}
        />

        <Img
          src={staticFile(characterImage)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            objectPosition: "bottom",
            filter: `
              drop-shadow(0 0 30px rgba(167, 139, 250, 0.4))
              drop-shadow(0 15px 50px rgba(0, 0, 0, 0.5))
            `,
          }}
        />
      </div>

      {/* 日付とタイトル */}
      <div
        style={{
          position: "absolute",
          bottom: 100,
          left: 80,
          opacity: infoOpacity,
          transform: `translateY(${infoSlideY}px)`,
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: 22,
            color: "rgba(167, 139, 250, 0.9)",
            fontWeight: 500,
            letterSpacing: "0.1em",
            marginBottom: 10,
          }}
        >
          {displayDate}
        </p>
        <p
          style={{
            margin: 0,
            fontSize: 28,
            color: "rgba(255, 255, 255, 0.95)",
            fontWeight: 600,
            letterSpacing: "0.05em",
            textShadow: "0 2px 10px rgba(0, 0, 0, 0.4)",
          }}
        >
          {title}
        </p>
      </div>

      {/* コーナー装飾 */}
      {[
        { top: 50, left: 50, borderTop: true, borderLeft: true },
        { top: 50, right: 50, borderTop: true, borderRight: true },
        { bottom: 50, left: 50, borderBottom: true, borderLeft: true },
        { bottom: 50, right: 50, borderBottom: true, borderRight: true },
      ].map((corner, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            ...(corner.top !== undefined && { top: corner.top }),
            ...(corner.bottom !== undefined && { bottom: corner.bottom }),
            ...(corner.left !== undefined && { left: corner.left }),
            ...(corner.right !== undefined && { right: corner.right }),
            width: 80,
            height: 80,
            borderTop: corner.borderTop ? "3px solid rgba(102, 126, 234, 0.7)" : "none",
            borderBottom: corner.borderBottom ? "3px solid rgba(102, 126, 234, 0.7)" : "none",
            borderLeft: corner.borderLeft ? "3px solid rgba(102, 126, 234, 0.7)" : "none",
            borderRight: corner.borderRight ? "3px solid rgba(102, 126, 234, 0.7)" : "none",
            opacity: cornerOpacity,
          }}
        />
      ))}

      {/* スキャンライン */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 0, 0, 0.03) 2px,
            rgba(0, 0, 0, 0.03) 4px
          )`,
          pointerEvents: "none",
        }}
      />
    </div>
  );
};
