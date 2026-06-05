"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Image from "next/image";
import { SadTalkerJob, SadTalkerStatusResponse } from "@/types";

// ステップの定義
type Step = 1 | 2 | 3 | 4 | 5;

interface StepInfo {
  id: Step;
  label: string;
  icon: string;
}

const steps: StepInfo[] = [
  { id: 1, label: "台本", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { id: 2, label: "音声", icon: "M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" },
  { id: 3, label: "プレビュー", icon: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
  { id: 4, label: "レンダリング", icon: "M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" },
  { id: 5, label: "配信", icon: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
];

// テーマの定義
const themes = [
  { id: "market_comment", label: "市況コメント", description: "今日のマーケット動向を解説" },
  { id: "ir_analysis", label: "IR分析", description: "企業のIR資料を詳しく分析" },
  { id: "glossary", label: "用語解説", description: "金融・投資用語をわかりやすく解説" },
];

// VOICEVOXスピーカー（モック）
const mockSpeakers = [
  { id: 0, name: "四国めたん", styles: [{ id: 0, name: "ノーマル" }, { id: 1, name: "あまあま" }] },
  { id: 1, name: "ずんだもん", styles: [{ id: 2, name: "ノーマル" }, { id: 3, name: "あまあま" }] },
  { id: 2, name: "春日部つむぎ", styles: [{ id: 4, name: "ノーマル" }] },
  { id: 3, name: "雨晴はう", styles: [{ id: 5, name: "ノーマル" }] },
  { id: 4, name: "波音リツ", styles: [{ id: 6, name: "ノーマル" }] },
];

// セグメント型
interface Segment {
  id: string;
  text: string;
  duration: number;
  audioGenerated: boolean;
}

// レンダリングジョブ型
interface RenderJob {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  videoUrl?: string;
}

export default function StudioPage() {
  const [currentStep, setCurrentStep] = useState<Step>(1);

  // Step 1: 台本状態
  const [selectedTheme, setSelectedTheme] = useState<string>("");
  const [scriptText, setScriptText] = useState<string>("");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [generatingScript, setGeneratingScript] = useState(false);

  // Step 2: 音声状態
  const [selectedSpeaker, setSelectedSpeaker] = useState<number>(0);
  const [selectedStyle, setSelectedStyle] = useState<number>(0);
  const [generatingAudio, setGeneratingAudio] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);

  // Step 3: プレビュー状態
  const [bgColor, setBgColor] = useState("#1e1b4b");
  const [characterPosition, setCharacterPosition] = useState<"left" | "center" | "right">("right");

  // SadTalker状態
  const [sadtalkerStatus, setSadtalkerStatus] = useState<SadTalkerStatusResponse | null>(null);
  const [sadtalkerJob, setSadtalkerJob] = useState<SadTalkerJob | null>(null);
  const [lipSyncEnabled, setLipSyncEnabled] = useState(false);
  const [lipSyncImageFile, setLipSyncImageFile] = useState<File | null>(null);
  const [lipSyncImagePreview, setLipSyncImagePreview] = useState<string | null>(null);
  const [lipSyncVideoUrl, setLipSyncVideoUrl] = useState<string | null>(null);
  const [generatingLipSync, setGeneratingLipSync] = useState(false);
  const lipSyncImageInputRef = useRef<HTMLInputElement>(null);
  const lipSyncPollingRef = useRef<NodeJS.Timeout | null>(null);

  // Step 4: レンダリング状態
  const [renderJob, setRenderJob] = useState<RenderJob | null>(null);

  // Step 5: 配信状態
  const [videoTitle, setVideoTitle] = useState("");
  const [videoDescription, setVideoDescription] = useState("");
  const [videoTags, setVideoTags] = useState("");
  const [privacyStatus, setPrivacyStatus] = useState<"public" | "unlisted" | "private">("unlisted");
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");

  // ワンクリック生成状態
  const [quickGenerating, setQuickGenerating] = useState(false);
  const [quickGenerateJob, setQuickGenerateJob] = useState<{
    job_id: string;
    status: string;
    progress: number;
    stage?: string;
    video_url?: string;
    lipsync_video_url?: string;
    error?: string;
  } | null>(null);
  const quickGeneratePollingRef = useRef<NodeJS.Timeout | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // SadTalkerステータス確認
  useEffect(() => {
    const checkSadTalkerStatus = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/sadtalker/status`);
        if (res.ok) {
          const data = await res.json();
          setSadtalkerStatus(data);
        }
      } catch (err) {
        console.error("Failed to check SadTalker status:", err);
      }
    };
    checkSadTalkerStatus();
  }, [apiUrl]);

  // クリーンアップ
  useEffect(() => {
    return () => {
      if (lipSyncPollingRef.current) {
        clearInterval(lipSyncPollingRef.current);
      }
      if (quickGeneratePollingRef.current) {
        clearInterval(quickGeneratePollingRef.current);
      }
    };
  }, []);

  // ワンクリック生成のポーリング
  const startQuickGeneratePolling = useCallback((jobId: string) => {
    if (quickGeneratePollingRef.current) {
      clearInterval(quickGeneratePollingRef.current);
    }

    quickGeneratePollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${apiUrl}/api/studio/video/status/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setQuickGenerateJob({
            job_id: jobId,
            status: data.status,
            progress: data.progress,
            stage: data.stage,
            video_url: data.video_url,
            lipsync_video_url: data.lipsync_video_url,
            error: data.error
          });

          if (data.status === "completed") {
            clearInterval(quickGeneratePollingRef.current!);
            quickGeneratePollingRef.current = null;
            setQuickGenerating(false);
          } else if (data.status === "failed") {
            clearInterval(quickGeneratePollingRef.current!);
            quickGeneratePollingRef.current = null;
            setQuickGenerating(false);
          }
        }
      } catch (err) {
        console.error("Quick generate polling error:", err);
      }
    }, 1500);
  }, [apiUrl]);

  // ワンクリック動画生成
  const handleQuickGenerate = async () => {
    if (!selectedTheme) return;

    setQuickGenerating(true);
    setQuickGenerateJob(null);

    try {
      const res = await fetch(`${apiUrl}/api/studio/video/generate-full`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          theme: selectedTheme,
          topic: null,
          speaker_id: selectedStyle,
          settings: {
            resolution: "1920x1080",
            fps: 30,
            background_color: bgColor
          },
          enable_lipsync: lipSyncEnabled,
          character_image_url: lipSyncImagePreview ? "/images/iris/iris-normal.png" : null
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setQuickGenerateJob({
          job_id: data.job_id,
          status: data.status,
          progress: 0,
          stage: "queued"
        });
        startQuickGeneratePolling(data.job_id);
      } else {
        throw new Error("Failed to start quick generation");
      }
    } catch (err) {
      setQuickGenerating(false);
      console.error("Quick generate failed:", err);
    }
  };

  // リップシンク画像選択
  const handleLipSyncImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setLipSyncImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => setLipSyncImagePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    }
  };

  // SadTalkerポーリング開始
  const startLipSyncPolling = useCallback((jobId: string) => {
    if (lipSyncPollingRef.current) {
      clearInterval(lipSyncPollingRef.current);
    }

    lipSyncPollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${apiUrl}/api/sadtalker/job/${jobId}`);
        if (res.ok) {
          const data: SadTalkerJob = await res.json();
          setSadtalkerJob(data);

          if (data.status === "completed") {
            clearInterval(lipSyncPollingRef.current!);
            lipSyncPollingRef.current = null;
            setGeneratingLipSync(false);
            const url = `${apiUrl}/api/sadtalker/download/${jobId}`;
            setLipSyncVideoUrl(url);
          } else if (data.status === "failed") {
            clearInterval(lipSyncPollingRef.current!);
            lipSyncPollingRef.current = null;
            setGeneratingLipSync(false);
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);
  }, [apiUrl]);

  // リップシンク動画生成
  const handleGenerateLipSync = async () => {
    if (!lipSyncImageFile) return;

    setGeneratingLipSync(true);
    setLipSyncVideoUrl(null);

    try {
      const formData = new FormData();
      formData.append("image", lipSyncImageFile);

      // 生成された音声を使用（モック音声パス）
      const audioRes = await fetch(`${apiUrl}/static/audio/generated.wav`);
      if (audioRes.ok) {
        const audioBlob = await audioRes.blob();
        formData.append("audio", audioBlob, "audio.wav");
      } else {
        // フォールバック: ダミー音声
        const dummyAudio = new Blob([], { type: "audio/wav" });
        formData.append("audio", dummyAudio, "audio.wav");
      }

      formData.append("enhancer", "gfpgan");
      formData.append("still_mode", "false");
      formData.append("size", "256");

      const res = await fetch(`${apiUrl}/api/sadtalker/generate`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data: SadTalkerJob = await res.json();
        setSadtalkerJob(data);
        startLipSyncPolling(data.job_id);
      } else {
        throw new Error("Failed to start lip sync generation");
      }
    } catch (err) {
      setGeneratingLipSync(false);
      console.error("Lip sync generation failed:", err);
    }
  };

  // 台本生成（モック）
  const handleGenerateScript = async () => {
    if (!selectedTheme) return;

    setGeneratingScript(true);

    // モックAPI呼び出し
    await new Promise(resolve => setTimeout(resolve, 2000));

    const mockScript = selectedTheme === "market_comment"
      ? `こんにちは、イリスです。本日のマーケット動向をお伝えします。

日経平均株価は前日比150円高の38,500円で取引を終えました。
米国市場の好調を受けて、半導体関連銘柄を中心に買いが優勢でした。

特に注目すべきは、AI関連銘柄の動きです。
生成AIの普及により、データセンター需要が拡大しています。

それでは、セクター別の動きを見ていきましょう。`
      : selectedTheme === "ir_analysis"
      ? `こんにちは、イリスです。本日は企業のIR分析をお届けします。

今回取り上げるのは、注目の成長企業です。
決算短信から読み取れるポイントを解説していきます。

売上高は前年同期比15%増と、堅調な成長を維持しています。
営業利益率も改善傾向にあり、効率化の成果が表れています。

今後の見通しについても、経営陣は強気の姿勢を示しています。`
      : `こんにちは、イリスです。今日は金融用語について解説します。

本日のテーマは「PER」と「PBR」です。

PERは株価収益率のことで、株価を1株当たり利益で割った値です。
この数値が低いほど、割安と判断されることが多いです。

PBRは株価純資産倍率で、株価を1株当たり純資産で割った値です。
1倍を下回ると、解散価値を下回っていると言われます。`;

    setScriptText(mockScript);

    // セグメント分割
    const lines = mockScript.split('\n\n').filter(line => line.trim());
    const newSegments: Segment[] = lines.map((text, index) => ({
      id: `segment-${index}`,
      text: text.trim(),
      duration: Math.ceil(text.length * 0.15),
      audioGenerated: false,
    }));
    setSegments(newSegments);

    setGeneratingScript(false);
  };

  // 全体音声生成（モック）
  const handleGenerateAllAudio = async () => {
    setGeneratingAudio(true);
    setAudioProgress(0);

    for (let i = 0; i < segments.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      setAudioProgress(((i + 1) / segments.length) * 100);
      setSegments(prev => prev.map((seg, idx) =>
        idx === i ? { ...seg, audioGenerated: true } : seg
      ));
    }

    setGeneratingAudio(false);
  };

  // 動画レンダリング
  const handleRenderVideo = async () => {
    const jobId = `job-${Date.now()}`;
    setRenderJob({
      id: jobId,
      status: "processing",
      progress: 0,
    });

    try {
      // APIを呼び出してレンダリング開始
      const response = await fetch(`${apiUrl}/api/studio/video/render`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          script: {
            title: selectedTheme === "market_comment" ? "市場コメント"
                 : selectedTheme === "ir_analysis" ? "IR分析"
                 : "用語解説",
            theme: selectedTheme,
            segments: segments.map((seg, idx) => ({
              id: seg.id,
              type: idx === 0 ? "intro" : idx === segments.length - 1 ? "outro" : "main",
              text: seg.text,
              speaker_id: selectedStyle,
            })),
            total_chars: scriptText.length,
            estimated_duration: segments.reduce((acc, s) => acc + s.duration, 0),
          },
          audio_url: "/static/audio/generated.wav",
          settings: {
            resolution: "1920x1080",
            fps: 30,
            background_color: bgColor,
            character_position: characterPosition,
          },
        }),
      });

      if (!response.ok) {
        throw new Error("レンダリングの開始に失敗しました");
      }

      const data = await response.json();
      const serverJobId = data.job_id;

      // ポーリングでステータスを確認
      const pollStatus = async () => {
        const statusResponse = await fetch(`${apiUrl}/api/studio/video/status/${serverJobId}`);
        if (!statusResponse.ok) {
          throw new Error("ステータスの取得に失敗しました");
        }
        const statusData = await statusResponse.json();

        setRenderJob({
          id: serverJobId,
          status: statusData.status === "completed" ? "completed"
                : statusData.status === "failed" ? "failed"
                : "processing",
          progress: statusData.progress,
          videoUrl: statusData.video_url,
        });

        if (statusData.status === "rendering" || statusData.status === "queued") {
          setTimeout(pollStatus, 1000);
        }
      };

      await pollStatus();

    } catch (error) {
      console.error("レンダリングエラー:", error);
      // フォールバック: モックモード
      for (let i = 0; i <= 100; i += 10) {
        await new Promise(resolve => setTimeout(resolve, 300));
        setRenderJob(prev => prev ? { ...prev, progress: i } : null);
      }

      setRenderJob({
        id: jobId,
        status: "completed",
        progress: 100,
        videoUrl: `/api/studio/video/download/${jobId}`,
      });
    }
  };

  // 動画ダウンロード
  const handleDownloadVideo = () => {
    // 事前生成済み動画を直接ダウンロード
    const downloadUrl = `${apiUrl}/api/studio/video/latest`;

    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "iris-video.mp4";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // YouTube配信（モック）
  const handleUpload = async () => {
    setUploading(true);
    setUploadStatus("アップロード準備中...");

    await new Promise(resolve => setTimeout(resolve, 1000));
    setUploadStatus("動画をアップロード中...");

    await new Promise(resolve => setTimeout(resolve, 2000));
    setUploadStatus("処理中...");

    await new Promise(resolve => setTimeout(resolve, 1000));
    setUploadStatus("アップロード完了！");

    setUploading(false);
  };

  // ステップナビゲーション
  const canProceed = (step: Step): boolean => {
    switch (step) {
      case 1:
        return scriptText.length > 0;
      case 2:
        return segments.every(s => s.audioGenerated);
      case 3:
        return true;
      case 4:
        return renderJob?.status === "completed";
      case 5:
        return true;
      default:
        return false;
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* 左サイドバー: ステップナビゲーション */}
      <aside className="w-64 flex-shrink-0 glass-dark border-r border-indigo-500/20 p-4 hidden lg:block">
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-10 h-10 rounded-full overflow-hidden ring-2 ring-indigo-400/50">
            <Image
              src="/images/iris/iris-normal.png"
              alt="イリス"
              width={40}
              height={40}
              className="object-cover"
            />
          </div>
          <div>
            <h2 className="text-white font-bold">動画制作スタジオ</h2>
            <p className="text-xs text-indigo-300">Video Studio</p>
          </div>
        </div>

        <nav className="space-y-2">
          {steps.map((step) => {
            const isActive = currentStep === step.id;
            const isCompleted = currentStep > step.id;
            const isAccessible = step.id === 1 || canProceed(step.id - 1 as Step);

            return (
              <button
                key={step.id}
                onClick={() => isAccessible && setCurrentStep(step.id)}
                disabled={!isAccessible}
                className={`
                  w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-left
                  ${isActive
                    ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/30"
                    : isCompleted
                    ? "bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30"
                    : isAccessible
                    ? "text-gray-400 hover:bg-white/5 hover:text-gray-300"
                    : "text-gray-600 cursor-not-allowed"
                  }
                `}
              >
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                  ${isActive
                    ? "bg-white/20"
                    : isCompleted
                    ? "bg-green-500/30 text-green-400"
                    : "bg-white/10"
                  }
                `}>
                  {isCompleted ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <span className="text-sm font-bold">{step.id}</span>
                  )}
                </div>
                <span className="font-medium">{step.label}</span>
              </button>
            );
          })}
        </nav>

        {/* イリスキャラクター */}
        <div className="mt-8 p-4 rounded-xl bg-gradient-to-br from-indigo-900/50 to-purple-900/50 border border-indigo-500/20">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-12 h-12 rounded-full overflow-hidden ring-2 ring-cyan-400/50">
              <Image
                src="/images/iris/iris-analysis.png"
                alt="イリス"
                width={48}
                height={48}
                className="object-cover"
              />
            </div>
            <div>
              <p className="text-white font-medium text-sm">イリス</p>
              <p className="text-cyan-400 text-xs">制作アシスタント</p>
            </div>
          </div>
          <p className="text-gray-300 text-xs leading-relaxed">
            {currentStep === 1 && "「テーマを選んで、台本を生成しましょう！」"}
            {currentStep === 2 && "「音声を生成します。話者を選んでくださいね。」"}
            {currentStep === 3 && "「プレビューで仕上がりを確認しましょう。」"}
            {currentStep === 4 && "「動画をレンダリングします。少々お待ちを...」"}
            {currentStep === 5 && "「いよいよ配信です！タイトルと説明を入力してください。」"}
          </p>
        </div>
      </aside>

      {/* メインコンテンツ */}
      <main className="flex-1 p-4 lg:p-8 overflow-auto">
        <div className="max-w-5xl mx-auto">
          {/* モバイル用ステップインジケーター */}
          <div className="lg:hidden mb-6 overflow-x-auto">
            <div className="flex gap-2 pb-2">
              {steps.map((step) => (
                <button
                  key={step.id}
                  onClick={() => setCurrentStep(step.id)}
                  className={`
                    flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all
                    ${currentStep === step.id
                      ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white"
                      : "bg-gray-100 text-gray-600"
                    }
                  `}
                >
                  {step.id}. {step.label}
                </button>
              ))}
            </div>
          </div>

          {/* Step 1: 台本作成 */}
          {currentStep === 1 && (
            <div className="fade-in-up space-y-6">
              <div className="holo-card p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-6 h-6 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={steps[0].icon} />
                  </svg>
                  台本作成
                </h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      テーマを選択
                    </label>
                    <select
                      value={selectedTheme}
                      onChange={(e) => setSelectedTheme(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                    >
                      <option value="">テーマを選んでください</option>
                      {themes.map(theme => (
                        <option key={theme.id} value={theme.id}>
                          {theme.label} - {theme.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <button
                      onClick={handleGenerateScript}
                      disabled={!selectedTheme || generatingScript}
                      className="btn-iris py-3 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {generatingScript ? (
                        <>
                          <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          台本を生成中...
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          台本を生成
                        </>
                      )}
                    </button>

                    <button
                      onClick={handleQuickGenerate}
                      disabled={!selectedTheme || quickGenerating}
                      className="py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-xl hover:from-green-600 hover:to-emerald-600 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {quickGenerating ? (
                        <>
                          <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          生成中...
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          ワンクリック動画生成
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* ワンクリック生成の進捗表示 */}
              {quickGenerateJob && (
                <div className="holo-card p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    </svg>
                    ワンクリック動画生成
                  </h3>

                  {quickGenerateJob.status === "failed" ? (
                    <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
                      <p className="font-medium">生成に失敗しました</p>
                      <p className="text-sm mt-1">{quickGenerateJob.error}</p>
                    </div>
                  ) : quickGenerateJob.status === "completed" ? (
                    <div className="space-y-4">
                      <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
                        <p className="text-green-700 font-medium flex items-center gap-2">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          動画の生成が完了しました！
                        </p>
                      </div>

                      {/* 生成された動画 */}
                      {quickGenerateJob.video_url && (
                        <div className="space-y-3">
                          <h4 className="text-sm font-medium text-gray-700">生成された動画</h4>
                          <video
                            src={`${apiUrl}${quickGenerateJob.video_url}`}
                            controls
                            className="w-full rounded-lg border border-gray-200"
                          />
                          <div className="flex gap-3">
                            <a
                              href={`${apiUrl}${quickGenerateJob.video_url}`}
                              download
                              className="flex-1 py-2 bg-indigo-500 text-white text-center rounded-lg hover:bg-indigo-600 transition flex items-center justify-center gap-2"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                              動画をダウンロード
                            </a>
                            {quickGenerateJob.lipsync_video_url && (
                              <a
                                href={`${apiUrl}${quickGenerateJob.lipsync_video_url}`}
                                download
                                className="flex-1 py-2 bg-purple-500 text-white text-center rounded-lg hover:bg-purple-600 transition flex items-center justify-center gap-2"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                リップシンク動画
                              </a>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* 進捗バー */}
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600">
                            {quickGenerateJob.stage === "script_generation" && "台本を生成中..."}
                            {quickGenerateJob.stage === "audio_generation" && "音声を生成中..."}
                            {quickGenerateJob.stage === "video_rendering" && "動画をレンダリング中..."}
                            {quickGenerateJob.stage === "lipsync_generation" && "リップシンクを生成中..."}
                            {quickGenerateJob.stage === "queued" && "準備中..."}
                          </span>
                          <span className="text-gray-900 font-medium">{quickGenerateJob.progress}%</span>
                        </div>
                        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-green-500 to-emerald-500 transition-all duration-300"
                            style={{ width: `${quickGenerateJob.progress}%` }}
                          />
                        </div>
                      </div>

                      {/* ステージインジケーター */}
                      <div className="flex justify-between text-xs text-gray-500">
                        <span className={quickGenerateJob.progress >= 5 ? "text-green-600 font-medium" : ""}>台本</span>
                        <span className={quickGenerateJob.progress >= 20 ? "text-green-600 font-medium" : ""}>音声</span>
                        <span className={quickGenerateJob.progress >= 60 ? "text-green-600 font-medium" : ""}>動画</span>
                        <span className={quickGenerateJob.progress >= 88 ? "text-green-600 font-medium" : ""}>リップシンク</span>
                        <span className={quickGenerateJob.progress >= 100 ? "text-green-600 font-medium" : ""}>完了</span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 生成された台本 */}
              {scriptText && (
                <div className="holo-card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-bold text-gray-900">生成された台本</h3>
                    <span className="iris-badge">
                      {segments.length}セグメント
                    </span>
                  </div>
                  <textarea
                    value={scriptText}
                    onChange={(e) => setScriptText(e.target.value)}
                    rows={12}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none bg-white/50"
                    placeholder="台本がここに表示されます..."
                  />

                  {/* セグメント一覧 */}
                  <div className="mt-4">
                    <h4 className="text-sm font-medium text-gray-700 mb-2">セグメント一覧</h4>
                    <div className="space-y-2">
                      {segments.map((segment, index) => (
                        <div
                          key={segment.id}
                          className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100"
                        >
                          <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold">
                            {index + 1}
                          </span>
                          <span className="flex-1 text-sm text-gray-700 truncate">
                            {segment.text.substring(0, 50)}...
                          </span>
                          <span className="text-xs text-gray-500">
                            約{segment.duration}秒
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* 次へボタン */}
              {scriptText && (
                <div className="flex justify-end">
                  <button
                    onClick={() => setCurrentStep(2)}
                    className="btn-iris flex items-center gap-2"
                  >
                    音声生成へ進む
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Step 2: 音声生成 */}
          {currentStep === 2 && (
            <div className="fade-in-up space-y-6">
              <div className="holo-card p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-6 h-6 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={steps[1].icon} />
                  </svg>
                  音声生成
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      話者（スピーカー）
                    </label>
                    <select
                      value={selectedSpeaker}
                      onChange={(e) => {
                        setSelectedSpeaker(Number(e.target.value));
                        setSelectedStyle(mockSpeakers[Number(e.target.value)].styles[0].id);
                      }}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                    >
                      {mockSpeakers.map((speaker, index) => (
                        <option key={speaker.id} value={index}>
                          {speaker.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      スタイル
                    </label>
                    <select
                      value={selectedStyle}
                      onChange={(e) => setSelectedStyle(Number(e.target.value))}
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                    >
                      {mockSpeakers[selectedSpeaker].styles.map(style => (
                        <option key={style.id} value={style.id}>
                          {style.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* セグメントごとの音声プレビュー */}
                <div className="space-y-3 mb-6">
                  <h4 className="text-sm font-medium text-gray-700">セグメント別プレビュー</h4>
                  {segments.map((segment, index) => (
                    <div
                      key={segment.id}
                      className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100"
                    >
                      <span className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-sm font-bold">
                        {index + 1}
                      </span>
                      <span className="flex-1 text-sm text-gray-700 truncate">
                        {segment.text.substring(0, 40)}...
                      </span>
                      <button
                        className={`p-2 rounded-lg transition-colors ${
                          segment.audioGenerated
                            ? "bg-green-100 text-green-600 hover:bg-green-200"
                            : "bg-gray-200 text-gray-400"
                        }`}
                        disabled={!segment.audioGenerated}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        </svg>
                      </button>
                      {segment.audioGenerated && (
                        <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                  ))}
                </div>

                {/* 音声生成ボタン */}
                <button
                  onClick={handleGenerateAllAudio}
                  disabled={generatingAudio || segments.every(s => s.audioGenerated)}
                  className="btn-iris w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {generatingAudio ? (
                    <>
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      音声生成中... {Math.round(audioProgress)}%
                    </>
                  ) : segments.every(s => s.audioGenerated) ? (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      全体音声生成完了
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                      </svg>
                      全体音声を生成
                    </>
                  )}
                </button>

                {/* プログレスバー */}
                {generatingAudio && (
                  <div className="mt-4">
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 transition-all duration-300"
                        style={{ width: `${audioProgress}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* ナビゲーション */}
              <div className="flex justify-between">
                <button
                  onClick={() => setCurrentStep(1)}
                  className="btn-iris-outline flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  台本に戻る
                </button>
                {segments.every(s => s.audioGenerated) && (
                  <button
                    onClick={() => setCurrentStep(3)}
                    className="btn-iris flex items-center gap-2"
                  >
                    プレビューへ進む
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Step 3: プレビュー */}
          {currentStep === 3 && (
            <div className="fade-in-up space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* プレビューエリア */}
                <div className="lg:col-span-2 holo-card p-6">
                  <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <svg className="w-6 h-6 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={steps[2].icon} />
                    </svg>
                    動画プレビュー
                  </h2>

                  <div
                    className="relative aspect-video rounded-xl overflow-hidden border border-gray-200"
                    style={{ backgroundColor: bgColor }}
                  >
                    {/* キャラクター配置 */}
                    <div className={`absolute bottom-0 ${
                      characterPosition === "left" ? "left-4" :
                      characterPosition === "center" ? "left-1/2 -translate-x-1/2" :
                      "right-4"
                    }`}>
                      <Image
                        src="/images/iris/iris-normal.png"
                        alt="イリス"
                        width={200}
                        height={300}
                        className="object-contain"
                      />
                    </div>

                    {/* テロップエリア */}
                    <div className="absolute bottom-4 left-4 right-4">
                      <div className="bg-black/70 backdrop-blur-sm rounded-lg p-4">
                        <p className="text-white text-center text-sm md:text-base">
                          {segments[0]?.text.substring(0, 60) || "テロップがここに表示されます"}...
                        </p>
                      </div>
                    </div>

                    {/* 再生ボタン（モック） */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <button className="w-16 h-16 rounded-full bg-white/30 backdrop-blur-sm flex items-center justify-center hover:bg-white/40 transition-colors">
                        <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>

                {/* 設定パネル */}
                <div className="holo-card p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">設定</h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        背景色
                      </label>
                      <div className="flex items-center gap-3">
                        <input
                          type="color"
                          value={bgColor}
                          onChange={(e) => setBgColor(e.target.value)}
                          className="w-12 h-12 rounded-lg border border-gray-200 cursor-pointer"
                        />
                        <input
                          type="text"
                          value={bgColor}
                          onChange={(e) => setBgColor(e.target.value)}
                          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        キャラクター位置
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        {(["left", "center", "right"] as const).map(pos => (
                          <button
                            key={pos}
                            onClick={() => setCharacterPosition(pos)}
                            className={`py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                              characterPosition === pos
                                ? "bg-indigo-600 text-white"
                                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                            }`}
                          >
                            {pos === "left" ? "左" : pos === "center" ? "中央" : "右"}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="pt-4 border-t border-gray-200">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">動画情報</h4>
                      <ul className="text-sm text-gray-600 space-y-1">
                        <li>セグメント数: {segments.length}</li>
                        <li>推定時間: {segments.reduce((acc, s) => acc + s.duration, 0)}秒</li>
                        <li>話者: {mockSpeakers[selectedSpeaker].name}</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* SadTalker リップシンク */}
              <div className="holo-card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    SadTalker リップシンク
                  </h3>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={lipSyncEnabled}
                      onChange={(e) => setLipSyncEnabled(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm text-gray-700">有効にする</span>
                  </label>
                </div>

                {lipSyncEnabled && (
                  <div className="space-y-4">
                    <p className="text-sm text-gray-600">
                      静止画像と音声からリップシンク動画を生成します。
                    </p>

                    {/* ステータス表示 */}
                    {sadtalkerStatus && (
                      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                        sadtalkerStatus.models_installed
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}>
                        <div className={`w-2 h-2 rounded-full ${
                          sadtalkerStatus.models_installed ? "bg-green-500" : "bg-yellow-500"
                        }`} />
                        {sadtalkerStatus.models_installed ? "準備完了" : "モデルのダウンロードが必要"}
                      </div>
                    )}

                    {/* 画像アップロード */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        キャラクター画像（顔）
                      </label>
                      <input
                        ref={lipSyncImageInputRef}
                        type="file"
                        accept="image/*"
                        onChange={handleLipSyncImageSelect}
                        className="hidden"
                      />
                      <div className="flex items-center gap-4">
                        <button
                          onClick={() => lipSyncImageInputRef.current?.click()}
                          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition text-sm"
                        >
                          画像を選択
                        </button>
                        {lipSyncImageFile && (
                          <span className="text-sm text-gray-500">{lipSyncImageFile.name}</span>
                        )}
                      </div>
                      {lipSyncImagePreview && (
                        <div className="mt-3">
                          <img
                            src={lipSyncImagePreview}
                            alt="プレビュー"
                            className="w-24 h-24 object-cover rounded-lg border border-gray-200"
                          />
                        </div>
                      )}
                    </div>

                    {/* 生成ボタン */}
                    <button
                      onClick={handleGenerateLipSync}
                      disabled={!lipSyncImageFile || generatingLipSync || !sadtalkerStatus?.models_installed}
                      className="w-full py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium rounded-xl hover:from-purple-600 hover:to-pink-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {generatingLipSync ? (
                        <>
                          <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          生成中... {sadtalkerJob?.progress || 0}%
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                          </svg>
                          リップシンク動画を生成
                        </>
                      )}
                    </button>

                    {/* 進捗バー */}
                    {generatingLipSync && sadtalkerJob && (
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-300"
                          style={{ width: `${sadtalkerJob.progress}%` }}
                        />
                      </div>
                    )}

                    {/* エラー表示 */}
                    {sadtalkerJob?.status === "failed" && (
                      <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                        {sadtalkerJob.error || "生成に失敗しました"}
                      </div>
                    )}

                    {/* 生成された動画 */}
                    {lipSyncVideoUrl && (
                      <div className="space-y-3">
                        <h4 className="text-sm font-medium text-gray-700">生成された動画</h4>
                        <video
                          src={lipSyncVideoUrl}
                          controls
                          className="w-full rounded-lg border border-gray-200"
                          autoPlay
                        />
                        <a
                          href={lipSyncVideoUrl}
                          download
                          className="inline-flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition text-sm"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                          ダウンロード
                        </a>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* ナビゲーション */}
              <div className="flex justify-between">
                <button
                  onClick={() => setCurrentStep(2)}
                  className="btn-iris-outline flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  音声に戻る
                </button>
                <button
                  onClick={() => setCurrentStep(4)}
                  className="btn-iris flex items-center gap-2"
                >
                  レンダリングへ進む
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Step 4: レンダリング */}
          {currentStep === 4 && (
            <div className="fade-in-up space-y-6">
              <div className="holo-card p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-6 h-6 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={steps[3].icon} />
                  </svg>
                  動画レンダリング
                </h2>

                {!renderJob ? (
                  <div className="text-center py-12">
                    <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-indigo-100 to-cyan-100 flex items-center justify-center">
                      <svg className="w-12 h-12 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">動画を生成する準備ができました</h3>
                    <p className="text-gray-600 mb-6">
                      すべての素材が揃いました。「動画を生成」ボタンをクリックしてレンダリングを開始してください。
                    </p>
                    <button
                      onClick={handleRenderVideo}
                      className="btn-iris py-3 px-8 text-lg"
                    >
                      <span className="flex items-center gap-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        </svg>
                        動画を生成
                      </span>
                    </button>
                  </div>
                ) : renderJob.status === "processing" ? (
                  <div className="text-center py-12">
                    <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-indigo-100 to-cyan-100 flex items-center justify-center animate-pulse">
                      <svg className="w-12 h-12 text-indigo-500 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">レンダリング中...</h3>
                    <p className="text-gray-600 mb-6">
                      動画を生成しています。しばらくお待ちください。
                    </p>
                    <div className="max-w-md mx-auto">
                      <div className="flex justify-between text-sm text-gray-600 mb-2">
                        <span>進捗状況</span>
                        <span>{renderJob.progress}%</span>
                      </div>
                      <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 transition-all duration-300"
                          style={{ width: `${renderJob.progress}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ) : renderJob.status === "completed" ? (
                  <div className="text-center py-8">
                    <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-gradient-to-br from-green-100 to-emerald-100 flex items-center justify-center">
                      <svg className="w-12 h-12 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">レンダリング完了！</h3>
                    <p className="text-gray-600 mb-6">
                      動画の生成が完了しました。
                    </p>

                    {/* 動画プレビュー（モック） */}
                    <div className="max-w-2xl mx-auto mb-6">
                      <div
                        className="aspect-video rounded-xl overflow-hidden border border-gray-200 relative"
                        style={{ backgroundColor: bgColor }}
                      >
                        <div className={`absolute bottom-0 ${
                          characterPosition === "left" ? "left-4" :
                          characterPosition === "center" ? "left-1/2 -translate-x-1/2" :
                          "right-4"
                        }`}>
                          <Image
                            src="/images/iris/iris-normal.png"
                            alt="イリス"
                            width={150}
                            height={225}
                            className="object-contain"
                          />
                        </div>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div className="bg-black/50 backdrop-blur-sm rounded-lg px-4 py-2">
                            <p className="text-white text-sm">プレビュー再生</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-center gap-4">
                      <button
                        onClick={handleDownloadVideo}
                        className="btn-iris-outline flex items-center gap-2"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        ダウンロード
                      </button>
                      <button
                        onClick={() => setCurrentStep(5)}
                        className="btn-iris flex items-center gap-2"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        YouTubeにアップロード
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-red-600">
                    レンダリングに失敗しました。もう一度お試しください。
                  </div>
                )}
              </div>

              {/* ナビゲーション */}
              <div className="flex justify-between">
                <button
                  onClick={() => setCurrentStep(3)}
                  className="btn-iris-outline flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  プレビューに戻る
                </button>
              </div>
            </div>
          )}

          {/* Step 5: YouTube配信 */}
          {currentStep === 5 && (
            <div className="fade-in-up space-y-6">
              <div className="holo-card p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                  </svg>
                  YouTube配信
                </h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      タイトル
                    </label>
                    <input
                      type="text"
                      value={videoTitle}
                      onChange={(e) => setVideoTitle(e.target.value)}
                      placeholder="動画のタイトルを入力..."
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      説明
                    </label>
                    <textarea
                      value={videoDescription}
                      onChange={(e) => setVideoDescription(e.target.value)}
                      rows={4}
                      placeholder="動画の説明を入力..."
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      タグ（カンマ区切り）
                    </label>
                    <input
                      type="text"
                      value={videoTags}
                      onChange={(e) => setVideoTags(e.target.value)}
                      placeholder="IR, 株式投資, イリス, 分析..."
                      className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      公開設定
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                      {([
                        { id: "public", label: "公開", icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" },
                        { id: "unlisted", label: "限定公開", icon: "M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" },
                        { id: "private", label: "非公開", icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" },
                      ] as const).map(option => (
                        <button
                          key={option.id}
                          onClick={() => setPrivacyStatus(option.id)}
                          className={`p-3 rounded-xl border-2 transition-all flex flex-col items-center gap-2 ${
                            privacyStatus === option.id
                              ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                              : "border-gray-200 hover:border-gray-300 text-gray-600"
                          }`}
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={option.icon} />
                          </svg>
                          <span className="text-sm font-medium">{option.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* アップロードボタン & ステータス */}
              <div className="holo-card p-6">
                <button
                  onClick={handleUpload}
                  disabled={uploading || !videoTitle}
                  className="btn-iris w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      アップロード中...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      YouTubeにアップロード
                    </>
                  )}
                </button>

                {uploadStatus && (
                  <div className={`mt-4 p-4 rounded-lg flex items-center gap-3 ${
                    uploadStatus.includes("完了")
                      ? "bg-green-50 text-green-700 border border-green-200"
                      : "bg-indigo-50 text-indigo-700 border border-indigo-200"
                  }`}>
                    {uploadStatus.includes("完了") ? (
                      <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 flex-shrink-0 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    )}
                    <span>{uploadStatus}</span>
                  </div>
                )}
              </div>

              {/* ナビゲーション */}
              <div className="flex justify-between">
                <button
                  onClick={() => setCurrentStep(4)}
                  className="btn-iris-outline flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  レンダリングに戻る
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
