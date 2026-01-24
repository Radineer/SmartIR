export interface ScriptSegment {
  text: string;
  startFrame: number;
  durationFrames: number;
  expression?: string;
  marketType?: "nikkei" | "topix" | "dowjones" | "usdjpy";
}

export interface VideoProps {
  title: string;
  companyName: string;
  script: ScriptSegment[];
  audioUrl?: string;
  bgmUrl?: string;
  characterImage?: string;
  /** VRMモデルを使用するかどうか */
  useVRM?: boolean;
  /** VRMモデルのURL */
  vrmModelUrl?: string;
}

/** VRM表情タイプ */
export type VRMExpressionType =
  | "neutral"
  | "happy"
  | "angry"
  | "sad"
  | "surprised"
  | "thinking";

/** リップシンク用の母音タイプ */
export type VowelType = "a" | "i" | "u" | "e" | "o" | "n";
