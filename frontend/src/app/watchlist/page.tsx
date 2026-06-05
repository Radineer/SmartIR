"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { useWatchlist } from "@/contexts/WatchlistContext";
import type { WatchlistItemWithPrice, AlertType } from "@/types";

// アラートモーダルコンポーネント
function AlertModal({
  item,
  onClose,
  onCreateAlert,
}: {
  item: WatchlistItemWithPrice;
  onClose: () => void;
  onCreateAlert: (alertType: AlertType, threshold: number) => void;
}) {
  const [alertType, setAlertType] = useState<AlertType>("price_above");
  const [threshold, setThreshold] = useState<string>(
    item.current_price?.toString() || ""
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const thresholdValue = parseFloat(threshold);
    if (!isNaN(thresholdValue) && thresholdValue > 0) {
      onCreateAlert(alertType, thresholdValue);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-xl">
        <h3 className="text-lg font-semibold mb-4">
          アラート設定 - {item.name || item.ticker_code}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              アラートタイプ
            </label>
            <select
              value={alertType}
              onChange={(e) => setAlertType(e.target.value as AlertType)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="price_above">指定価格を上回ったら通知</option>
              <option value="price_below">指定価格を下回ったら通知</option>
              <option value="volatility">変動率が閾値を超えたら通知</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {alertType === "volatility" ? "変動率 (%)" : "価格 (円)"}
            </label>
            <input
              type="number"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              step={alertType === "volatility" ? "0.1" : "1"}
              min="0"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder={
                alertType === "volatility" ? "5.0" : item.current_price?.toString()
              }
            />
            {item.current_price && alertType !== "volatility" && (
              <p className="text-xs text-gray-500 mt-1">
                現在価格: {item.current_price.toLocaleString()}円
              </p>
            )}
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              キャンセル
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              設定する
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// 銘柄追加モーダルコンポーネント
function AddItemModal({
  watchlistId,
  onClose,
  onAddItem,
}: {
  watchlistId: number;
  onClose: () => void;
  onAddItem: (tickerCode: string, notes?: string) => void;
}) {
  const [tickerCode, setTickerCode] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (tickerCode.trim()) {
      onAddItem(tickerCode.trim(), notes.trim() || undefined);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-xl">
        <h3 className="text-lg font-semibold mb-4">銘柄を追加</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              証券コード
            </label>
            <input
              type="text"
              value={tickerCode}
              onChange={(e) => setTickerCode(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="例: 7203"
              maxLength={10}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              メモ（任意）
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              rows={3}
              placeholder="決算発表後に購入検討など"
              maxLength={500}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              キャンセル
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              追加する
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// 価格変動インジケーター
function PriceChange({
  change,
  changePercent,
}: {
  change?: number;
  changePercent?: number;
}) {
  if (change === undefined || changePercent === undefined) {
    return <span className="text-gray-400 text-sm">--</span>;
  }

  const isPositive = change > 0;
  const isNegative = change < 0;

  return (
    <span
      className={`text-sm font-medium ${
        isPositive
          ? "text-green-600"
          : isNegative
          ? "text-red-600"
          : "text-gray-500"
      }`}
    >
      {isPositive ? "+" : ""}
      {change.toLocaleString()}円 ({isPositive ? "+" : ""}
      {changePercent.toFixed(2)}%)
    </span>
  );
}

// ウォッチリストアイテムカード
function WatchlistItemCard({
  item,
  onRemove,
  onSetAlert,
}: {
  item: WatchlistItemWithPrice;
  onRemove: () => void;
  onSetAlert: () => void;
}) {
  const [isRemoving, setIsRemoving] = useState(false);

  const handleRemove = () => {
    setIsRemoving(true);
    setTimeout(onRemove, 300);
  };

  const alertTypeLabels: Record<AlertType, string> = {
    price_above: "上限",
    price_below: "下限",
    volatility: "変動",
    ir_release: "IR",
  };

  return (
    <div
      className={`holo-card p-5 group transition-all duration-300 ${
        isRemoving ? "opacity-0 scale-95" : ""
      } ${item.is_alert_triggered ? "ring-2 ring-orange-400" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <Link href={`/stocks/${item.ticker_code}`} className="flex-1 min-w-0">
          <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
            {item.ticker_code}
          </span>
          <h3 className="text-base font-semibold text-gray-900 mt-2 group-hover:text-indigo-600 transition-colors truncate">
            {item.name || `銘柄 ${item.ticker_code}`}
          </h3>
        </Link>
        <div className="flex items-center gap-1">
          <button
            onClick={onSetAlert}
            className="p-2 text-gray-400 hover:text-indigo-500 hover:bg-indigo-50 rounded-lg transition-colors"
            title="アラート設定"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
              />
            </svg>
          </button>
          <button
            onClick={handleRemove}
            className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            title="削除"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* 価格情報 */}
      <div className="mt-3 space-y-1">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-bold text-gray-900">
            {item.current_price
              ? `${item.current_price.toLocaleString()}円`
              : "--"}
          </span>
          <PriceChange
            change={item.price_change}
            changePercent={item.price_change_percent}
          />
        </div>
      </div>

      {/* アラート表示 */}
      {item.alerts && item.alerts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {item.alerts.map((alert) => (
            <span
              key={alert.id}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${
                alert.is_triggered
                  ? "bg-orange-100 text-orange-700 border border-orange-200"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {alertTypeLabels[alert.alert_type]}:{" "}
              {alert.threshold.toLocaleString()}
              {alert.alert_type === "volatility" ? "%" : "円"}
              {alert.is_triggered && (
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
              )}
            </span>
          ))}
        </div>
      )}

      {/* メモ */}
      {item.notes && (
        <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded p-2">
          {item.notes}
        </div>
      )}

      {/* フッター */}
      <div className="mt-3 pt-3 border-t border-indigo-100/50 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {new Date(item.added_at).toLocaleDateString("ja-JP")} 追加
        </span>
        <Link
          href={`/stocks/${item.ticker_code}`}
          className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
        >
          詳細を見る
        </Link>
      </div>
    </div>
  );
}

export default function WatchlistPage() {
  const {
    localWatchlist,
    removeFromLocalWatchlist,
    isAuthenticated,
    watchlists,
    currentWatchlist,
    isLoading,
    error,
    fetchWatchlists,
    fetchWatchlist,
    createWatchlist,
    removeItem,
    addItem,
    createAlert,
  } = useWatchlist();

  const [selectedWatchlistId, setSelectedWatchlistId] = useState<number | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showAlertModal, setShowAlertModal] = useState<WatchlistItemWithPrice | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // 初期読み込み
  useEffect(() => {
    if (isAuthenticated) {
      fetchWatchlists();
    }
  }, [isAuthenticated, fetchWatchlists]);

  // 最初のウォッチリストを選択
  useEffect(() => {
    if (watchlists.length > 0 && !selectedWatchlistId) {
      setSelectedWatchlistId(watchlists[0].id);
    }
  }, [watchlists, selectedWatchlistId]);

  // 選択されたウォッチリストを読み込み
  useEffect(() => {
    if (selectedWatchlistId) {
      fetchWatchlist(selectedWatchlistId);
    }
  }, [selectedWatchlistId, fetchWatchlist]);

  // 自動更新
  useEffect(() => {
    if (autoRefresh && selectedWatchlistId) {
      const interval = setInterval(() => {
        fetchWatchlist(selectedWatchlistId);
      }, 30000); // 30秒ごと
      return () => clearInterval(interval);
    }
  }, [autoRefresh, selectedWatchlistId, fetchWatchlist]);

  // ウォッチリスト作成
  const handleCreateWatchlist = async () => {
    const name = prompt("ウォッチリスト名を入力してください:", "新規ウォッチリスト");
    if (name) {
      const newWatchlist = await createWatchlist(name);
      if (newWatchlist) {
        setSelectedWatchlistId(newWatchlist.id);
      }
    }
  };

  // 銘柄追加
  const handleAddItem = useCallback(
    async (tickerCode: string, notes?: string) => {
      if (selectedWatchlistId) {
        await addItem(selectedWatchlistId, tickerCode, undefined, undefined, notes);
      }
    },
    [selectedWatchlistId, addItem]
  );

  // アラート作成
  const handleCreateAlert = useCallback(
    async (alertType: AlertType, threshold: number) => {
      if (showAlertModal) {
        await createAlert(showAlertModal.id, alertType, threshold);
      }
    },
    [showAlertModal, createAlert]
  );

  // ログイン前のローカルウォッチリスト表示
  if (!isAuthenticated) {
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
              <h1 className="section-title text-2xl md:text-3xl">ウォッチリスト</h1>
              <p className="text-gray-600 mt-3">
                {localWatchlist.length > 0 ? (
                  <>
                    <span className="text-indigo-600 font-semibold">
                      {localWatchlist.length}
                    </span>
                    銘柄を登録中
                  </>
                ) : (
                  "お気に入りの銘柄を登録してみましょう"
                )}
              </p>
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200">
                <span className="text-sm text-amber-700">
                  ログインすると価格アラートやリアルタイム更新が使えます
                </span>
              </div>
            </div>
            <Link
              href="/login"
              className="btn-iris"
            >
              ログイン
            </Link>
          </div>
        </div>

        {/* ローカルウォッチリスト */}
        {localWatchlist.length === 0 ? (
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-indigo-100 mb-4">
              <Image
                src="/images/iris/iris-normal.png"
                alt="イリス"
                width={48}
                height={48}
                className="opacity-50"
              />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              ウォッチリストに銘柄がありません
            </h3>
            <p className="text-gray-500 mb-6">
              銘柄ページの星マークをタップして追加してみてくださいね
            </p>
            <Link href="/stocks" className="btn-iris inline-block">
              銘柄一覧を見る
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {localWatchlist.map((item) => (
              <div key={item.ticker_code} className="holo-card p-5 group">
                <div className="flex items-start justify-between gap-2">
                  <Link
                    href={`/stocks/${item.ticker_code}`}
                    className="flex-1 min-w-0"
                  >
                    <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 text-indigo-700 border border-indigo-200">
                      {item.ticker_code}
                    </span>
                    <h3 className="text-base font-semibold text-gray-900 mt-2 group-hover:text-indigo-600 transition-colors truncate">
                      {item.name}
                    </h3>
                  </Link>
                  <button
                    onClick={() => removeFromLocalWatchlist(item.ticker_code)}
                    className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="削除"
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
                <div className="mt-3 pt-3 border-t border-indigo-100/50 flex items-center justify-between">
                  <span className="text-xs text-gray-400">
                    {new Date(item.addedAt).toLocaleDateString("ja-JP")} 追加
                  </span>
                  <Link
                    href={`/stocks/${item.ticker_code}`}
                    className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
                  >
                    詳細を見る
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ログイン後のサーバーウォッチリスト表示
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
            <h1 className="section-title text-2xl md:text-3xl">ウォッチリスト</h1>
            <p className="text-gray-600 mt-3">
              {currentWatchlist && currentWatchlist.items.length > 0 ? (
                <>
                  <span className="text-indigo-600 font-semibold">
                    {currentWatchlist.items.length}
                  </span>
                  銘柄を監視中
                </>
              ) : (
                "気になる銘柄を追加してリアルタイムで監視しましょう"
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded"
              />
              自動更新
            </label>
            <button
              onClick={() => setShowAddModal(true)}
              className="btn-iris"
              disabled={!selectedWatchlistId}
            >
              銘柄を追加
            </button>
          </div>
        </div>
      </div>

      {/* ウォッチリストタブ */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
        {watchlists.map((wl) => (
          <button
            key={wl.id}
            onClick={() => setSelectedWatchlistId(wl.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              selectedWatchlistId === wl.id
                ? "bg-indigo-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-100"
            }`}
          >
            {wl.name}
            <span className="ml-2 text-xs opacity-70">({wl.item_count})</span>
          </button>
        ))}
        <button
          onClick={handleCreateWatchlist}
          className="px-4 py-2 rounded-lg text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 transition-colors"
        >
          + 新規作成
        </button>
      </div>

      {/* エラー表示 */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* ローディング */}
      {isLoading && (
        <div className="text-center py-16">
          <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto" />
          <p className="mt-4 text-gray-500">読み込み中...</p>
        </div>
      )}

      {/* ウォッチリストアイテム */}
      {!isLoading && currentWatchlist && (
        <>
          {currentWatchlist.items.length === 0 ? (
            <div className="text-center py-16">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-indigo-100 mb-4">
                <Image
                  src="/images/iris/iris-normal.png"
                  alt="イリス"
                  width={48}
                  height={48}
                  className="opacity-50"
                />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                このウォッチリストに銘柄がありません
              </h3>
              <p className="text-gray-500 mb-6">
                「銘柄を追加」ボタンから銘柄コードを入力して追加してください
              </p>
              <button
                onClick={() => setShowAddModal(true)}
                className="btn-iris inline-block"
              >
                銘柄を追加
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {currentWatchlist.items.map((item) => (
                <WatchlistItemCard
                  key={item.id}
                  item={item}
                  onRemove={() => removeItem(item.id)}
                  onSetAlert={() => setShowAlertModal(item)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* ウォッチリストがない場合 */}
      {!isLoading && watchlists.length === 0 && (
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-indigo-100 mb-4">
            <Image
              src="/images/iris/iris-normal.png"
              alt="イリス"
              width={48}
              height={48}
              className="opacity-50"
            />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            ウォッチリストを作成しましょう
          </h3>
          <p className="text-gray-500 mb-6">
            ウォッチリストを作成して、気になる銘柄を追加してください
          </p>
          <button onClick={handleCreateWatchlist} className="btn-iris inline-block">
            ウォッチリストを作成
          </button>
        </div>
      )}

      {/* 銘柄追加モーダル */}
      {showAddModal && selectedWatchlistId && (
        <AddItemModal
          watchlistId={selectedWatchlistId}
          onClose={() => setShowAddModal(false)}
          onAddItem={handleAddItem}
        />
      )}

      {/* アラート設定モーダル */}
      {showAlertModal && (
        <AlertModal
          item={showAlertModal}
          onClose={() => setShowAlertModal(null)}
          onCreateAlert={handleCreateAlert}
        />
      )}
    </div>
  );
}
