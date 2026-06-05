"use client";

import { useEffect, useState, useMemo } from "react";
import Image from "next/image";
import { api } from "@/lib/api";
import type {
  BacktestStrategy,
  BacktestStrategyId,
  BacktestResult,
  BacktestHistoryItem,
  OptimizeResult,
} from "@/types";

// デフォルト戦略定義（APIが利用できない場合のフォールバック）
const DEFAULT_STRATEGIES: BacktestStrategy[] = [
  {
    id: "sma_cross",
    name: "SMAクロス",
    description: "短期移動平均線が長期移動平均線を上抜けで買い、下抜けで売り",
    parameters: [
      { name: "short_period", label: "短期SMA期間", type: "number", default: 5, min: 2, max: 50, step: 1 },
      { name: "long_period", label: "長期SMA期間", type: "number", default: 25, min: 5, max: 200, step: 1 },
    ],
  },
  {
    id: "rsi",
    name: "RSI",
    description: "RSIが下限を下回ったら買い、上限を上回ったら売り",
    parameters: [
      { name: "period", label: "RSI期間", type: "number", default: 14, min: 2, max: 50, step: 1 },
      { name: "oversold", label: "売られすぎ", type: "number", default: 30, min: 10, max: 40, step: 5 },
      { name: "overbought", label: "買われすぎ", type: "number", default: 70, min: 60, max: 90, step: 5 },
    ],
  },
  {
    id: "macd",
    name: "MACD",
    description: "MACDラインがシグナルラインを上抜けで買い、下抜けで売り",
    parameters: [
      { name: "fast_period", label: "短期EMA", type: "number", default: 12, min: 5, max: 30, step: 1 },
      { name: "slow_period", label: "長期EMA", type: "number", default: 26, min: 10, max: 50, step: 1 },
      { name: "signal_period", label: "シグナル期間", type: "number", default: 9, min: 3, max: 20, step: 1 },
    ],
  },
  {
    id: "bollinger",
    name: "ボリンジャーバンド",
    description: "下バンドでの買い、上バンドでの売り",
    parameters: [
      { name: "period", label: "移動平均期間", type: "number", default: 20, min: 5, max: 50, step: 1 },
      { name: "std_dev", label: "標準偏差倍率", type: "number", default: 2, min: 1, max: 3, step: 0.5 },
    ],
  },
  {
    id: "momentum",
    name: "モメンタム",
    description: "一定期間の価格変化率を基に売買",
    parameters: [
      { name: "period", label: "モメンタム期間", type: "number", default: 10, min: 5, max: 30, step: 1 },
      { name: "threshold", label: "閾値(%)", type: "number", default: 5, min: 1, max: 20, step: 1 },
    ],
  },
  {
    id: "mean_reversion",
    name: "平均回帰",
    description: "移動平均からの乖離率を基に逆張り",
    parameters: [
      { name: "period", label: "移動平均期間", type: "number", default: 20, min: 5, max: 50, step: 1 },
      { name: "deviation", label: "乖離率閾値(%)", type: "number", default: 5, min: 1, max: 15, step: 1 },
    ],
  },
  {
    id: "breakout",
    name: "ブレイクアウト",
    description: "一定期間の高値更新で買い、安値更新で売り",
    parameters: [
      { name: "period", label: "参照期間", type: "number", default: 20, min: 5, max: 60, step: 1 },
    ],
  },
];

// アイコンコンポーネント
const StrategyIcon = ({ strategyId }: { strategyId: BacktestStrategyId }) => {
  switch (strategyId) {
    case "sma_cross":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
        </svg>
      );
    case "rsi":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      );
    case "macd":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      );
    case "bollinger":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
        </svg>
      );
    case "momentum":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      );
    case "mean_reversion":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      );
    case "breakout":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
        </svg>
      );
    default:
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2z" />
        </svg>
      );
  }
};

// 結果フォーマット関数
const formatCurrency = (value: number) =>
  new Intl.NumberFormat("ja-JP", { style: "currency", currency: "JPY", maximumFractionDigits: 0 }).format(value);

const formatPercent = (value: number, decimals = 2) =>
  `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;

const formatNumber = (value: number, decimals = 2) => value.toFixed(decimals);

export default function BacktestPage() {
  // 戦略関連
  const [strategies, setStrategies] = useState<BacktestStrategy[]>(DEFAULT_STRATEGIES);
  const [selectedStrategy, setSelectedStrategy] = useState<BacktestStrategyId>("sma_cross");
  const [parameters, setParameters] = useState<Record<string, number | string>>({});

  // 入力フォーム
  const [tickerCode, setTickerCode] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialCapital, setInitialCapital] = useState(1000000);

  // 実行状態
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [error, setError] = useState("");

  // 結果
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null);
  const [history, setHistory] = useState<BacktestHistoryItem[]>([]);

  // タブ
  const [activeTab, setActiveTab] = useState<"result" | "trades" | "history">("result");

  // 最適化ターゲット
  const [optimizeTarget, setOptimizeTarget] = useState<"sharpe_ratio" | "total_return" | "max_drawdown">("sharpe_ratio");

  // 現在の戦略
  const currentStrategy = useMemo(
    () => strategies.find((s) => s.id === selectedStrategy),
    [strategies, selectedStrategy]
  );

  // 初期化
  useEffect(() => {
    const loadData = async () => {
      try {
        const [strategiesData, historyData] = await Promise.all([
          api.getBacktestStrategies().catch(() => DEFAULT_STRATEGIES),
          api.getBacktestHistory().catch(() => []),
        ]);
        setStrategies(strategiesData.length > 0 ? strategiesData : DEFAULT_STRATEGIES);
        setHistory(historyData);
      } catch (err) {
        console.error("Failed to load backtest data:", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();

    // デフォルト日付設定
    const today = new Date();
    const oneYearAgo = new Date(today);
    oneYearAgo.setFullYear(today.getFullYear() - 1);
    setEndDate(today.toISOString().split("T")[0]);
    setStartDate(oneYearAgo.toISOString().split("T")[0]);
  }, []);

  // 戦略変更時にパラメータを初期化
  useEffect(() => {
    if (currentStrategy) {
      const defaults: Record<string, number | string> = {};
      currentStrategy.parameters.forEach((p) => {
        defaults[p.name] = p.default;
      });
      setParameters(defaults);
    }
  }, [currentStrategy]);

  // バックテスト実行
  const handleRunBacktest = async () => {
    if (!tickerCode.trim()) {
      setError("銘柄コードを入力してください");
      return;
    }
    if (!startDate || !endDate) {
      setError("期間を設定してください");
      return;
    }

    setRunning(true);
    setError("");
    setResult(null);
    setOptimizeResult(null);

    try {
      const res = await api.runBacktest({
        ticker_code: tickerCode.toUpperCase(),
        strategy_id: selectedStrategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        parameters,
      });
      setResult(res);
      setActiveTab("result");
      // 履歴を更新
      const updatedHistory = await api.getBacktestHistory().catch(() => []);
      setHistory(updatedHistory);
    } catch (err) {
      setError(err instanceof Error ? err.message : "バックテストの実行に失敗しました");
    } finally {
      setRunning(false);
    }
  };

  // パラメータ最適化
  const handleOptimize = async () => {
    if (!tickerCode.trim()) {
      setError("銘柄コードを入力してください");
      return;
    }
    if (!startDate || !endDate) {
      setError("期間を設定してください");
      return;
    }

    setOptimizing(true);
    setError("");
    setOptimizeResult(null);

    try {
      const parameterRanges: Record<string, { min: number; max: number; step: number }> = {};
      if (currentStrategy) {
        currentStrategy.parameters.forEach((p) => {
          if (p.type === "number" && p.min !== undefined && p.max !== undefined) {
            parameterRanges[p.name] = {
              min: p.min,
              max: p.max,
              step: p.step || 1,
            };
          }
        });
      }

      const res = await api.optimizeBacktest({
        ticker_code: tickerCode.toUpperCase(),
        strategy_id: selectedStrategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        parameter_ranges: parameterRanges,
        optimize_target: optimizeTarget,
      });
      setOptimizeResult(res);
      setResult(res.backtest_result);
      // 最適パラメータを適用
      setParameters(res.best_parameters);
      setActiveTab("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "最適化に失敗しました");
    } finally {
      setOptimizing(false);
    }
  };

  // 履歴から結果を読み込み
  const handleLoadHistory = async (id: number) => {
    try {
      const res = await api.getBacktestResult(id);
      setResult(res);
      setSelectedStrategy(res.strategy_id);
      setTickerCode(res.ticker_code);
      setStartDate(res.start_date);
      setEndDate(res.end_date);
      setInitialCapital(res.initial_capital);
      setParameters(res.parameters);
      setActiveTab("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "履歴の読み込みに失敗しました");
    }
  };

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
                src="/images/iris/iris-analysis.png"
                alt="イリス"
                width={64}
                height={64}
                className="object-cover"
              />
            </div>
          </div>
          <div className="flex-1">
            <h1 className="section-title text-2xl md:text-3xl">バックテストラボ</h1>
            <p className="text-gray-600 mt-3">
              「過去のデータを使って投資戦略をテストできます。パラメータを調整して、最適な戦略を見つけましょう。」
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 左: 設定パネル */}
        <div className="lg:col-span-1 space-y-6">
          {/* 戦略選択 */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              戦略を選択
            </h2>
            <div className="grid grid-cols-2 gap-3">
              {strategies.map((strategy) => (
                <button
                  key={strategy.id}
                  onClick={() => setSelectedStrategy(strategy.id)}
                  className={`p-3 rounded-xl border-2 transition-all text-left ${
                    selectedStrategy === strategy.id
                      ? "border-indigo-500 bg-indigo-50"
                      : "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"
                  }`}
                >
                  <div className={`mb-2 ${selectedStrategy === strategy.id ? "text-indigo-600" : "text-gray-500"}`}>
                    <StrategyIcon strategyId={strategy.id} />
                  </div>
                  <div className={`text-sm font-medium ${selectedStrategy === strategy.id ? "text-indigo-900" : "text-gray-700"}`}>
                    {strategy.name}
                  </div>
                </button>
              ))}
            </div>
            {currentStrategy && (
              <p className="mt-4 text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
                {currentStrategy.description}
              </p>
            )}
          </div>

          {/* 基本設定 */}
          <div className="holo-card p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              基本設定
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">銘柄コード</label>
                <input
                  type="text"
                  value={tickerCode}
                  onChange={(e) => setTickerCode(e.target.value)}
                  placeholder="例: 7203.T"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">開始日</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">終了日</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">初期資金</label>
                <input
                  type="number"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  min={100000}
                  step={100000}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* パラメータ設定 */}
          {currentStrategy && currentStrategy.parameters.length > 0 && (
            <div className="holo-card p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                パラメータ設定
              </h2>
              <div className="space-y-4">
                {currentStrategy.parameters.map((param) => (
                  <div key={param.name}>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {param.label}
                      {param.min !== undefined && param.max !== undefined && (
                        <span className="text-xs text-gray-400 ml-2">
                          ({param.min} - {param.max})
                        </span>
                      )}
                    </label>
                    {param.type === "number" ? (
                      <input
                        type="number"
                        value={parameters[param.name] ?? param.default}
                        onChange={(e) =>
                          setParameters((prev) => ({
                            ...prev,
                            [param.name]: Number(e.target.value),
                          }))
                        }
                        min={param.min}
                        max={param.max}
                        step={param.step}
                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      />
                    ) : (
                      <select
                        value={parameters[param.name] ?? param.default}
                        onChange={(e) =>
                          setParameters((prev) => ({
                            ...prev,
                            [param.name]: e.target.value,
                          }))
                        }
                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      >
                        {param.options?.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 実行ボタン */}
          <div className="holo-card p-6">
            <button
              onClick={handleRunBacktest}
              disabled={running || optimizing}
              className="w-full btn-iris py-3 text-base font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {running ? (
                <>
                  <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  実行中...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  バックテスト実行
                </>
              )}
            </button>

            {/* 最適化セクション */}
            <div className="mt-4 pt-4 border-t border-gray-200">
              <label className="block text-sm font-medium text-gray-700 mb-2">最適化ターゲット</label>
              <select
                value={optimizeTarget}
                onChange={(e) => setOptimizeTarget(e.target.value as typeof optimizeTarget)}
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent mb-3"
              >
                <option value="sharpe_ratio">シャープレシオ</option>
                <option value="total_return">総リターン</option>
                <option value="max_drawdown">最大ドローダウン</option>
              </select>
              <button
                onClick={handleOptimize}
                disabled={running || optimizing}
                className="w-full btn-iris-outline py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {optimizing ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    最適化中...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    パラメータ最適化
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-3 bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-200">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {error}
              </div>
            )}
          </div>
        </div>

        {/* 右: 結果表示 */}
        <div className="lg:col-span-2 space-y-6">
          {/* タブ */}
          <div className="flex gap-2">
            {[
              { id: "result", label: "結果サマリー" },
              { id: "trades", label: "取引履歴" },
              { id: "history", label: "過去のテスト" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  activeTab === tab.id
                    ? "bg-indigo-500 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* 結果サマリー */}
          {activeTab === "result" && (
            <div className="space-y-6">
              {result ? (
                <>
                  {/* 最適化結果バナー */}
                  {optimizeResult && (
                    <div className="holo-card p-4 bg-gradient-to-r from-green-50 to-cyan-50">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center text-white">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-bold text-green-800">最適パラメータが見つかりました</p>
                          <p className="text-sm text-green-600">
                            {optimizeResult.optimize_target === "sharpe_ratio" && "シャープレシオ"}
                            {optimizeResult.optimize_target === "total_return" && "総リターン"}
                            {optimizeResult.optimize_target === "max_drawdown" && "最大ドローダウン"}
                            : {formatNumber(optimizeResult.best_score)}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* パフォーマンス概要 */}
                  <div className="holo-card p-6">
                    <h3 className="text-lg font-bold text-gray-900 mb-4">パフォーマンス概要</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <div className="p-4 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl">
                        <p className="text-xs text-gray-500 mb-1">総リターン</p>
                        <p className={`text-xl font-bold ${result.total_return_percent >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {formatPercent(result.total_return_percent)}
                        </p>
                      </div>
                      <div className="p-4 bg-gradient-to-br from-cyan-50 to-blue-50 rounded-xl">
                        <p className="text-xs text-gray-500 mb-1">シャープレシオ</p>
                        <p className="text-xl font-bold text-gray-900">{formatNumber(result.sharpe_ratio)}</p>
                      </div>
                      <div className="p-4 bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl">
                        <p className="text-xs text-gray-500 mb-1">最大ドローダウン</p>
                        <p className="text-xl font-bold text-red-600">{formatPercent(result.max_drawdown_percent)}</p>
                      </div>
                      <div className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl">
                        <p className="text-xs text-gray-500 mb-1">勝率</p>
                        <p className="text-xl font-bold text-gray-900">{formatNumber(result.win_rate)}%</p>
                      </div>
                    </div>
                  </div>

                  {/* 詳細統計 */}
                  <div className="holo-card p-6">
                    <h3 className="text-lg font-bold text-gray-900 mb-4">詳細統計</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">初期資金</span>
                        <span className="font-medium">{formatCurrency(result.initial_capital)}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">最終資産</span>
                        <span className="font-medium">{formatCurrency(result.final_value)}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">年率リターン</span>
                        <span className={`font-medium ${result.annualized_return >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {formatPercent(result.annualized_return)}
                        </span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">総取引数</span>
                        <span className="font-medium">{result.total_trades}回</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">勝ち取引</span>
                        <span className="font-medium text-green-600">{result.winning_trades}回</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">負け取引</span>
                        <span className="font-medium text-red-600">{result.losing_trades}回</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">平均勝ち</span>
                        <span className="font-medium text-green-600">{formatCurrency(result.avg_win)}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">平均負け</span>
                        <span className="font-medium text-red-600">{formatCurrency(Math.abs(result.avg_loss))}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">プロフィットファクター</span>
                        <span className="font-medium">{formatNumber(result.profit_factor)}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">最大利益</span>
                        <span className="font-medium text-green-600">{formatCurrency(result.best_trade)}</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">最大損失</span>
                        <span className="font-medium text-red-600">{formatCurrency(result.worst_trade)}</span>
                      </div>
                    </div>
                  </div>

                  {/* 資産推移グラフ（簡易版） */}
                  {result.equity_curve && result.equity_curve.length > 0 && (
                    <div className="holo-card p-6">
                      <h3 className="text-lg font-bold text-gray-900 mb-4">資産推移</h3>
                      <div className="h-48 flex items-end gap-0.5">
                        {result.equity_curve.slice(-60).map((point, i, arr) => {
                          const min = Math.min(...arr.map((p) => p.value));
                          const max = Math.max(...arr.map((p) => p.value));
                          const range = max - min || 1;
                          const height = ((point.value - min) / range) * 100;
                          const isPositive = point.value >= result.initial_capital;
                          return (
                            <div
                              key={i}
                              className={`flex-1 rounded-t ${isPositive ? "bg-gradient-to-t from-green-400 to-green-300" : "bg-gradient-to-t from-red-400 to-red-300"}`}
                              style={{ height: `${Math.max(height, 5)}%` }}
                              title={`${point.date}: ${formatCurrency(point.value)}`}
                            />
                          );
                        })}
                      </div>
                      <div className="flex justify-between text-xs text-gray-500 mt-2">
                        <span>{result.equity_curve[0]?.date}</span>
                        <span>{result.equity_curve[result.equity_curve.length - 1]?.date}</span>
                      </div>
                    </div>
                  )}

                  {/* 使用パラメータ */}
                  <div className="holo-card p-6">
                    <h3 className="text-lg font-bold text-gray-900 mb-4">使用パラメータ</h3>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(result.parameters).map(([key, value]) => (
                        <span
                          key={key}
                          className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm"
                        >
                          {key}: {value}
                        </span>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="holo-card p-12 flex flex-col items-center justify-center text-gray-400">
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
                    「戦略を選んで<br />バックテストを実行してみましょう」
                  </p>
                </div>
              )}
            </div>
          )}

          {/* 取引履歴 */}
          {activeTab === "trades" && (
            <div className="holo-card p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">取引履歴</h3>
              {result && result.trades.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-3 px-2 font-medium text-gray-600">日付</th>
                        <th className="text-left py-3 px-2 font-medium text-gray-600">売買</th>
                        <th className="text-right py-3 px-2 font-medium text-gray-600">価格</th>
                        <th className="text-right py-3 px-2 font-medium text-gray-600">株数</th>
                        <th className="text-right py-3 px-2 font-medium text-gray-600">金額</th>
                        <th className="text-right py-3 px-2 font-medium text-gray-600">損益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trades.map((trade, i) => (
                        <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="py-3 px-2">{trade.date}</td>
                          <td className="py-3 px-2">
                            <span
                              className={`px-2 py-1 rounded text-xs font-medium ${
                                trade.action === "buy"
                                  ? "bg-green-100 text-green-700"
                                  : "bg-red-100 text-red-700"
                              }`}
                            >
                              {trade.action === "buy" ? "買い" : "売り"}
                            </span>
                          </td>
                          <td className="text-right py-3 px-2">{formatCurrency(trade.price)}</td>
                          <td className="text-right py-3 px-2">{trade.shares}</td>
                          <td className="text-right py-3 px-2">{formatCurrency(trade.value)}</td>
                          <td className={`text-right py-3 px-2 font-medium ${
                            trade.pnl !== undefined
                              ? trade.pnl >= 0
                                ? "text-green-600"
                                : "text-red-600"
                              : ""
                          }`}>
                            {trade.pnl !== undefined ? formatCurrency(trade.pnl) : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  取引履歴がありません
                </p>
              )}
            </div>
          )}

          {/* 過去のテスト */}
          {activeTab === "history" && (
            <div className="holo-card p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">過去のバックテスト</h3>
              {history.length > 0 ? (
                <div className="space-y-3">
                  {history.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => handleLoadHistory(item.id)}
                      className="w-full p-4 bg-gray-50 hover:bg-indigo-50 rounded-xl transition-colors text-left"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900">{item.ticker_code}</span>
                          <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs">
                            {item.strategy_name}
                          </span>
                        </div>
                        <span className={`font-bold ${item.total_return_percent >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {formatPercent(item.total_return_percent)}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>{item.start_date} - {item.end_date}</span>
                        <span>SR: {formatNumber(item.sharpe_ratio)}</span>
                        <span>{new Date(item.created_at).toLocaleDateString("ja-JP")}</span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  過去のバックテスト履歴がありません
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 使い方説明 */}
      <div className="mt-8 glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">使い方</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[
            { step: "1", title: "戦略を選択", desc: "7種類の売買戦略から選びます" },
            { step: "2", title: "条件を設定", desc: "銘柄・期間・パラメータを入力" },
            { step: "3", title: "バックテスト実行", desc: "過去データで戦略をシミュレート" },
            { step: "4", title: "結果を分析", desc: "リターンやリスク指標を確認" },
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
