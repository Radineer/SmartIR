import React from "react";
import { useCurrentFrame, interpolate } from "remotion";

interface BackgroundProps {
  primaryColor?: string;
  secondaryColor?: string;
}

export const Background: React.FC<BackgroundProps> = ({
  primaryColor = "#667eea",
  secondaryColor = "#764ba2",
}) => {
  const frame = useCurrentFrame();

  // 背景のアニメーション効果
  const gradientAngle = interpolate(frame, [0, 300], [135, 180], {
    extrapolateRight: "clamp",
  });

  return (
    <>
      {/* ベース背景 */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: "#1a1a2e",
        }}
      />

      {/* グラデーションオーバーレイ */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(${gradientAngle}deg, ${primaryColor} 0%, ${secondaryColor} 100%)`,
          opacity: 0.3,
        }}
      />

      {/* パーティクル効果（オプション） */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: "50px 50px",
          opacity: 0.5,
        }}
      />
    </>
  );
};
