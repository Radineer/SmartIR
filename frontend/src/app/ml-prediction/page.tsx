"use client";

import { useState, useCallback } from "react";
import Image from "next/image";
import { api } from "@/lib/api";
import type {
  MLPrediction,
  FeatureImportance,
  ModelEvaluation,
  IrisMLComment,
} from "@/types";

// 予測履歴の型
interface PredictionHistory {
  ticker: string;
  prediction: MLPrediction;
  timestamp: Date;
}

// 方向性アイコン
const DirectionIcon = ({ direction }: { direction: "up" | "down" | "neutral" }) => {
  switch (direction) {
    case "up":
      return (
        <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      );
    case "down":
      return (
        <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6" />
        </svg>
      );
    default:
      return (
        <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14" />
        </svg>
      );
  }
};

// 信頼度バッジ
const ConfidenceBadge = ({ confidence }: { confidence: number }) => {
  const getColor = () => {
    if (confidence >= 0.8) return "bg-green-100 text-green-800 border-green-300";
    if (confidence >= 0.6) return "bg-yellow-100 text-yellow-800 border-yellow-300";
    return "bg-red-100 text-red-800 border-red-300";
  };

  const getLabel = () => {
    if (confidence >= 0.8) return "高信頼度";
    if (confidence >= 0.6) return "中信頼度";
    return "低信頼度";
  };

  return (
    <span className={`px-3 py-1 text-sm font-medium rounded-full border ${getColor()}`}>
      {getLabel()}: {(confidence * 100).toFixed(1)}%
    </span>
  );
};

// 棒グラフコンポーネント
const BarChart = ({ features }: { features: FeatureImportance["features"] }) => {
  const maxImportance = Math.max(...features.map((f) => f.importance));

  return (
    <div className="space-y-3">
      {features.map((feature, index) => (
        <div key={index} className="group">
          <div className="flex justify-between items-center mb-1">
            <span className="text-sm font-medium text-gray-700 truncate max-w-[200px]" title={feature.name}>
              {feature.name}
            </span>
            <span className="text-sm text-gray-500">
              {(feature.importance * 100).toFixed(1)}%
            </span>
          </div>
          <div className="sentiment-bar">
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{
                width: `${(feature.importance / maxImportance) * 100}%`,
                background: `linear-gradient(90deg, #6366F1 0%, #22D3EE ${(feature.importance / maxImportance) * 100}%)`,
              }}
            />
          </div>
          {feature.description && (
            <p className="text-xs text-gray-500 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {feature.description}
            </p>
          )}
        </div>
      ))}
    </div>
  );
};

// メトリクスカード
const MetricCard = ({ label, value, format = "percent" }: { label: string; value: number; format?: "percent" | "number" }) => {
  const displayValue = format === "percent" ? `${(value * 100).toFixed(1)}%` : value.toLocaleString();
  const getColor = () => {
    if (format !== "percent") return "text-indigo-600";
    if (value >= 0.8) return "text-green-600";
    if (value >= 0.6) return "text-yellow-600";
    return "text-red-600";
  };

  return (
    <div className="glass rounded-xl p-4 text-center">
      <div className={`text-2xl font-bold ${getColor()}`}>{displayValue}</div>
      <div className="text-sm text-gray-600 mt-1">{label}</div>
    </div>
  );
};

export default function MLPredictionPage() {
  // 単一予測用
  const [ticker, setTicker] = useState("");
  const [prediction, setPrediction] = useState<MLPrediction | null>(null);
  const [features, setFeatures] = useState<FeatureImportance | null>(null);
  const [evaluation, setEvaluation] = useState<ModelEvaluation | null>(null);
  const [irisComment, setIrisComment] = useState<IrisMLComment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 一括予測用
  const [batchTickers, setBatchTickers] = useState("");
  const [batchPredictions, setBatchPredictions] = useState<MLPrediction[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState("");

  // 予測履歴
  const [history, setHistory] = useState<PredictionHistory[]>([]);

  // タブ状態
  const [activeTab, setActiveTab] = useState<"single" | "batch">("single");

  // 単一銘柄の予測を取得
  const handlePredict = useCallback(async () => {
    if (!ticker.trim()) {
      setError("銘柄コードを入力してください");
      return;
    }

    const normalizedTicker = ticker.trim().toUpperCase();
    setLoading(true);
    setError("");
    setPrediction(null);
    setFeatures(null);
    setEvaluation(null);
    setIrisComment(null);

    try {
      // すべてのAPI呼び出しを並列で実行
      const [predResult, featResult, evalResult, commentResult] = await Promise.allSettled([
        api.getMLPrediction(normalizedTicker),
        api.getFeatureImportance(normalizedTicker),
        api.getModelEvaluation(normalizedTicker),
        api.getIrisMLComment(normalizedTicker),
      ]);

      if (predResult.status === "fulfilled") {
        setPrediction(predResult.value);
        // 履歴に追加
        setHistory((prev) => [
          { ticker: normalizedTicker, prediction: predResult.value, timestamp: new Date() },
          ...prev.slice(0, 9), // 最大10件
        ]);
      } else {
        throw new Error(predResult.reason?.message || "予測の取得に失敗しました");
      }

      if (featResult.status === "fulfilled") {
        setFeatures(featResult.value);
      }

      if (evalResult.status === "fulfilled") {
        setEvaluation(evalResult.value);
      }

      if (commentResult.status === "fulfilled") {
        setIrisComment(commentResult.value);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "予測の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  // 一括予測を取得
  const handleBatchPredict = useCallback(async () => {
    if (!batchTickers.trim()) {
      setBatchError("銘柄コードを入力してください");
      return;
    }

    const tickerList = batchTickers
      .split(/[,\s\n]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    if (tickerList.length === 0) {
      setBatchError("有効な銘柄コードを入力してください");
      return;
    }

    if (tickerList.length > 20) {
      setBatchError("一度に予測できるのは20銘柄までです");
      return;
    }

    setBatchLoading(true);
    setBatchError("");
    setBatchPredictions([]);

    try {
      const result = await api.getMLBatchPrediction(tickerList);
      setBatchPredictions(result.predictions);
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : "一括予測の取得に失敗しました");
    } finally {
      setBatchLoading(false);
    }
  }, [batchTickers]);

  // 履歴から予測を再表示
  const handleHistoryClick = (item: PredictionHistory) => {
    setTicker(item.ticker);
    setPrediction(item.prediction);
    setActiveTab("single");
  };

  // 方向性の表示テキスト
  const getDirectionText = (direction: "up" | "down" | "neutral") => {
    switch (direction) {
      case "up":
        return "上昇";
      case "down":
        return "下落";
      default:
        return "中立";
    }
  };

  // 方向性の色クラス
  const getDirectionColor = (direction: "up" | "down" | "neutral") => {
    switch (direction) {
      case "up":
        return "text-green-600";
      case "down":
        return "text-red-600";
      default:
        return "text-gray-600";
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* ヘッダー */}
      <div className="glass rounded-2xl p-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex-shrink-0">
            <div className="relative w-16 h-16 rounded-full overflow-hidden ring-2 ring-indigo-200 ring-offset-2">
              <Image
                src="/images/iris/iris-analysis.png"
                alt="イリス"
                width={64}
                height={64}
                className="object-cover"
              />
            </div>
          </div>
          <div className="flex-1">
            <h1 className="section-title text-2xl md:text-3xl">ML予測ダッシュボード</h1>
            <p className="text-gray-600 mt-3">
              「機械学習モデルを使って株価の動向を予測します。データは嘘をつきませんから...でも、投資判断は自己責任でお願いしますね。」
            </p>
          </div>
        </div>
      </div>

      {/* タブ切り替え */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab("single")}
          className={`px-6 py-3 rounded-xl font-medium transition-all ${
            activeTab === "single"
              ? "bg-indigo-500 text-white shadow-lg shadow-indigo-200"
              : "bg-white text-gray-600 hover:bg-gray-50 border border-gray-200"
          }`}
        >
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            単一銘柄予測
          </div>
        </button>
        <button
          onClick={() => setActiveTab("batch")}
          className={`px-6 py-3 rounded-xl font-medium transition-all ${
            activeTab === "batch"
              ? "bg-indigo-500 text-white shadow-lg shadow-indigo-200"
              : "bg-white text-gray-600 hover:bg-gray-50 border border-gray-200"
          }`}
        >
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            一括予測
          </div>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 左: 入力フォームと履歴 */}
        <div className="space-y-6">
          {/* 入力フォーム */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              {activeTab === "single" ? "銘柄コード入力" : "一括予測入力"}
            </h2>

            {activeTab === "single" ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">銘柄コード</label>
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handlePredict()}
                    placeholder="例: 7203.T"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={handlePredict}
                  disabled={loading || !ticker.trim()}
                  className="w-full btn-iris py-3 text-base font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      予測中...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      予測を実行
                    </>
                  )}
                </button>
                {error && (
                  <div className="flex items-center gap-3 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-200">
                    <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {error}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    銘柄コード（複数入力可、カンマ・スペース・改行区切り）
                  </label>
                  <textarea
                    value={batchTickers}
                    onChange={(e) => setBatchTickers(e.target.value)}
                    placeholder="例:&#10;7203.T&#10;6758.T&#10;9984.T"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                    rows={5}
                  />
                  <p className="text-xs text-gray-500 mt-1">最大20銘柄まで一度に予測できます</p>
                </div>
                <button
                  onClick={handleBatchPredict}
                  disabled={batchLoading || !batchTickers.trim()}
                  className="w-full btn-iris py-3 text-base font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {batchLoading ? (
                    <>
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      一括予測中...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                      </svg>
                      一括予測を実行
                    </>
                  )}
                </button>
                {batchError && (
                  <div className="flex items-center gap-3 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-200">
                    <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {batchError}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 予測履歴 */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              予測履歴
            </h2>
            {history.length > 0 ? (
              <div className="space-y-2">
                {history.map((item, index) => (
                  <button
                    key={index}
                    onClick={() => handleHistoryClick(item)}
                    className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-50 hover:bg-indigo-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <DirectionIcon direction={item.prediction.direction} />
                      <div>
                        <span className="font-medium text-gray-900">{item.ticker}</span>
                        <span className={`ml-2 text-sm ${getDirectionColor(item.prediction.direction)}`}>
                          {getDirectionText(item.prediction.direction)}
                        </span>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">
                      {item.timestamp.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm text-center py-4">まだ履歴がありません</p>
            )}
          </div>
        </div>

        {/* 右: 結果表示 */}
        <div className="lg:col-span-2 space-y-6">
          {activeTab === "single" ? (
            <>
              {/* 予測結果 */}
              <div className="holo-card p-6">
                <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  予測結果
                </h2>

                {prediction ? (
                  <div className="space-y-6">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-6 glass rounded-xl">
                      <div className="flex items-center gap-4">
                        <div className={`w-16 h-16 rounded-full flex items-center justify-center ${
                          prediction.direction === "up" ? "bg-green-100" :
                          prediction.direction === "down" ? "bg-red-100" : "bg-gray-100"
                        }`}>
                          <DirectionIcon direction={prediction.direction} />
                        </div>
                        <div>
                          <div className="text-sm text-gray-500">銘柄</div>
                          <div className="text-2xl font-bold text-gray-900">{prediction.ticker}</div>
                        </div>
                      </div>
                      <div className="text-center sm:text-right">
                        <div className={`text-3xl font-bold ${getDirectionColor(prediction.direction)}`}>
                          {getDirectionText(prediction.direction)}
                        </div>
                        <div className="text-lg text-gray-600">
                          確率: {(prediction.probability * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-3 justify-center">
                      <ConfidenceBadge confidence={prediction.confidence} />
                      {prediction.model_version && (
                        <span className="iris-badge">モデル: {prediction.model_version}</span>
                      )}
                      <span className="iris-badge">
                        予測日時: {new Date(prediction.predicted_at).toLocaleString("ja-JP")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-[200px] text-gray-400">
                    <svg className="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    <p>銘柄コードを入力して予測を実行してください</p>
                  </div>
                )}
              </div>

              {/* イリスのコメント */}
              {irisComment && (
                <div className="holo-card p-6">
                  <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full overflow-hidden ring-2 ring-indigo-200">
                      <Image
                        src="/images/iris/iris-normal.png"
                        alt="イリス"
                        width={32}
                        height={32}
                        className="object-cover"
                      />
                    </div>
                    イリスのコメント
                  </h2>
                  <div className="bg-gradient-to-br from-indigo-50/50 via-purple-50/50 to-cyan-50/50 rounded-xl p-4 border border-indigo-100">
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0">
                        <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                          irisComment.sentiment === "bullish" ? "bg-green-100 text-green-800" :
                          irisComment.sentiment === "bearish" ? "bg-red-100 text-red-800" :
                          "bg-gray-100 text-gray-800"
                        }`}>
                          {irisComment.sentiment === "bullish" ? "強気" :
                           irisComment.sentiment === "bearish" ? "弱気" : "中立"}
                        </div>
                      </div>
                      <p className="text-gray-700 leading-relaxed">{irisComment.comment}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* 特徴量重要度 */}
              {features && features.features.length > 0 && (
                <div className="holo-card p-6">
                  <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                    </svg>
                    特徴量重要度
                  </h2>
                  <BarChart features={features.features} />
                  <p className="text-xs text-gray-500 mt-4 text-center">
                    算出日時: {new Date(features.computed_at).toLocaleString("ja-JP")}
                  </p>
                </div>
              )}

              {/* モデル評価メトリクス */}
              {evaluation && (
                <div className="holo-card p-6">
                  <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    モデル評価メトリクス
                  </h2>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <MetricCard label="正解率" value={evaluation.accuracy} />
                    <MetricCard label="適合率" value={evaluation.precision} />
                    <MetricCard label="再現率" value={evaluation.recall} />
                    <MetricCard label="F1スコア" value={evaluation.f1_score} />
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-4">
                    <MetricCard label="学習サンプル数" value={evaluation.training_samples} format="number" />
                    <MetricCard label="テストサンプル数" value={evaluation.test_samples} format="number" />
                  </div>
                  <p className="text-xs text-gray-500 mt-4 text-center">
                    最終学習: {new Date(evaluation.last_trained).toLocaleString("ja-JP")}
                    {evaluation.model_version && ` | モデル: ${evaluation.model_version}`}
                  </p>
                </div>
              )}
            </>
          ) : (
            /* 一括予測結果 */
            <div className="holo-card p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                一括予測結果
              </h2>

              {batchPredictions.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">銘柄</th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-gray-500">予測</th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-gray-500">確率</th>
                        <th className="px-4 py-3 text-center text-sm font-medium text-gray-500">信頼度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchPredictions.map((pred, index) => (
                        <tr
                          key={index}
                          className="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                          onClick={() => {
                            setTicker(pred.ticker);
                            setPrediction(pred);
                            setActiveTab("single");
                          }}
                        >
                          <td className="px-4 py-3">
                            <span className="font-medium text-gray-900">{pred.ticker}</span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-2">
                              <DirectionIcon direction={pred.direction} />
                              <span className={`font-medium ${getDirectionColor(pred.direction)}`}>
                                {getDirectionText(pred.direction)}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="text-gray-700">{(pred.probability * 100).toFixed(1)}%</span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <ConfidenceBadge confidence={pred.confidence} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-[300px] text-gray-400">
                  <svg className="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                  </svg>
                  <p>複数の銘柄コードを入力して一括予測を実行してください</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 注意事項 */}
      <div className="mt-8 glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          ご注意
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <span className="text-amber-600 font-bold">1</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-900">投資助言ではありません</h3>
              <p className="text-sm text-gray-600 mt-1">
                本予測は機械学習モデルによる参考情報であり、投資助言ではありません。
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <span className="text-amber-600 font-bold">2</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-900">過去の実績は将来を保証しません</h3>
              <p className="text-sm text-gray-600 mt-1">
                モデルの精度は市場環境により変動します。過去の結果が将来を保証するものではありません。
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <span className="text-amber-600 font-bold">3</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-900">自己責任でご利用ください</h3>
              <p className="text-sm text-gray-600 mt-1">
                投資判断は自己責任で行ってください。損失について当サービスは責任を負いません。
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <span className="text-amber-600 font-bold">4</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-900">信頼度を確認してください</h3>
              <p className="text-sm text-gray-600 mt-1">
                予測の信頼度が低い場合は、特に慎重に判断してください。
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
