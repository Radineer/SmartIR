import React, { useMemo } from "react";
import {
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
  Img,
  staticFile,
  Sequence,
  Easing,
} from "remotion";

interface EndingSceneProps {
  /** ED表示時間（フレーム数）- 8秒 = 240フレーム */
  durationFrames?: number;
  /** キャラクター画像パス（お辞儀） */
  characterImage?: string;
  /** 次回予告テキスト */
  nextEpisodeText?: string;
  /** Twitter/Xアカウント */
  twitterHandle?: string;
}

// アニメーションボタンコンポーネント
const AnimatedButton: React.FC<{
  icon: React.ReactNode;
  label: string;
  color: string;
  glowColor: string;
  frame: number;
  startFrame: number;
  delay?: number;
}> = ({ icon, label, color, glowColor, frame, startFrame, delay = 0 }) => {
  const localFrame = frame - startFrame - delay;

  // ボタンのスケールアニメーション
  const buttonScale = localFrame >= 0
    ? spring({
        frame: localFrame,
        fps: 30,
        config: {
          damping: 10,
          stiffness: 150,
          mass: 0.5,
        },
      })
    : 0;

  // パルスエフェクト
  const pulse = localFrame > 15
    ? interpolate(Math.sin(localFrame * 0.12), [-1, 1], [1, 1.05])
    : 1;

  // グローのパルス
  const glowPulse = localFrame > 15
    ? interpolate(Math.sin(localFrame * 0.1), [-1, 1], [0.5, 1])
    : 0.5;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        transform: `scale(${buttonScale * pulse})`,
        opacity: buttonScale,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
          padding: "16px 32px",
          background: color,
          borderRadius: 50,
          boxShadow: `
            0 4px 20px ${glowColor},
            0 0 ${40 * glowPulse}px ${glowColor},
            inset 0 1px 0 rgba(255, 255, 255, 0.2)
          `,
          border: "2px solid rgba(255, 255, 255, 0.15)",
          cursor: "pointer",
          transition: "transform 0.2s",
        }}
      >
        <span style={{ fontSize: 32 }}>{icon}</span>
        <span
          style={{
            color: "white",
            fontSize: 20,
            fontWeight: "bold",
            letterSpacing: "0.05em",
          }}
        >
          {label}
        </span>
      </div>
    </div>
  );
};

// ベルアイコンコンポーネント（通知ON）
const BellIcon: React.FC<{ frame: number; isActive: boolean }> = ({
  frame,
  isActive,
}) => {
  // ベルの揺れアニメーション
  const bellRotation = isActive
    ? interpolate(Math.sin(frame * 0.4), [-1, 1], [-15, 15])
    : 0;

  return (
    <div
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `rotate(${bellRotation}deg)`,
        transformOrigin: "top center",
      }}
    >
      {/* ベル本体 */}
      <svg
        width="36"
        height="36"
        viewBox="0 0 24 24"
        fill="none"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>

      {/* 通知ドット */}
      {isActive && (
        <div
          style={{
            position: "absolute",
            top: -2,
            right: -2,
            width: 12,
            height: 12,
            background: "#ff4444",
            borderRadius: "50%",
            border: "2px solid white",
          }}
        />
      )}
    </div>
  );
};

// SNSアイコン（X/Twitter）
const TwitterXIcon: React.FC<{ size?: number }> = ({ size = 32 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="white"
  >
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

// キラキラパーティクル
const SparkleParticles: React.FC<{ frame: number; count?: number }> = ({
  frame,
  count = 20,
}) => {
  const particles = useMemo(() => {
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      x: (i * 37) % 100,
      y: (i * 53) % 100,
      size: 3 + (i % 4) * 2,
      speed: 0.3 + (i % 5) * 0.15,
      delay: (i * 7) % 40,
    }));
  }, [count]);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
      }}
    >
      {particles.map((particle) => {
        const particleOpacity = interpolate(
          Math.sin((frame - particle.delay) * 0.08 + particle.id),
          [-1, 1],
          [0, 0.8]
        );

        const yOffset = Math.sin((frame - particle.delay) * 0.04 + particle.id * 0.5) * 30;

        return (
          <div
            key={particle.id}
            style={{
              position: "absolute",
              left: `${particle.x}%`,
              top: `${particle.y}%`,
              width: particle.size,
              height: particle.size,
              background: `radial-gradient(circle, rgba(255, 255, 255, 0.9) 0%, rgba(167, 139, 250, 0.5) 50%, transparent 100%)`,
              borderRadius: "50%",
              boxShadow: `0 0 ${particle.size * 3}px rgba(167, 139, 250, 0.6)`,
              opacity: Math.max(0, particleOpacity),
              transform: `translateY(${yOffset}px)`,
            }}
          />
        );
      })}
    </div>
  );
};

// ED: 8秒 = 240フレーム
export const EndingScene: React.FC<EndingSceneProps> = ({
  durationFrames = 240,
  characterImage = "/images/iris/iris-bow.png",
  nextEpisodeText = "次回もお楽しみに！",
  twitterHandle = "@AI_IR_Insight",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // === Phase 1: ありがとう + お辞儀 (0-60f) ===
  const thankYouOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const thankYouScale = spring({
    frame,
    fps,
    config: {
      damping: 12,
      stiffness: 100,
      mass: 0.8,
    },
  });

  // お辞儀アニメーション
  const bowRotation = interpolate(frame, [10, 35, 50], [0, 15, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  const characterOpacity = interpolate(frame, [5, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // === Phase 2: 次回予告 (60-120f) ===
  const nextEpisodeSlideY = interpolate(frame, [60, 90], [50, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  const nextEpisodeOpacity = interpolate(frame, [60, 85], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // === Phase 3: CTAボタン (120-180f) ===
  // ボタンは AnimatedButton 内で個別に処理

  // === Phase 4: SNSリンク (180-210f) ===
  const snsSlideX = interpolate(frame, [180, 205], [80, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  const snsOpacity = interpolate(frame, [180, 200], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // === Phase 5: ロゴ + フェードアウト (210-240f) ===
  const logoOpacity = interpolate(frame, [210, 225], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const finalFadeOut = interpolate(frame, [225, 240], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // グローパルス
  const glowPulse = interpolate(Math.sin(frame * 0.08), [-1, 1], [0.6, 1]);

  // 背景グラデーションアニメーション
  const bgShift = frame * 0.3;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "#000",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: finalFadeOut,
        }}
      >
        {/* 背景グラデーション */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `
              radial-gradient(ellipse at ${50 + Math.sin(bgShift * 0.01) * 10}% 40%, rgba(118, 75, 162, 0.5) 0%, transparent 55%),
              radial-gradient(ellipse at 30% 70%, rgba(102, 126, 234, 0.4) 0%, transparent 50%),
              radial-gradient(ellipse at 70% 25%, rgba(236, 72, 153, 0.3) 0%, transparent 45%),
              radial-gradient(ellipse at 85% 75%, rgba(167, 139, 250, 0.25) 0%, transparent 40%),
              linear-gradient(180deg, #14141f 0%, #0a0a12 50%, #050508 100%)
            `,
          }}
        />

        {/* キラキラパーティクル */}
        <SparkleParticles frame={frame} count={30} />

        {/* グリッドオーバーレイ */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `
              linear-gradient(rgba(118, 75, 162, 0.03) 1px, transparent 1px),
              linear-gradient(90deg, rgba(118, 75, 162, 0.03) 1px, transparent 1px)
            `,
            backgroundSize: "50px 50px",
            opacity: 0.4,
          }}
        />

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
          {/* Phase 1: ありがとうテキスト + イリス */}
          <Sequence from={0} durationInFrames={240}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                marginBottom: 40,
              }}
            >
              {/* ありがとうテキスト */}
              <div
                style={{
                  opacity: thankYouOpacity,
                  transform: `scale(${Math.min(thankYouScale, 1)})`,
                }}
              >
                <h1
                  style={{
                    margin: 0,
                    fontSize: 60,
                    fontWeight: "bold",
                    color: "white",
                    textShadow: `
                      0 0 ${30 * glowPulse}px rgba(118, 75, 162, 0.9),
                      0 0 ${60 * glowPulse}px rgba(118, 75, 162, 0.5),
                      0 0 ${90 * glowPulse}px rgba(167, 139, 250, 0.3),
                      0 4px 20px rgba(0, 0, 0, 0.8)
                    `,
                    letterSpacing: "0.12em",
                  }}
                >
                  ご視聴ありがとうございました
                </h1>

                {/* 装飾ライン */}
                <div
                  style={{
                    width: 400,
                    height: 3,
                    background: `linear-gradient(90deg,
                      transparent,
                      rgba(118, 75, 162, 0.9) 20%,
                      rgba(236, 72, 153, 0.8) 50%,
                      rgba(167, 139, 250, 0.9) 80%,
                      transparent
                    )`,
                    margin: "25px auto 0",
                    borderRadius: 2,
                    boxShadow: "0 0 15px rgba(118, 75, 162, 0.5)",
                  }}
                />
              </div>
            </div>
          </Sequence>

          {/* Phase 2: 次回予告 */}
          <Sequence from={60} durationInFrames={180}>
            <div
              style={{
                transform: `translateY(${nextEpisodeSlideY}px)`,
                opacity: nextEpisodeOpacity,
                marginBottom: 50,
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontSize: 32,
                  color: "rgba(255, 255, 255, 0.9)",
                  fontWeight: 500,
                  letterSpacing: "0.15em",
                  textShadow: "0 2px 10px rgba(0, 0, 0, 0.5)",
                }}
              >
                {nextEpisodeText}
              </p>
            </div>
          </Sequence>

          {/* Phase 3: CTAボタン */}
          <Sequence from={120} durationInFrames={120}>
            <div
              style={{
                display: "flex",
                gap: 40,
                alignItems: "flex-start",
              }}
            >
              {/* チャンネル登録ボタン */}
              <AnimatedButton
                icon={
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
                    <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
                  </svg>
                }
                label="チャンネル登録"
                color="linear-gradient(135deg, #ff0000 0%, #cc0000 100%)"
                glowColor="rgba(255, 0, 0, 0.4)"
                frame={frame}
                startFrame={120}
                delay={0}
              />

              {/* 高評価ボタン */}
              <AnimatedButton
                icon={
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
                    <path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/>
                  </svg>
                }
                label="高評価"
                color="linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
                glowColor="rgba(102, 126, 234, 0.4)"
                frame={frame}
                startFrame={120}
                delay={10}
              />

              {/* 通知ONボタン */}
              <AnimatedButton
                icon={<BellIcon frame={frame} isActive={frame > 145} />}
                label="通知ON"
                color="linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
                glowColor="rgba(245, 158, 11, 0.4)"
                frame={frame}
                startFrame={120}
                delay={20}
              />
            </div>
          </Sequence>

          {/* Phase 4: SNSリンク */}
          <Sequence from={180} durationInFrames={60}>
            <div
              style={{
                transform: `translateX(${snsSlideX}px)`,
                opacity: snsOpacity,
                marginTop: 50,
                display: "flex",
                alignItems: "center",
                gap: 16,
                padding: "14px 28px",
                background: "rgba(255, 255, 255, 0.08)",
                borderRadius: 40,
                border: "1px solid rgba(255, 255, 255, 0.15)",
                backdropFilter: "blur(10px)",
              }}
            >
              <TwitterXIcon size={28} />
              <span
                style={{
                  color: "white",
                  fontSize: 20,
                  fontWeight: 500,
                  letterSpacing: "0.05em",
                }}
              >
                {twitterHandle}
              </span>
            </div>
          </Sequence>
        </div>

        {/* イリス（お辞儀） */}
        <Sequence from={0} durationInFrames={240}>
          <div
            style={{
              position: "absolute",
              right: 80,
              bottom: 0,
              width: 380,
              height: 550,
              opacity: characterOpacity * finalFadeOut,
              transform: `rotate(${bowRotation}deg)`,
              transformOrigin: "bottom center",
            }}
          >
            {/* キャラクター後光 */}
            <div
              style={{
                position: "absolute",
                left: "50%",
                bottom: "15%",
                width: 350,
                height: 350,
                transform: "translateX(-50%)",
                background: `radial-gradient(circle, rgba(236, 72, 153, 0.25) 0%, rgba(118, 75, 162, 0.1) 40%, transparent 70%)`,
                filter: "blur(25px)",
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
                  drop-shadow(0 0 25px rgba(236, 72, 153, 0.35))
                  drop-shadow(0 15px 45px rgba(0, 0, 0, 0.5))
                `,
              }}
            />
          </div>
        </Sequence>

        {/* Phase 5: ロゴ */}
        <Sequence from={210} durationInFrames={30}>
          <div
            style={{
              position: "absolute",
              bottom: 50,
              left: 70,
              opacity: logoOpacity,
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: 28,
                color: "rgba(255, 255, 255, 0.75)",
                fontWeight: 600,
                letterSpacing: "0.12em",
                textShadow: `
                  0 0 20px rgba(102, 126, 234, 0.5),
                  0 2px 10px rgba(0, 0, 0, 0.4)
                `,
              }}
            >
              AI-IR Insight
            </p>
          </div>
        </Sequence>

        {/* コーナー装飾 */}
        <div
          style={{
            position: "absolute",
            top: 50,
            left: 50,
            width: 70,
            height: 70,
            borderTop: "3px solid rgba(118, 75, 162, 0.6)",
            borderLeft: "3px solid rgba(118, 75, 162, 0.6)",
            opacity: thankYouOpacity,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 50,
            right: 50,
            width: 70,
            height: 70,
            borderTop: "3px solid rgba(118, 75, 162, 0.6)",
            borderRight: "3px solid rgba(118, 75, 162, 0.6)",
            opacity: thankYouOpacity,
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 50,
            left: 50,
            width: 70,
            height: 70,
            borderBottom: "3px solid rgba(118, 75, 162, 0.6)",
            borderLeft: "3px solid rgba(118, 75, 162, 0.6)",
            opacity: thankYouOpacity,
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 50,
            right: 50,
            width: 70,
            height: 70,
            borderBottom: "3px solid rgba(118, 75, 162, 0.6)",
            borderRight: "3px solid rgba(118, 75, 162, 0.6)",
            opacity: thankYouOpacity,
          }}
        />

        {/* ビネット効果 */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse at center, transparent 50%, rgba(0, 0, 0, 0.4) 100%)`,
            pointerEvents: "none",
          }}
        />

        {/* スキャンライン */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `repeating-linear-gradient(
              0deg,
              transparent,
              transparent 2px,
              rgba(0, 0, 0, 0.02) 2px,
              rgba(0, 0, 0, 0.02) 4px
            )`,
            pointerEvents: "none",
          }}
        />
      </div>
    </div>
  );
};
