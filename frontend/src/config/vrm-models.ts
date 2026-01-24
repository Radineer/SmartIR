export interface VRMModelConfig {
  id: string;
  name: string;
  path: string;
  description: string;
  credit?: string;
  expressions: string[];
}

export const VRM_MODELS: VRMModelConfig[] = [
  {
    id: "iris-default",
    name: "イリス（デフォルト）",
    path: "/models/vrm/iris.vrm",
    description: "2050年から来たAIアナリスト",
    expressions: ["neutral", "happy", "sad", "angry", "surprised"],
  },
  {
    id: "sample-a",
    name: "サンプルアバター",
    path: "/models/vrm/AvatarSample_A.vrm",
    description: "VRoid公式サンプル",
    credit: "VRoid Project",
    expressions: ["neutral", "happy"],
  },
];

export const DEFAULT_MODEL_ID = "sample-a";
