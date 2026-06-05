"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import { api } from "@/lib/api";
import type { Document, Company, VTuberScript, ScriptType, ScriptTypeId } from "@/types";
import { VRM_MODELS, DEFAULT_MODEL_ID } from "@/config/vrm-models";

// VRMViewerは動的インポート（SSR無効化）
const VRMViewer = dynamic(
  () => import("@/components/VRMViewer").then((mod) => mod.VRMViewer),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full text-gray-400">3Dモデル読み込み中...</div> }
);

// アイコンコンポーネント
const ScriptTypeIcon = ({ icon }: { icon: string }) => {
  switch (icon) {
    case "document":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    case "sun":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      );
    case "chart-bar":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      );
    case "tag":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
      );
    case "chart-line":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
        </svg>
      );
    case "briefcase":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      );
    case "heart":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
        </svg>
      );
    default:
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      );
  }
};

// テーマ株のプリセット
const THEME_PRESETS = [
  "AI関連",
  "半導体関連",
  "EV・電気自動車関連",
  "再生可能エネルギー関連",
  "メタバース関連",
  "DX（デジタルトランスフォーメーション）関連",
  "宇宙関連",
  "防衛関連",
  "インバウンド関連",
  "高配当株",
];

export default function VTuberPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [companies, setCompanies] = useState<Map<number, Company>>(new Map());
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [script, setScript] = useState<VTuberScript | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  // 台本タイプ関連
  const [scriptTypes, setScriptTypes] = useState<ScriptType[]>([]);
  const [selectedScriptType, setSelectedScriptType] = useState<ScriptTypeId>("ir_document");

  // 各タイプ用の入力フォーム状態
  const [morningInput, setMorningInput] = useState({
    previous_day_summary: "",
    today_events: "",
  });
  const [earningsInput, setEarningsInput] = useState({
    tickers: "",
  });
  const [themeInput, setThemeInput] = useState({
    theme: "",
  });
  const [technicalInput, setTechnicalInput] = useState({
    ticker: "",
  });
  const [portfolioInput, setPortfolioInput] = useState({
    positions: "",
    summary: "",
  });
  const [sentimentInput, setSentimentInput] = useState({
    fear_greed_index: 50,
    vix: undefined as number | undefined,
  });

  // VRM/TTS関連の状態
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [generatingAudio, setGeneratingAudio] = useState(false);
  const [audioError, setAudioError] = useState("");
  const defaultModel = VRM_MODELS.find(m => m.id === DEFAULT_MODEL_ID) || VRM_MODELS[0];

  useEffect(() => {
    Promise.all([
      api.getDocuments(undefined, 30),
      api.getCompanies(),
      api.getScriptTypes().catch(() => []),
    ])
      .then(async ([docs, comps, types]) => {
        setDocuments(docs);
        const compMap = new Map<number, Company>();
        comps.forEach((c) => compMap.set(c.id, c));
        setCompanies(compMap);
        if (types.length > 0) {
          setScriptTypes(types);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // IR資料から台本生成
  const handleGenerateFromDocument = async () => {
    if (!selectedDocId) return;

    setGenerating(true);
    setError("");
    setScript(null);

    try {
      const result = await api.generateScriptFromDocument(selectedDocId);
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // 朝の市況サマリー台本生成
  const handleGenerateMorningScript = async () => {
    setGenerating(true);
    setError("");
    setScript(null);

    try {
      const result = await api.generateMorningScript({
        previous_day_summary: morningInput.previous_day_summary || undefined,
        today_events: morningInput.today_events || undefined,
      });
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // 決算シーズン特集台本生成
  const handleGenerateEarningsScript = async () => {
    if (!earningsInput.tickers.trim()) {
      setError("銘柄コードを入力してください");
      return;
    }

    setGenerating(true);
    setError("");
    setScript(null);

    try {
      const tickers = earningsInput.tickers.split(/[,\s]+/).filter(Boolean);
      const result = await api.generateEarningsScript({ tickers });
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // テーマ株特集台本生成
  const handleGenerateThemeScript = async () => {
    if (!themeInput.theme.trim()) {
      setError("テーマを入力してください");
      return;
    }

    setGenerating(true);
    setError("");
    setScript(null);

    try {
      const result = await api.generateThemeScript({ theme: themeInput.theme });
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // テクニカル分析台本生成
  const handleGenerateTechnicalScript = async () => {
    if (!technicalInput.ticker.trim()) {
      setError("銘柄コードを入力してください");
      return;
    }

    setGenerating(true);
    setError("");
    setScript(null);

    try {
      const result = await api.generateTechnicalScript({ ticker: technicalInput.ticker });
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // ポートフォリオレビュー台本生成
  const handleGeneratePortfolioScript = async () => {
    setGenerating(true);
    setError("");
    setScript(null);

    try {
      // サンプルデータ（実際はユーザーのポートフォリオデータを使用）
      const positions = [
        { ticker: "7203.T", name: "トヨタ自動車", quantity: 100, avg_cost: 2800, current_price: 3000, unrealized_pnl: 20000, pnl_percent: 7.14 },
        { ticker: "6758.T", name: "ソニーグループ", quantity: 50, avg_cost: 14000, current_price: 15000, unrealized_pnl: 50000, pnl_percent: 7.14 },
      ];
      const portfolio_summary = {
        total_value: 1050000,
        weekly_pnl: 35000,
        weekly_return: 3.5,
        ytd_return: 12.5,
      };

      const result = await api.generatePortfolioScript({ positions, portfolio_summary });
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // 市場心理解説台本生成
  const handleGenerateSentimentScript = async () => {
    setGenerating(true);
    setError("");
    setScript(null);

    try {
      const result = await api.generateSentimentScript({
        fear_greed_index: sentimentInput.fear_greed_index,
        vix: sentimentInput.vix,
      });
      setScript(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "台本生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  // 統合生成ハンドラー
  const handleGenerate = () => {
    switch (selectedScriptType) {
      case "ir_document":
        handleGenerateFromDocument();
        break;
      case "morning_market":
        handleGenerateMorningScript();
        break;
      case "earnings_season":
        handleGenerateEarningsScript();
        break;
      case "theme_stock":
        handleGenerateThemeScript();
        break;
      case "technical_analysis":
        handleGenerateTechnicalScript();
        break;
      case "portfolio_review":
        handleGeneratePortfolioScript();
        break;
      case "fear_greed_commentary":
        handleGenerateSentimentScript();
        break;
    }
  };

  // 音声生成関数
  const handleGenerateAudio = async () => {
    if (!script) return;

    // 既存のaudioUrlをクリーンアップ
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }

    setGeneratingAudio(true);
    setAudioError("");

    try {
      const result = await api.generateSpeech(script.script);
      const audioBlob = new Blob(
        [Uint8Array.from(atob(result.audioBase64), c => c.charCodeAt(0))],
        { type: "audio/wav" }
      );
      setAudioUrl(URL.createObjectURL(audioBlob));
    } catch (err) {
      console.error(err);
      setAudioError(err instanceof Error ? err.message : "音声生成に失敗しました");
    } finally {
      setGeneratingAudio(false);
    }
  };

  // 生成ボタンの有効/無効判定
  const isGenerateDisabled = () => {
    if (generating) return true;
    switch (selectedScriptType) {
      case "ir_document":
        return !selectedDocId;
      case "earnings_season":
        return !earningsInput.tickers.trim();
      case "theme_stock":
        return !themeInput.theme.trim();
      case "technical_analysis":
        return !technicalInput.ticker.trim();
      default:
        return false;
    }
  };

  // 現在の台本タイプ情報を取得
  const currentScriptType = scriptTypes.find(t => t.id === selectedScriptType);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2 animate-pulse">
            <Image
              src="/images/iris/iris-normal.png"
              alt="イリス"
              width={64}
              height={64}
              className="object-cover"
            />
          </div>
          <p className="text-indigo-600 text-sm">読み込み中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* ヘッダー */}
      <div className="glass rounded-2xl p-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex-shrink-0">
            <div className="relative w-16 h-16 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
              <Image
                src="/images/iris/iris-normal.png"
                alt="イリス"
                width={64}
                height={64}
                className="object-cover"
              />
            </div>
          </div>
          <div className="flex-1">
            <h1 className="section-title text-2xl md:text-3xl">イリスの台本スタジオ</h1>
            <p className="text-gray-600 mt-3">
              「様々なコンテンツタイプの台本を自動生成します。IR解説から市況サマリー、テーマ株特集まで対応しています。」
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 左: 台本タイプ選択と入力フォーム */}
        <div className="space-y-6">
          {/* 台本タイプ選択 */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
              </svg>
              台本タイプを選択
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {scriptTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => {
                    setSelectedScriptType(type.id);
                    setError("");
                  }}
                  className={`p-3 rounded-xl border-2 transition-all text-left ${
                    selectedScriptType === type.id
                      ? "border-indigo-500 bg-indigo-50"
                      : "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"
                  }`}
                >
                  <div className={`mb-2 ${selectedScriptType === type.id ? "text-indigo-600" : "text-gray-500"}`}>
                    <ScriptTypeIcon icon={type.icon} />
                  </div>
                  <div className={`text-sm font-medium ${selectedScriptType === type.id ? "text-indigo-900" : "text-gray-700"}`}>
                    {type.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{type.duration}</div>
                </button>
              ))}
            </div>
            {currentScriptType && (
              <p className="mt-4 text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
                {currentScriptType.description}
              </p>
            )}
          </div>

          {/* 入力フォーム */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              入力情報
            </h2>

            {/* IR資料解説フォーム */}
            {selectedScriptType === "ir_document" && (
              <div className="space-y-4">
                <div className="relative">
                  <select
                    value={selectedDocId || ""}
                    onChange={(e) => setSelectedDocId(Number(e.target.value) || null)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent appearance-none bg-white cursor-pointer"
                  >
                    <option value="">ドキュメントを選択してください</option>
                    {documents.map((doc) => {
                      const company = companies.get(doc.company_id);
                      return (
                        <option key={doc.id} value={doc.id}>
                          {company?.name || "不明"} - {doc.title} ({doc.publish_date})
                        </option>
                      );
                    })}
                  </select>
                  <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>
            )}

            {/* 朝の市況サマリーフォーム */}
            {selectedScriptType === "morning_market" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">前日のポイント（任意）</label>
                  <textarea
                    value={morningInput.previous_day_summary}
                    onChange={(e) => setMorningInput({ ...morningInput, previous_day_summary: e.target.value })}
                    placeholder="例：米国株が大幅上昇、半導体セクターが好調"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">今日の注目イベント（任意）</label>
                  <textarea
                    value={morningInput.today_events}
                    onChange={(e) => setMorningInput({ ...morningInput, today_events: e.target.value })}
                    placeholder="例：日銀金融政策決定会合、トヨタ決算発表"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                    rows={2}
                  />
                </div>
                <p className="text-xs text-gray-500">市況データは自動的に取得されます</p>
              </div>
            )}

            {/* 決算シーズン特集フォーム */}
            {selectedScriptType === "earnings_season" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">対象銘柄コード（カンマ区切り）</label>
                  <input
                    type="text"
                    value={earningsInput.tickers}
                    onChange={(e) => setEarningsInput({ ...earningsInput, tickers: e.target.value })}
                    placeholder="例：7203.T, 6758.T, 9984.T"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <p className="text-xs text-gray-500">複数の銘柄を横断的に分析します</p>
              </div>
            )}

            {/* テーマ株特集フォーム */}
            {selectedScriptType === "theme_stock" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">テーマ</label>
                  <input
                    type="text"
                    value={themeInput.theme}
                    onChange={(e) => setThemeInput({ ...themeInput, theme: e.target.value })}
                    placeholder="例：AI関連、半導体関連"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">おすすめテーマ</label>
                  <div className="flex flex-wrap gap-2">
                    {THEME_PRESETS.map((theme) => (
                      <button
                        key={theme}
                        onClick={() => setThemeInput({ theme })}
                        className={`px-3 py-1 text-xs rounded-full transition-colors ${
                          themeInput.theme === theme
                            ? "bg-indigo-500 text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-indigo-100"
                        }`}
                      >
                        {theme}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* テクニカル分析フォーム */}
            {selectedScriptType === "technical_analysis" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">銘柄コード</label>
                  <input
                    type="text"
                    value={technicalInput.ticker}
                    onChange={(e) => setTechnicalInput({ ...technicalInput, ticker: e.target.value })}
                    placeholder="例：7203.T"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <p className="text-xs text-gray-500">株価データは自動的に取得されます</p>
              </div>
            )}

            {/* ポートフォリオレビューフォーム */}
            {selectedScriptType === "portfolio_review" && (
              <div className="space-y-4">
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <p className="text-sm text-amber-800">
                    現在はサンプルデータで台本を生成します。今後、実際のポートフォリオ連携を追加予定です。
                  </p>
                </div>
              </div>
            )}

            {/* 市場心理解説フォーム */}
            {selectedScriptType === "fear_greed_commentary" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    恐怖強欲指数: {sentimentInput.fear_greed_index}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={sentimentInput.fear_greed_index}
                    onChange={(e) => setSentimentInput({ ...sentimentInput, fear_greed_index: Number(e.target.value) })}
                    className="w-full h-2 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>極度の恐怖</span>
                    <span>中立</span>
                    <span>極度の強欲</span>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">VIX指数（任意）</label>
                  <input
                    type="number"
                    value={sentimentInput.vix || ""}
                    onChange={(e) => setSentimentInput({ ...sentimentInput, vix: e.target.value ? Number(e.target.value) : undefined })}
                    placeholder="例：22.5"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
              </div>
            )}

            {/* 生成ボタン */}
            <button
              onClick={handleGenerate}
              disabled={isGenerateDisabled()}
              className="w-full mt-6 btn-iris py-3 text-base font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  台本生成中...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                  台本を生成
                </>
              )}
            </button>

            {error && (
              <div className="mt-4 flex items-center gap-3 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-200">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {error}
              </div>
            )}
          </div>

          {/* キャラクター情報 */}
          <div className="holo-card p-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-20 h-20 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
                <Image
                  src="/images/iris/iris-analysis.png"
                  alt="イリス"
                  width={80}
                  height={80}
                  className="object-cover"
                />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-gray-900 mb-1">イリス</h3>
                <p className="text-sm text-indigo-600 mb-2">2050年から来たAIアナリスト</p>
                <p className="text-sm text-gray-600 leading-relaxed">
                  難しい金融用語も分かりやすく説明するのが得意。クールだけど、面白いデータを見つけると少し興奮する一面も。口癖は「データは嘘をつきませんから」。
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 右: 台本プレビュー */}
        <div className="space-y-6">
          {/* VRMビューワー */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              3Dプレビュー
            </h2>
            <div className="h-[300px] bg-gradient-to-br from-indigo-50/50 via-purple-50/50 to-cyan-50/50 rounded-xl border border-indigo-100 overflow-hidden">
              <VRMViewer
                modelUrl={defaultModel.path}
                className="w-full h-full"
              />
            </div>
          </div>

          {/* 台本プレビュー */}
          <div className="holo-card p-6 min-h-[400px]">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              生成された台本
            </h2>

            {script ? (
              <div>
                <div className="flex flex-wrap items-center justify-between gap-2 mb-4 p-3 glass rounded-lg">
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    <span>{script.character_name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>推定 {script.duration_estimate}</span>
                  </div>
                </div>
                {script.title && (
                  <div className="mb-3 text-sm font-medium text-indigo-600 bg-indigo-50 px-3 py-2 rounded-lg">
                    {script.title}
                  </div>
                )}
                <div className="bg-gradient-to-br from-indigo-50/50 via-purple-50/50 to-cyan-50/50 rounded-xl p-4 max-h-[300px] overflow-y-auto border border-indigo-100">
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
                    {script.script}
                  </pre>
                </div>

                {/* 音声プレビューセクション */}
                <div className="mt-4 p-4 glass rounded-lg">
                  <div className="flex items-center gap-3 mb-3">
                    <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    </svg>
                    <span className="text-sm font-medium text-gray-700">音声プレビュー</span>
                  </div>

                  <button
                    onClick={handleGenerateAudio}
                    disabled={generatingAudio}
                    className="w-full btn-iris py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {generatingAudio ? (
                      <>
                        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        音声生成中...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        音声を生成
                      </>
                    )}
                  </button>

                  {audioError && (
                    <div className="mt-3 flex items-center gap-2 text-red-600 text-sm">
                      <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      {audioError}
                    </div>
                  )}

                  {audioUrl && (
                    <div className="mt-3">
                      <audio controls className="w-full" src={audioUrl}>
                        お使いのブラウザは音声再生に対応していません。
                      </audio>
                    </div>
                  )}
                </div>

                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() => navigator.clipboard.writeText(script.script)}
                    className="btn-iris-outline flex-1 flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                    </svg>
                    コピー
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-[300px] text-gray-400">
                <div className="w-20 h-20 rounded-full overflow-hidden ring-2 ring-gray-200 ring-offset-2 mb-4 opacity-50">
                  <Image
                    src="/images/iris/iris-normal.png"
                    alt="イリス"
                    width={80}
                    height={80}
                    className="object-cover"
                  />
                </div>
                <p className="text-center">
                  「台本タイプを選んで<br />生成ボタンを押してみてください」
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 使い方説明 */}
      <div className="mt-8 glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">使い方</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[
            { step: "1", title: "台本タイプを選択", desc: "7種類の台本タイプから選びます" },
            { step: "2", title: "必要情報を入力", desc: "銘柄コードやテーマなどを入力します" },
            { step: "3", title: "台本を生成", desc: "ボタンを押すとAIが台本を作成します" },
            { step: "4", title: "コピーして使用", desc: "生成された台本をコピーしてご利用ください" },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center text-white font-bold flex-shrink-0">
                {item.step}
              </div>
              <div>
                <h3 className="font-bold text-gray-900">{item.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
