import React from "react";
import { useCurrentFrame } from "remotion";
import type { ScriptSegment } from "../types";

interface SubtitlesProps {
  script: ScriptSegment[];
}

export const Subtitles: React.FC<SubtitlesProps> = ({ script }) => {
  const frame = useCurrentFrame();

  const currentSegment = script.find(
    (s) => frame >= s.startFrame && frame < s.startFrame + s.durationFrames
  );

  if (!currentSegment) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        left: 60,
        right: 500,
        padding: 20,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        borderRadius: 12,
        color: "white",
        fontSize: 32,
        lineHeight: 1.5,
      }}
    >
      {currentSegment.text}
    </div>
  );
};
