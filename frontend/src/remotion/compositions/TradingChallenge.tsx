import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
  Sequence,
  Audio,
  OffthreadVideo,
  staticFile,
} from "remotion";
import { z } from "zod";

// --- Schema ---
const positionSchema = z.object({
  name: z.string(),
  ticker: z.string(),
  pnl: z.number(),
  pnlPct: z.number(),
});

export const tradingChallengePropsSchema = z.object({
  day: z.number(),
  date: z.string(),
  nav: z.number(),
  dailyReturn: z.number(),
  cumulativeReturn: z.number(),
  maxDrawdown: z.number(),
  positions: z.array(positionSchema),
  characterVideoUrl: z.string(),
  audioUrl: z.string().optional(),
  script: z.array(z.object({
    text: z.string(),
    startFrame: z.number(),
    durationFrames: z.number(),
  })),
});

type Props = z.infer<typeof tradingChallengePropsSchema>;

// --- Colors (TikTok finance aesthetic) ---
const C = {
  bg: "#0D0D1A",
  green: "#00FF88",
  red: "#FF3B3B",
  cyan: "#00D4FF",
  purple: "#8B5CF6",
  white: "#FFFFFF",
  gray: "#8899AA",
  darkCard: "rgba(255,255,255,0.06)",
};

// --- TikTok Safe Zones (1080x1920) ---
// Top: 130px, Bottom: 520px, Right: 140px are danger zones
const SAFE = { top: 140, bottom: 1400, left: 60, right: 940 };

// =============================================================
// PHASE 1: HOOK (0-2s) — Giant text + number to stop scrolling
// =============================================================
const HookPhase: React.FC<{ day: number; dailyReturn: number; nav: number }> = ({
  day, dailyReturn, nav,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Frame 0 から即表示、1フレーム目で完了
  const titleIn = Math.min(1, spring({ frame, fps, config: { damping: 8, stiffness: 300 } }) + (frame >= 1 ? 0.3 : 0));
  const numberIn = Math.min(1, spring({ frame: Math.max(0, frame - 1), fps, config: { damping: 8, stiffness: 200 } }) + (frame >= 2 ? 0.2 : 0));

  // Screen shake on number appear
  const shakeX = frame > 8 && frame < 18 ? Math.sin(frame * 3) * 3 : 0;
  const shakeY = frame > 8 && frame < 18 ? Math.cos(frame * 4) * 2 : 0;

  const isPositive = dailyReturn >= 0;
  const color = isPositive ? C.green : C.red;

  return (
    <div style={{
      position: "absolute",
      top: SAFE.top,
      left: SAFE.left,
      right: 1080 - SAFE.right,
      zIndex: 30,
      transform: `translate(${shakeX}px, ${shakeY}px)`,
    }}>
      {/* Series tag */}
      <div style={{
        opacity: titleIn,
        transform: `translateY(${interpolate(titleIn, [0, 1], [30, 0])}px)`,
        fontSize: 28,
        fontWeight: 700,
        color: C.cyan,
        letterSpacing: 3,
        marginBottom: 12,
        textShadow: `0 0 20px ${C.cyan}60`,
      }}>
        DAY {day} ▸ AIトレーディング
      </div>

      {/* Main hook: P&L percentage */}
      <div style={{
        opacity: numberIn,
        transform: `scale(${interpolate(numberIn, [0, 1], [0.5, 1])})`,
        fontSize: 96,
        fontWeight: 900,
        color,
        lineHeight: 1,
        textShadow: `0 0 40px ${color}80, 0 0 80px ${color}40`,
        WebkitTextStroke: `1px ${color}`,
      }}>
        {isPositive ? "+" : ""}{dailyReturn.toFixed(2)}%
      </div>

      {/* NAV counter */}
      <div style={{
        opacity: numberIn,
        fontSize: 44,
        fontWeight: 700,
        color: C.white,
        marginTop: 8,
        textShadow: "0 2px 10px rgba(0,0,0,0.5)",
      }}>
        ¥{nav.toLocaleString()}
      </div>

      {/* Tagline */}
      <div style={{
        opacity: interpolate(frame - 15, [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        fontSize: 22,
        color: C.gray,
        marginTop: 10,
      }}>
        10万円 → AI完全自動運用
      </div>
    </div>
  );
};

// =============================================================
// PHASE 2: PORTFOLIO (appears after hook)
// =============================================================
const PortfolioPhase: React.FC<{
  positions: z.infer<typeof positionSchema>[];
  startFrame: number;
}> = ({ positions, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div style={{
      position: "absolute",
      top: 520,
      left: SAFE.left,
      right: 1080 - SAFE.right,
      zIndex: 20,
    }}>
      <div style={{
        fontSize: 18,
        color: C.cyan,
        fontWeight: 700,
        marginBottom: 10,
        letterSpacing: 2,
        opacity: spring({ frame: frame - startFrame, fps, config: { damping: 20, stiffness: 80 } }),
      }}>
        ── PORTFOLIO ──
      </div>
      {positions.map((pos, i) => {
        const rowIn = spring({
          frame: frame - startFrame - i * 3,
          fps,
          config: { damping: 14, stiffness: 80 },
        });
        const isPos = pos.pnl >= 0;
        const color = isPos ? C.green : C.red;

        // Highlight sweep
        const SWEEP_START = startFrame + 50;
        const SWEEP_CYCLE = 80;
        const phase = (frame - SWEEP_START) % SWEEP_CYCLE;
        const isHit = frame > SWEEP_START && phase >= i * 10 && phase < i * 10 + 12;

        return (
          <div key={pos.ticker} style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "10px 14px",
            marginBottom: 5,
            background: isHit ? "rgba(0,212,255,0.08)" : C.darkCard,
            borderRadius: 10,
            borderLeft: `3px solid ${color}`,
            opacity: rowIn,
            transform: `translateX(${interpolate(rowIn, [0, 1], [-40, 0])}px)`,
            boxShadow: isHit ? `0 0 12px ${C.cyan}30` : "none",
          }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.white }}>{pos.name}</div>
            <div style={{
              fontSize: 20,
              fontWeight: 800,
              color,
              textShadow: `0 0 8px ${color}50`,
            }}>
              {isPos ? "+" : ""}¥{pos.pnl.toLocaleString()}
            </div>
          </div>
        );
      })}
      {/* Strategy tag */}
      <div style={{
        marginTop: 8,
        fontSize: 12,
        color: C.purple,
        opacity: spring({
          frame: frame - startFrame - positions.length * 3 - 10,
          fps,
          config: { damping: 20, stiffness: 80 },
        }),
      }}>
        🤖 ML予測 × Lead-Lag PCA × テクニカル60+
      </div>
    </div>
  );
};

// =============================================================
// PHASE 3: RESULT FLASH (dramatic moment)
// =============================================================
const ResultFlash: React.FC<{
  profit: number;
  startFrame: number;
}> = ({ profit, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const flashIn = spring({ frame: frame - startFrame, fps, config: { damping: 10, stiffness: 120 } });
  const isPos = profit >= 0;
  const color = isPos ? C.green : C.red;

  // Screen shake
  const shakeX = frame >= startFrame && frame < startFrame + 10 ? Math.sin(frame * 5) * 4 : 0;
  const shakeY = frame >= startFrame && frame < startFrame + 10 ? Math.cos(frame * 6) * 3 : 0;

  if (frame < startFrame) return null;

  const fadeOut = frame > startFrame + 60
    ? interpolate(frame - startFrame - 60, [0, 20], [1, 0], { extrapolateRight: "clamp" })
    : 1;

  return (
    <>
      {/* Dark overlay behind flash */}
      <div style={{
        position: "absolute",
        inset: 0,
        zIndex: 34,
        background: `rgba(0,0,0,${0.5 * flashIn * fadeOut})`,
        pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute",
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 35,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `translate(${shakeX}px, ${shakeY}px)`,
        opacity: fadeOut,
      }}>
        <div style={{
          background: `${color}12`,
          border: `2px solid ${color}50`,
          borderRadius: 24,
          padding: "24px 60px",
          opacity: flashIn,
          transform: `scale(${interpolate(flashIn, [0, 1], [0.2, 1])})`,
          textAlign: "center",
          boxShadow: `0 0 60px ${color}30`,
        }}>
          <div style={{ fontSize: 22, color: C.gray, marginBottom: 6, letterSpacing: 2 }}>
            2日間の損益
          </div>
          <div style={{
            fontSize: 72,
            fontWeight: 900,
            color,
            textShadow: `0 0 40px ${color}90, 0 0 80px ${color}40`,
            lineHeight: 1,
          }}>
            {isPos ? "+" : ""}¥{profit.toLocaleString()}
          </div>
          <div style={{
            fontSize: 18,
            color: C.cyan,
            marginTop: 10,
            opacity: 0.8,
          }}>
            10万円 → ¥{(100000 + profit).toLocaleString()}
          </div>
        </div>
      </div>
    </>
  );
};

// =============================================================
// Subtitle — TikTok style (black outline, center-bottom safe zone)
// =============================================================
const Subtitle: React.FC<{ text: string; isActive: boolean }> = ({ text, isActive }) => {
  const frame = useCurrentFrame();
  if (!text || !isActive) return null;
  const opacity = Math.min(1, (frame % 200) / 3);

  return (
    <div style={{
      position: "absolute",
      bottom: 540,  // Above TikTok bottom UI
      left: 60,
      right: 160,  // Avoid right-side engagement buttons
      zIndex: 50,
      opacity,
    }}>
      <p style={{
        margin: 0,
        color: C.white,
        fontSize: 38,
        fontWeight: 800,
        lineHeight: 1.4,
        textAlign: "left",
        textShadow: `
          -2px -2px 0 #000, 2px -2px 0 #000,
          -2px 2px 0 #000, 2px 2px 0 #000,
          0 0 10px rgba(0,0,0,0.8)
        `,
        letterSpacing: "0.02em",
      }}>{text}</p>
    </div>
  );
};

// =============================================================
// Particles (more visible)
// =============================================================
const Particles: React.FC = () => {
  const frame = useCurrentFrame();
  const dots = [
    { x: 5, y: 15, sp: 0.3, sz: 4, c: C.cyan },
    { x: 20, y: 55, sp: 0.5, sz: 3, c: C.green },
    { x: 40, y: 25, sp: 0.4, sz: 5, c: C.purple },
    { x: 75, y: 65, sp: 0.6, sz: 3, c: C.cyan },
    { x: 55, y: 80, sp: 0.35, sz: 4, c: C.green },
    { x: 85, y: 40, sp: 0.45, sz: 3, c: C.purple },
  ];
  return <>
    {dots.map((d, i) => {
      const y = (d.y + frame * d.sp * 0.4) % 105;
      const op = interpolate(Math.sin(frame * 0.05 + i * 1.5), [-1, 1], [0.15, 0.45]);
      return <div key={i} style={{
        position: "absolute", left: `${d.x}%`, top: `${y}%`,
        width: d.sz, height: d.sz, borderRadius: "50%",
        backgroundColor: d.c, opacity: op,
        boxShadow: `0 0 ${d.sz * 5}px ${d.c}80`,
        pointerEvents: "none",
      }} />;
    })}
  </>;
};

// =============================================================
// Main Composition — TikTok viral format
// =============================================================
export const TradingChallengeVideo: React.FC<Props> = (props) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const {
    day, date, nav, dailyReturn, cumulativeReturn,
    maxDrawdown, positions, characterVideoUrl, audioUrl, script,
  } = props;

  const profit = nav - 100000;

  const currentSegment = script.find((seg) =>
    frame >= seg.startFrame && frame < seg.startFrame + seg.durationFrames
  );

  // === Phase timing ===
  // Phase 1: Hook (0-3s) — big number dominates
  // Phase 2: Portfolio (3-8s) — data slides in
  // Phase 3: Result flash (14s) — dramatic P&L reveal
  // Phase 4: CTA (last 3s) — ending
  const PORTFOLIO_START = Math.round(3 * fps);
  const RESULT_START = Math.round(14 * fps);
  const ENDING_START = durationInFrames - Math.round(2.5 * fps);

  // Background pulse
  const bgPulse = interpolate(Math.sin(frame / fps * 0.5), [-1, 1], [0.92, 1]);

  // Ending fade
  const endFade = frame > ENDING_START
    ? interpolate(frame, [ENDING_START, durationInFrames], [1, 0], { extrapolateRight: "clamp" })
    : 1;

  return (
    <AbsoluteFill style={{
      background: `radial-gradient(ellipse at 50% 30%,
        hsl(240, 50%, ${6 * bgPulse}%) 0%,
        ${C.bg} 70%)`,
      fontFamily: "'Noto Sans JP', 'Inter', sans-serif",
      color: C.white,
      opacity: endFade,
    }}>
      {/* Subtle grid */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `
          linear-gradient(${C.cyan}08 1px, transparent 1px),
          linear-gradient(90deg, ${C.cyan}08 1px, transparent 1px)`,
        backgroundSize: "80px 80px",
      }} />

      <Particles />

      {/* Audio */}
      <Audio src={staticFile("audio/bgm/business-calm.mp3")} volume={0.08} />
      {audioUrl && <Audio src={staticFile(audioUrl)} volume={1.0} />}
      <Sequence from={0}>
        <Audio src={staticFile("audio/se/op-appear.mp3")} volume={0.3} />
      </Sequence>
      <Sequence from={PORTFOLIO_START}>
        <Audio src={staticFile("audio/se/graph-display.mp3")} volume={0.25} />
      </Sequence>

      {/* ===== OmniHuman Character — bottom center ===== */}
      <div style={{
        position: "absolute",
        bottom: 560,
        left: "50%",
        transform: "translateX(-50%)",
        width: 500,
        height: 600,
        zIndex: 5,
        maskImage: `radial-gradient(ellipse 90% 85% at 50% 40%, black 45%, transparent 100%)`,
        WebkitMaskImage: `radial-gradient(ellipse 90% 85% at 50% 40%, black 45%, transparent 100%)`,
      }}>
        <OffthreadVideo
          src={staticFile(characterVideoUrl)}
          style={{
            width: "100%", height: "100%",
            objectFit: "cover", objectPosition: "center 15%",
          }}
          muted
        />
      </div>

      {/* ===== PHASE 1: HOOK ===== */}
      <HookPhase day={day} dailyReturn={dailyReturn} nav={nav} />

      {/* Date badge — top right (safe zone) */}
      <div style={{
        position: "absolute",
        top: SAFE.top,
        right: 1080 - SAFE.right,
        zIndex: 20,
        fontSize: 14,
        color: C.gray,
        textAlign: "right",
      }}>
        <div style={{ color: C.purple, fontWeight: 700, fontSize: 16 }}>SmartIR × Iris</div>
        <div>{date}</div>
      </div>

      {/* ===== PHASE 2: PORTFOLIO ===== */}
      <Sequence from={PORTFOLIO_START}>
        <PortfolioPhase positions={positions} startFrame={PORTFOLIO_START} />
      </Sequence>

      {/* ===== PHASE 3: RESULT FLASH ===== */}
      <Sequence from={RESULT_START}>
        <ResultFlash profit={profit} startFrame={0} />
      </Sequence>

      {/* ===== Ending vignette ===== */}
      {frame > ENDING_START && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 40, pointerEvents: "none",
          background: `radial-gradient(circle at 50% 50%,
            transparent 0%,
            rgba(0,0,0,${interpolate(frame, [ENDING_START, durationInFrames], [0, 0.9])}) 100%)`,
        }} />
      )}

      {/* ===== Subtitle ===== */}
      <Subtitle text={currentSegment?.text || ""} isActive={!!currentSegment} />
    </AbsoluteFill>
  );
};
