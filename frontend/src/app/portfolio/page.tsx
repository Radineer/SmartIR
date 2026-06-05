"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import { api } from "@/lib/api";
import type {
  PortfolioAnalysisPosition,
  PortfolioAnalysisResult,
  VaRResult,
  CorrelationResult,
  RebalanceMethod,
  RebalanceResult,
  EfficientFrontierResult,
  RiskDecompositionResult,
} from "@/types";

// 入力用ポジションの型
interface PositionInput {
  id: string;
  ticker_code: string;
  quantity: string;
  avg_price: string;
}

// 分析タブの定義
type AnalysisTab = "overview" | "var" | "correlation" | "rebalance" | "frontier" | "risk";

// リバランス方式の定義
const REBALANCE_METHODS: { id: RebalanceMethod; name: string; description: string }[] = [
  { id: "equal_weight", name: "均等配分", description: "すべての銘柄を同じウェイトに調整" },
  { id: "min_variance", name: "最小分散", description: "ポートフォリオ全体のリスクを最小化" },
  { id: "risk_parity", name: "リスクパリティ", description: "リスク寄与度を均等化" },
  { id: "max_sharpe", name: "最大シャープ", description: "リスク調整後リターンを最大化" },
];

// サンプルポジション
const SAMPLE_POSITIONS: PositionInput[] = [
  { id: "1", ticker_code: "7203.T", quantity: "100", avg_price: "2500" },
  { id: "2", ticker_code: "6758.T", quantity: "50", avg_price: "13000" },
  { id: "3", ticker_code: "9984.T", quantity: "30", avg_price: "8000" },
];

// カラーパレット（セクター配分チャート用）
const SECTOR_COLORS = [
  "#6366F1", "#22D3EE", "#F0ABFC", "#34D399", "#FBBF24",
  "#F87171", "#A78BFA", "#60A5FA", "#F472B6", "#4ADE80",
];

export default function PortfolioPage() {
  // ポジション入力
  const [positions, setPositions] = useState<PositionInput[]>([
    { id: crypto.randomUUID(), ticker_code: "", quantity: "", avg_price: "" },
  ]);

  // 分析結果
  const [analysisResult, setAnalysisResult] = useState<PortfolioAnalysisResult | null>(null);
  const [varResult, setVarResult] = useState<VaRResult | null>(null);
  const [correlationResult, setCorrelationResult] = useState<CorrelationResult | null>(null);
  const [rebalanceResult, setRebalanceResult] = useState<RebalanceResult | null>(null);
  const [frontierResult, setFrontierResult] = useState<EfficientFrontierResult | null>(null);
  const [riskResult, setRiskResult] = useState<RiskDecompositionResult | null>(null);

  // UI状態
  const [activeTab, setActiveTab] = useState<AnalysisTab>("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedRebalanceMethod, setSelectedRebalanceMethod] = useState<RebalanceMethod>("equal_weight");

  // VaR設定
  const [varConfidence, setVarConfidence] = useState(95);
  const [varHorizon, setVarHorizon] = useState(1);
  const [varMethod, setVarMethod] = useState<"historical" | "parametric" | "monte_carlo">("parametric");

  // ポジション追加
  const addPosition = () => {
    setPositions([
      ...positions,
      { id: crypto.randomUUID(), ticker_code: "", quantity: "", avg_price: "" },
    ]);
  };

  // ポジション削除
  const removePosition = (id: string) => {
    if (positions.length > 1) {
      setPositions(positions.filter((p) => p.id !== id));
    }
  };

  // ポジション更新
  const updatePosition = (id: string, field: keyof PositionInput, value: string) => {
    setPositions(
      positions.map((p) => (p.id === id ? { ...p, [field]: value } : p))
    );
  };

  // サンプルデータ読み込み
  const loadSampleData = () => {
    setPositions(SAMPLE_POSITIONS.map((p) => ({ ...p, id: crypto.randomUUID() })));
  };

  // 有効なポジションを取得
  const validPositions = useMemo(() => {
    return positions
      .filter((p) => p.ticker_code && p.quantity && p.avg_price)
      .map((p) => ({
        ticker_code: p.ticker_code.toUpperCase(),
        quantity: Number(p.quantity),
        avg_price: Number(p.avg_price),
      }));
  }, [positions]);

  // 分析実行
  const runAnalysis = async () => {
    if (validPositions.length === 0) {
      setError("有効なポジションを入力してください");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await api.analyzePortfolio(validPositions);
      setAnalysisResult(result);
      setActiveTab("overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  // VaR計算
  const calculateVaR = async () => {
    if (validPositions.length === 0) return;

    setLoading(true);
    setError("");

    try {
      const result = await api.calculateVaR(
        validPositions,
        varConfidence / 100,
        varHorizon,
        varMethod
      );
      setVarResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "VaR計算に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  // 相関分析
  const analyzeCorrelation = async () => {
    if (validPositions.length < 2) {
      setError("相関分析には2銘柄以上必要です");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await api.getCorrelation(validPositions);
      setCorrelationResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "相関分析に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  // リバランス提案
  const getRebalance = async () => {
    if (validPositions.length === 0) return;

    setLoading(true);
    setError("");

    try {
      const result = await api.getRebalanceSuggestion(validPositions, selectedRebalanceMethod);
      setRebalanceResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "リバランス提案の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  // 効率的フロンティア計算
  const calculateFrontier = async () => {
    if (validPositions.length < 2) {
      setError("効率的フロンティアには2銘柄以上必要です");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await api.getEfficientFrontier(validPositions);
      setFrontierResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "効率的フロンティア計算に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  // リスク分解分析
  const analyzeRisk = async () => {
    if (validPositions.length === 0) return;

    setLoading(true);
    setError("");

    try {
      const result = await api.getRiskDecomposition(validPositions);
      setRiskResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "リスク分解分析に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  // タブ変更時に対応する分析を実行
  const handleTabChange = (tab: AnalysisTab) => {
    setActiveTab(tab);
    if (validPositions.length === 0) return;

    switch (tab) {
      case "var":
        if (!varResult) calculateVaR();
        break;
      case "correlation":
        if (!correlationResult) analyzeCorrelation();
        break;
      case "rebalance":
        if (!rebalanceResult) getRebalance();
        break;
      case "frontier":
        if (!frontierResult) calculateFrontier();
        break;
      case "risk":
        if (!riskResult) analyzeRisk();
        break;
    }
  };

  // 数値フォーマット
  const formatNumber = (num: number, decimals = 0) => {
    return num.toLocaleString("ja-JP", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  const formatPercent = (num: number, decimals = 2) => {
    return `${num >= 0 ? "+" : ""}${num.toFixed(decimals)}%`;
  };

  const formatCurrency = (num: number) => {
    return `¥${formatNumber(num)}`;
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
            <h1 className="section-title text-2xl md:text-3xl">ポートフォリオ分析</h1>
            <p className="text-gray-600 mt-3">
              「保有銘柄を入力すると、総合的なポートフォリオ分析を行います。リスク指標、相関関係、最適化提案などを確認できます。」
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 左: ポジション入力フォーム */}
        <div className="lg:col-span-1 space-y-6">
          <div className="holo-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                ポジション入力
              </h2>
              <button
                onClick={loadSampleData}
                className="text-xs text-indigo-600 hover:text-indigo-800 underline"
              >
                サンプル読込
              </button>
            </div>

            <div className="space-y-4">
              {positions.map((position, index) => (
                <div key={position.id} className="p-4 bg-gray-50 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-600">銘柄 {index + 1}</span>
                    {positions.length > 1 && (
                      <button
                        onClick={() => removePosition(position.id)}
                        className="text-red-500 hover:text-red-700 p-1"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    placeholder="銘柄コード (例: 7203.T)"
                    value={position.ticker_code}
                    onChange={(e) => updatePosition(position.id, "ticker_code", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="number"
                      placeholder="保有株数"
                      value={position.quantity}
                      onChange={(e) => updatePosition(position.id, "quantity", e.target.value)}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                    />
                    <input
                      type="number"
                      placeholder="取得価格"
                      value={position.avg_price}
                      onChange={(e) => updatePosition(position.id, "avg_price", e.target.value)}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                    />
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={addPosition}
              className="w-full mt-4 py-2 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              銘柄を追加
            </button>

            <button
              onClick={runAnalysis}
              disabled={loading || validPositions.length === 0}
              className="w-full mt-4 btn-iris py-3 text-base font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  分析中...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  分析を実行
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

          {/* 入力済み銘柄サマリー */}
          {validPositions.length > 0 && (
            <div className="holo-card p-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">入力済み: {validPositions.length}銘柄</h3>
              <div className="space-y-2">
                {validPositions.map((p) => (
                  <div key={p.ticker_code} className="flex items-center justify-between text-sm">
                    <span className="font-mono text-indigo-600">{p.ticker_code}</span>
                    <span className="text-gray-500">
                      {p.quantity}株 @ {formatCurrency(p.avg_price)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 右: 分析結果 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 分析タブ */}
          <div className="holo-card p-2">
            <div className="flex overflow-x-auto gap-1">
              {[
                { id: "overview" as AnalysisTab, name: "概要", icon: "chart-bar" },
                { id: "var" as AnalysisTab, name: "VaR", icon: "shield" },
                { id: "correlation" as AnalysisTab, name: "相関", icon: "link" },
                { id: "rebalance" as AnalysisTab, name: "リバランス", icon: "refresh" },
                { id: "frontier" as AnalysisTab, name: "効率フロンティア", icon: "trending-up" },
                { id: "risk" as AnalysisTab, name: "リスク分解", icon: "pie-chart" },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  disabled={!analysisResult && tab.id !== "overview"}
                  className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === tab.id
                      ? "bg-indigo-500 text-white"
                      : "text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  }`}
                >
                  {tab.name}
                </button>
              ))}
            </div>
          </div>

          {/* 概要タブ */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {analysisResult ? (
                <>
                  {/* サマリーカード */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="holo-card p-4">
                      <p className="text-sm text-gray-500">総資産価値</p>
                      <p className="text-xl font-bold text-gray-900">{formatCurrency(analysisResult.total_value)}</p>
                    </div>
                    <div className="holo-card p-4">
                      <p className="text-sm text-gray-500">含み損益</p>
                      <p className={`text-xl font-bold ${analysisResult.total_unrealized_pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {formatCurrency(analysisResult.total_unrealized_pnl)}
                      </p>
                      <p className={`text-sm ${analysisResult.total_unrealized_pnl_percent >= 0 ? "text-green-500" : "text-red-500"}`}>
                        {formatPercent(analysisResult.total_unrealized_pnl_percent)}
                      </p>
                    </div>
                    <div className="holo-card p-4">
                      <p className="text-sm text-gray-500">ボラティリティ</p>
                      <p className="text-xl font-bold text-gray-900">
                        {analysisResult.volatility ? `${(analysisResult.volatility * 100).toFixed(2)}%` : "-"}
                      </p>
                    </div>
                    <div className="holo-card p-4">
                      <p className="text-sm text-gray-500">シャープレシオ</p>
                      <p className="text-xl font-bold text-indigo-600">
                        {analysisResult.sharpe_ratio?.toFixed(2) || "-"}
                      </p>
                    </div>
                  </div>

                  {/* ポジション一覧 */}
                  <div className="holo-card p-6">
                    <h3 className="text-lg font-bold text-gray-900 mb-4">ポジション詳細</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200">
                            <th className="text-left py-3 px-2">銘柄</th>
                            <th className="text-right py-3 px-2">現在価格</th>
                            <th className="text-right py-3 px-2">評価額</th>
                            <th className="text-right py-3 px-2">ウェイト</th>
                            <th className="text-right py-3 px-2">損益</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analysisResult.positions.map((pos) => (
                            <tr key={pos.ticker_code} className="border-b border-gray-100 hover:bg-gray-50">
                              <td className="py-3 px-2">
                                <span className="font-mono text-indigo-600">{pos.ticker_code}</span>
                                {pos.name && <span className="ml-2 text-gray-500">{pos.name}</span>}
                              </td>
                              <td className="text-right py-3 px-2">{formatCurrency(pos.current_price)}</td>
                              <td className="text-right py-3 px-2">{formatCurrency(pos.market_value)}</td>
                              <td className="text-right py-3 px-2">{(pos.weight * 100).toFixed(1)}%</td>
                              <td className={`text-right py-3 px-2 ${pos.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                                {formatPercent(pos.unrealized_pnl_percent)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* セクター配分チャート */}
                  {analysisResult.sector_allocation.length > 0 && (
                    <div className="holo-card p-6">
                      <h3 className="text-lg font-bold text-gray-900 mb-4">セクター配分</h3>
                      <div className="flex flex-col md:flex-row items-center gap-8">
                        {/* 円グラフ風の表示 */}
                        <div className="relative w-48 h-48">
                          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                            {(() => {
                              let cumulativePercent = 0;
                              return analysisResult.sector_allocation.map((sector, index) => {
                                const percent = sector.weight * 100;
                                const dashArray = `${percent} ${100 - percent}`;
                                const dashOffset = -cumulativePercent;
                                cumulativePercent += percent;
                                return (
                                  <circle
                                    key={sector.sector}
                                    cx="50"
                                    cy="50"
                                    r="40"
                                    fill="none"
                                    stroke={SECTOR_COLORS[index % SECTOR_COLORS.length]}
                                    strokeWidth="20"
                                    strokeDasharray={dashArray}
                                    strokeDashoffset={dashOffset}
                                    className="transition-all duration-500"
                                  />
                                );
                              });
                            })()}
                          </svg>
                        </div>
                        {/* 凡例 */}
                        <div className="flex-1 grid grid-cols-2 gap-3">
                          {analysisResult.sector_allocation.map((sector, index) => (
                            <div key={sector.sector} className="flex items-center gap-2">
                              <div
                                className="w-3 h-3 rounded-full flex-shrink-0"
                                style={{ backgroundColor: SECTOR_COLORS[index % SECTOR_COLORS.length] }}
                              />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">{sector.sector}</p>
                                <p className="text-xs text-gray-500">{(sector.weight * 100).toFixed(1)}%</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="holo-card p-12 text-center">
                  <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-indigo-100 flex items-center justify-center">
                    <svg className="w-10 h-10 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">ポートフォリオを分析</h3>
                  <p className="text-gray-500">左側のフォームに保有銘柄を入力して分析を実行してください</p>
                </div>
              )}
            </div>
          )}

          {/* VaRタブ */}
          {activeTab === "var" && (
            <div className="space-y-6">
              <div className="holo-card p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">VaR設定</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      信頼水準: {varConfidence}%
                    </label>
                    <input
                      type="range"
                      min="90"
                      max="99"
                      value={varConfidence}
                      onChange={(e) => setVarConfidence(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">保有期間（日）</label>
                    <select
                      value={varHorizon}
                      onChange={(e) => setVarHorizon(Number(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                    >
                      <option value={1}>1日</option>
                      <option value={5}>5日</option>
                      <option value={10}>10日</option>
                      <option value={20}>20日</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">計算方式</label>
                    <select
                      value={varMethod}
                      onChange={(e) => setVarMethod(e.target.value as typeof varMethod)}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                    >
                      <option value="parametric">パラメトリック法</option>
                      <option value="historical">ヒストリカル法</option>
                      <option value="monte_carlo">モンテカルロ法</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={calculateVaR}
                  disabled={loading}
                  className="mt-4 btn-iris py-2 px-6"
                >
                  VaRを計算
                </button>
              </div>

              {varResult && (
                <div className="holo-card p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">VaR計算結果</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-red-50 rounded-xl p-4">
                      <p className="text-sm text-red-600">VaR（{varResult.confidence_level * 100}%）</p>
                      <p className="text-2xl font-bold text-red-700">{formatCurrency(varResult.var_value)}</p>
                      <p className="text-sm text-red-500">{formatPercent(-varResult.var_percent)}</p>
                    </div>
                    {varResult.expected_shortfall && (
                      <div className="bg-orange-50 rounded-xl p-4">
                        <p className="text-sm text-orange-600">期待ショートフォール</p>
                        <p className="text-2xl font-bold text-orange-700">{formatCurrency(varResult.expected_shortfall)}</p>
                      </div>
                    )}
                    <div className="bg-gray-50 rounded-xl p-4">
                      <p className="text-sm text-gray-600">保有期間</p>
                      <p className="text-2xl font-bold text-gray-900">{varResult.time_horizon}日</p>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-4">
                      <p className="text-sm text-gray-600">計算方式</p>
                      <p className="text-lg font-bold text-gray-900">{varResult.method}</p>
                    </div>
                  </div>
                  <div className="mt-4 p-4 bg-indigo-50 rounded-lg">
                    <p className="text-sm text-indigo-700">
                      <strong>解釈:</strong> {varResult.confidence_level * 100}%の確率で、{varResult.time_horizon}日間の損失は{formatCurrency(varResult.var_value)}以内に収まります。
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 相関タブ */}
          {activeTab === "correlation" && (
            <div className="space-y-6">
              <div className="holo-card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900">相関マトリックス</h3>
                  <button
                    onClick={analyzeCorrelation}
                    disabled={loading}
                    className="btn-iris py-2 px-4 text-sm"
                  >
                    再計算
                  </button>
                </div>

                {correlationResult && (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr>
                            <th className="py-2 px-3"></th>
                            {correlationResult.tickers.map((ticker) => (
                              <th key={ticker} className="py-2 px-3 text-center font-mono text-indigo-600">
                                {ticker}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {correlationResult.tickers.map((ticker1, i) => (
                            <tr key={ticker1}>
                              <td className="py-2 px-3 font-mono text-indigo-600">{ticker1}</td>
                              {correlationResult.correlation_matrix[i].map((corr, j) => {
                                const absCorr = Math.abs(corr);
                                const bgColor = i === j
                                  ? "bg-gray-100"
                                  : corr > 0.7
                                  ? "bg-red-100"
                                  : corr > 0.3
                                  ? "bg-yellow-100"
                                  : corr < -0.3
                                  ? "bg-green-100"
                                  : "bg-gray-50";
                                return (
                                  <td
                                    key={j}
                                    className={`py-2 px-3 text-center ${bgColor}`}
                                  >
                                    {corr.toFixed(2)}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {correlationResult.highly_correlated_pairs.length > 0 && (
                      <div className="mt-6">
                        <h4 className="font-medium text-gray-900 mb-3">高相関ペア</h4>
                        <div className="space-y-2">
                          {correlationResult.highly_correlated_pairs.map((pair, index) => (
                            <div key={index} className="flex items-center gap-3 p-3 bg-red-50 rounded-lg">
                              <span className="font-mono text-red-700">{pair.ticker1}</span>
                              <span className="text-gray-400">-</span>
                              <span className="font-mono text-red-700">{pair.ticker2}</span>
                              <span className="ml-auto text-red-600 font-medium">
                                相関: {pair.correlation.toFixed(2)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="mt-4 p-4 bg-indigo-50 rounded-lg">
                      <p className="text-sm text-indigo-700">
                        <strong>ヒント:</strong> 相関係数が0.7を超えるペアは分散効果が低くなります。異なるセクターの銘柄を組み合わせることで、ポートフォリオのリスクを低減できます。
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* リバランスタブ */}
          {activeTab === "rebalance" && (
            <div className="space-y-6">
              <div className="holo-card p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">リバランス方式を選択</h3>
                <div className="grid grid-cols-2 gap-3">
                  {REBALANCE_METHODS.map((method) => (
                    <button
                      key={method.id}
                      onClick={() => setSelectedRebalanceMethod(method.id)}
                      className={`p-4 rounded-xl border-2 text-left transition-all ${
                        selectedRebalanceMethod === method.id
                          ? "border-indigo-500 bg-indigo-50"
                          : "border-gray-200 hover:border-indigo-300"
                      }`}
                    >
                      <p className="font-medium text-gray-900">{method.name}</p>
                      <p className="text-sm text-gray-500 mt-1">{method.description}</p>
                    </button>
                  ))}
                </div>
                <button
                  onClick={getRebalance}
                  disabled={loading}
                  className="mt-4 btn-iris py-2 px-6"
                >
                  提案を取得
                </button>
              </div>

              {rebalanceResult && (
                <div className="holo-card p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">
                    リバランス提案（{REBALANCE_METHODS.find((m) => m.id === selectedRebalanceMethod)?.name}）
                  </h3>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="text-left py-3 px-2">銘柄</th>
                          <th className="text-right py-3 px-2">現在</th>
                          <th className="text-right py-3 px-2">目標</th>
                          <th className="text-right py-3 px-2">変動</th>
                          <th className="text-center py-3 px-2">アクション</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rebalanceResult.suggestions.map((suggestion) => (
                          <tr key={suggestion.ticker_code} className="border-b border-gray-100">
                            <td className="py-3 px-2 font-mono text-indigo-600">{suggestion.ticker_code}</td>
                            <td className="text-right py-3 px-2">{(suggestion.current_weight * 100).toFixed(1)}%</td>
                            <td className="text-right py-3 px-2">{(suggestion.target_weight * 100).toFixed(1)}%</td>
                            <td className={`text-right py-3 px-2 ${
                              suggestion.weight_change > 0 ? "text-green-600" : suggestion.weight_change < 0 ? "text-red-600" : "text-gray-500"
                            }`}>
                              {suggestion.weight_change > 0 ? "+" : ""}{(suggestion.weight_change * 100).toFixed(1)}%
                            </td>
                            <td className="text-center py-3 px-2">
                              <span className={`px-2 py-1 rounded text-xs font-medium ${
                                suggestion.action === "buy"
                                  ? "bg-green-100 text-green-700"
                                  : suggestion.action === "sell"
                                  ? "bg-red-100 text-red-700"
                                  : "bg-gray-100 text-gray-700"
                              }`}>
                                {suggestion.action === "buy" ? "買い" : suggestion.action === "sell" ? "売り" : "維持"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {rebalanceResult.expected_improvement && (
                    <div className="mt-6 grid grid-cols-2 gap-4">
                      {rebalanceResult.expected_improvement.sharpe_before !== undefined && (
                        <div className="p-4 bg-gray-50 rounded-lg">
                          <p className="text-sm text-gray-600">シャープレシオ</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-lg text-gray-500">{rebalanceResult.expected_improvement.sharpe_before?.toFixed(2)}</span>
                            <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                            </svg>
                            <span className="text-lg font-bold text-green-600">{rebalanceResult.expected_improvement.sharpe_after?.toFixed(2)}</span>
                          </div>
                        </div>
                      )}
                      {rebalanceResult.expected_improvement.volatility_before !== undefined && (
                        <div className="p-4 bg-gray-50 rounded-lg">
                          <p className="text-sm text-gray-600">ボラティリティ</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-lg text-gray-500">{(rebalanceResult.expected_improvement.volatility_before! * 100).toFixed(1)}%</span>
                            <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                            </svg>
                            <span className="text-lg font-bold text-green-600">{(rebalanceResult.expected_improvement.volatility_after! * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 効率的フロンティアタブ */}
          {activeTab === "frontier" && (
            <div className="space-y-6">
              <div className="holo-card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900">効率的フロンティア</h3>
                  <button
                    onClick={calculateFrontier}
                    disabled={loading}
                    className="btn-iris py-2 px-4 text-sm"
                  >
                    再計算
                  </button>
                </div>

                {frontierResult && (
                  <>
                    {/* フロンティア可視化 */}
                    <div className="relative h-80 bg-gradient-to-br from-indigo-50 to-cyan-50 rounded-xl p-4">
                      <svg className="w-full h-full" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet">
                        {/* 軸 */}
                        <line x1="50" y1="260" x2="380" y2="260" stroke="#CBD5E1" strokeWidth="2" />
                        <line x1="50" y1="260" x2="50" y2="20" stroke="#CBD5E1" strokeWidth="2" />

                        {/* 軸ラベル */}
                        <text x="215" y="290" textAnchor="middle" className="fill-gray-500 text-xs">リスク（ボラティリティ）</text>
                        <text x="20" y="140" textAnchor="middle" transform="rotate(-90, 20, 140)" className="fill-gray-500 text-xs">期待リターン</text>

                        {/* フロンティアカーブ */}
                        {frontierResult.frontier_points.length > 0 && (
                          <path
                            d={`M ${frontierResult.frontier_points
                              .map((p, i) => {
                                const x = 50 + (p.volatility * 1000);
                                const y = 260 - (p.expected_return * 500);
                                return `${i === 0 ? "M" : "L"} ${Math.min(Math.max(x, 50), 380)} ${Math.min(Math.max(y, 20), 260)}`;
                              })
                              .join(" ")}`}
                            fill="none"
                            stroke="url(#frontierGradient)"
                            strokeWidth="3"
                          />
                        )}

                        {/* グラデーション定義 */}
                        <defs>
                          <linearGradient id="frontierGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#6366F1" />
                            <stop offset="100%" stopColor="#22D3EE" />
                          </linearGradient>
                        </defs>

                        {/* 現在のポートフォリオ */}
                        <circle
                          cx={Math.min(Math.max(50 + (frontierResult.current_portfolio.volatility * 1000), 50), 380)}
                          cy={Math.min(Math.max(260 - (frontierResult.current_portfolio.expected_return * 500), 20), 260)}
                          r="8"
                          fill="#EF4444"
                          stroke="#FFF"
                          strokeWidth="2"
                        />

                        {/* 最適ポートフォリオ */}
                        <circle
                          cx={Math.min(Math.max(50 + (frontierResult.optimal_portfolio.volatility * 1000), 50), 380)}
                          cy={Math.min(Math.max(260 - (frontierResult.optimal_portfolio.expected_return * 500), 20), 260)}
                          r="8"
                          fill="#22C55E"
                          stroke="#FFF"
                          strokeWidth="2"
                        />

                        {/* 最小分散ポートフォリオ */}
                        <circle
                          cx={Math.min(Math.max(50 + (frontierResult.min_variance_portfolio.volatility * 1000), 50), 380)}
                          cy={Math.min(Math.max(260 - (frontierResult.min_variance_portfolio.expected_return * 500), 20), 260)}
                          r="8"
                          fill="#3B82F6"
                          stroke="#FFF"
                          strokeWidth="2"
                        />
                      </svg>

                      {/* 凡例 */}
                      <div className="absolute bottom-4 right-4 bg-white/80 backdrop-blur rounded-lg p-3 space-y-2 text-xs">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full bg-red-500" />
                          <span>現在のポートフォリオ</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full bg-green-500" />
                          <span>最大シャープ比率</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full bg-blue-500" />
                          <span>最小分散</span>
                        </div>
                      </div>
                    </div>

                    {/* 比較表 */}
                    <div className="mt-6 grid grid-cols-3 gap-4">
                      <div className="p-4 border border-red-200 rounded-xl bg-red-50">
                        <p className="text-sm font-medium text-red-700 mb-2">現在のポートフォリオ</p>
                        <p className="text-sm">期待リターン: {(frontierResult.current_portfolio.expected_return * 100).toFixed(2)}%</p>
                        <p className="text-sm">ボラティリティ: {(frontierResult.current_portfolio.volatility * 100).toFixed(2)}%</p>
                        <p className="text-sm">シャープ比率: {frontierResult.current_portfolio.sharpe_ratio.toFixed(2)}</p>
                      </div>
                      <div className="p-4 border border-green-200 rounded-xl bg-green-50">
                        <p className="text-sm font-medium text-green-700 mb-2">最大シャープ</p>
                        <p className="text-sm">期待リターン: {(frontierResult.optimal_portfolio.expected_return * 100).toFixed(2)}%</p>
                        <p className="text-sm">ボラティリティ: {(frontierResult.optimal_portfolio.volatility * 100).toFixed(2)}%</p>
                        <p className="text-sm">シャープ比率: {frontierResult.optimal_portfolio.sharpe_ratio.toFixed(2)}</p>
                      </div>
                      <div className="p-4 border border-blue-200 rounded-xl bg-blue-50">
                        <p className="text-sm font-medium text-blue-700 mb-2">最小分散</p>
                        <p className="text-sm">期待リターン: {(frontierResult.min_variance_portfolio.expected_return * 100).toFixed(2)}%</p>
                        <p className="text-sm">ボラティリティ: {(frontierResult.min_variance_portfolio.volatility * 100).toFixed(2)}%</p>
                        <p className="text-sm">シャープ比率: {frontierResult.min_variance_portfolio.sharpe_ratio.toFixed(2)}</p>
                      </div>
                    </div>

                    {/* 最適ウェイト */}
                    <div className="mt-6">
                      <h4 className="font-medium text-gray-900 mb-3">最適ポートフォリオの配分</h4>
                      <div className="flex flex-wrap gap-3">
                        {Object.entries(frontierResult.optimal_portfolio.weights).map(([ticker, weight]) => (
                          <div key={ticker} className="px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
                            <span className="font-mono text-green-700">{ticker}</span>
                            <span className="ml-2 text-green-600">{(weight * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* リスク分解タブ */}
          {activeTab === "risk" && (
            <div className="space-y-6">
              <div className="holo-card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900">リスク分解分析</h3>
                  <button
                    onClick={analyzeRisk}
                    disabled={loading}
                    className="btn-iris py-2 px-4 text-sm"
                  >
                    再計算
                  </button>
                </div>

                {riskResult && (
                  <>
                    <div className="grid grid-cols-2 gap-4 mb-6">
                      <div className="p-4 bg-indigo-50 rounded-xl">
                        <p className="text-sm text-indigo-600">総ボラティリティ</p>
                        <p className="text-2xl font-bold text-indigo-700">{(riskResult.total_volatility * 100).toFixed(2)}%</p>
                      </div>
                      <div className="p-4 bg-cyan-50 rounded-xl">
                        <p className="text-sm text-cyan-600">分散比率</p>
                        <p className="text-2xl font-bold text-cyan-700">{riskResult.diversification_ratio.toFixed(2)}</p>
                        <p className="text-xs text-cyan-500 mt-1">1より大きいほど分散効果が高い</p>
                      </div>
                    </div>

                    <h4 className="font-medium text-gray-900 mb-3">銘柄別リスク寄与度</h4>
                    <div className="space-y-4">
                      {riskResult.contributions.map((contrib) => (
                        <div key={contrib.ticker_code} className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-mono text-indigo-600">{contrib.ticker_code}</span>
                            <span className="text-gray-600">
                              寄与度: {contrib.contribution_percent.toFixed(1)}% |
                              単独ボラ: {(contrib.standalone_volatility * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-full transition-all duration-500"
                              style={{ width: `${Math.min(contrib.contribution_percent, 100)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="mt-6 p-4 bg-indigo-50 rounded-lg">
                      <p className="text-sm text-indigo-700">
                        <strong>解釈:</strong> 分散比率が{riskResult.diversification_ratio.toFixed(2)}なので、
                        ポートフォリオ構成により
                        {riskResult.diversification_ratio > 1.2
                          ? "良好な分散効果が得られています。"
                          : riskResult.diversification_ratio > 1.0
                          ? "一定の分散効果があります。"
                          : "分散効果が限定的です。異なるセクターの銘柄追加を検討してください。"}
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 使い方説明 */}
      <div className="mt-8 glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">使い方</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[
            { step: "1", title: "ポジションを入力", desc: "銘柄コード、株数、取得価格を入力" },
            { step: "2", title: "分析を実行", desc: "ボタンをクリックして分析開始" },
            { step: "3", title: "結果を確認", desc: "各タブで詳細な分析結果を確認" },
            { step: "4", title: "最適化を検討", desc: "リバランス提案を参考に調整" },
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
