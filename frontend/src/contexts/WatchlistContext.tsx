"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { api } from "@/lib/api";
import type { Watchlist, WatchlistWithPrices, WatchlistItemWithPrice, AlertType } from "@/types";

// ローカルストレージ用の簡易型（ログイン前用）
interface LocalWatchlistItem {
  ticker_code: string;
  name: string;
  addedAt: string;
}

interface WatchlistContextType {
  // ローカルウォッチリスト（非ログイン時用）
  localWatchlist: LocalWatchlistItem[];
  addToLocalWatchlist: (ticker_code: string, name: string) => void;
  removeFromLocalWatchlist: (ticker_code: string) => void;
  isInLocalWatchlist: (ticker_code: string) => boolean;

  // サーバーウォッチリスト（ログイン時用）
  watchlists: Watchlist[];
  currentWatchlist: WatchlistWithPrices | null;
  isLoading: boolean;
  error: string | null;

  // サーバーウォッチリスト操作
  fetchWatchlists: () => Promise<void>;
  fetchWatchlist: (id: number) => Promise<void>;
  createWatchlist: (name: string) => Promise<Watchlist | null>;
  deleteWatchlist: (id: number) => Promise<void>;
  addItem: (watchlistId: number, tickerCode: string, targetPriceHigh?: number, targetPriceLow?: number, notes?: string) => Promise<void>;
  removeItem: (itemId: number) => Promise<void>;
  updateItem: (itemId: number, data: { target_price_high?: number; target_price_low?: number; notes?: string }) => Promise<void>;

  // アラート操作
  createAlert: (itemId: number, alertType: AlertType, threshold: number) => Promise<void>;
  deleteAlert: (alertId: number) => Promise<void>;

  // ユーティリティ
  isAuthenticated: boolean;
  setIsAuthenticated: (value: boolean) => void;
  refreshCurrentWatchlist: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = "iris-watchlist";

export function WatchlistProvider({ children }: { children: ReactNode }) {
  // ローカルウォッチリスト（非ログイン時）
  const [localWatchlist, setLocalWatchlist] = useState<LocalWatchlistItem[]>([]);
  const [isLocalLoaded, setIsLocalLoaded] = useState(false);

  // サーバーウォッチリスト（ログイン時）
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [currentWatchlist, setCurrentWatchlist] = useState<WatchlistWithPrices | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // ローカルストレージからローカルウォッチリストを読み込み
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (stored) {
        try {
          setLocalWatchlist(JSON.parse(stored));
        } catch {
          localStorage.removeItem(LOCAL_STORAGE_KEY);
        }
      }
      setIsLocalLoaded(true);
    }
  }, []);

  // ローカルウォッチリストを保存
  useEffect(() => {
    if (isLocalLoaded && typeof window !== "undefined") {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(localWatchlist));
    }
  }, [localWatchlist, isLocalLoaded]);

  // 認証状態の確認
  useEffect(() => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("token");
      setIsAuthenticated(!!token);
    }
  }, []);

  // ローカルウォッチリスト操作
  const addToLocalWatchlist = useCallback((ticker_code: string, name: string) => {
    setLocalWatchlist((prev) => {
      if (prev.some((item) => item.ticker_code === ticker_code)) {
        return prev;
      }
      return [...prev, { ticker_code, name, addedAt: new Date().toISOString() }];
    });
  }, []);

  const removeFromLocalWatchlist = useCallback((ticker_code: string) => {
    setLocalWatchlist((prev) => prev.filter((item) => item.ticker_code !== ticker_code));
  }, []);

  const isInLocalWatchlist = useCallback((ticker_code: string) => {
    return localWatchlist.some((item) => item.ticker_code === ticker_code);
  }, [localWatchlist]);

  // サーバーウォッチリスト操作
  const fetchWatchlists = useCallback(async () => {
    if (!isAuthenticated) return;

    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getWatchlists();
      setWatchlists(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch watchlists");
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const fetchWatchlist = useCallback(async (id: number) => {
    if (!isAuthenticated) return;

    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getWatchlist(id);
      setCurrentWatchlist(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch watchlist");
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const refreshCurrentWatchlist = useCallback(async () => {
    if (currentWatchlist) {
      await fetchWatchlist(currentWatchlist.id);
    }
  }, [currentWatchlist, fetchWatchlist]);

  const createWatchlist = useCallback(async (name: string): Promise<Watchlist | null> => {
    if (!isAuthenticated) return null;

    setIsLoading(true);
    setError(null);
    try {
      const data = await api.createWatchlist(name);
      setWatchlists((prev) => [...prev, data]);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create watchlist");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const deleteWatchlist = useCallback(async (id: number) => {
    if (!isAuthenticated) return;

    setIsLoading(true);
    setError(null);
    try {
      await api.deleteWatchlist(id);
      setWatchlists((prev) => prev.filter((w) => w.id !== id));
      if (currentWatchlist?.id === id) {
        setCurrentWatchlist(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete watchlist");
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, currentWatchlist]);

  const addItem = useCallback(async (
    watchlistId: number,
    tickerCode: string,
    targetPriceHigh?: number,
    targetPriceLow?: number,
    notes?: string
  ) => {
    if (!isAuthenticated) return;

    setError(null);
    try {
      await api.addWatchlistItem(watchlistId, tickerCode, targetPriceHigh, targetPriceLow, notes);
      await refreshCurrentWatchlist();
      await fetchWatchlists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add item");
    }
  }, [isAuthenticated, refreshCurrentWatchlist, fetchWatchlists]);

  const removeItem = useCallback(async (itemId: number) => {
    if (!isAuthenticated) return;

    setError(null);
    try {
      await api.removeWatchlistItem(itemId);
      if (currentWatchlist) {
        setCurrentWatchlist({
          ...currentWatchlist,
          items: currentWatchlist.items.filter((item) => item.id !== itemId),
          item_count: currentWatchlist.item_count - 1,
        });
      }
      await fetchWatchlists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove item");
    }
  }, [isAuthenticated, currentWatchlist, fetchWatchlists]);

  const updateItem = useCallback(async (
    itemId: number,
    data: { target_price_high?: number; target_price_low?: number; notes?: string }
  ) => {
    if (!isAuthenticated) return;

    setError(null);
    try {
      await api.updateWatchlistItem(itemId, data);
      await refreshCurrentWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update item");
    }
  }, [isAuthenticated, refreshCurrentWatchlist]);

  const createAlert = useCallback(async (
    itemId: number,
    alertType: AlertType,
    threshold: number
  ) => {
    if (!isAuthenticated) return;

    setError(null);
    try {
      await api.createAlert(itemId, alertType, threshold);
      await refreshCurrentWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create alert");
    }
  }, [isAuthenticated, refreshCurrentWatchlist]);

  const deleteAlert = useCallback(async (alertId: number) => {
    if (!isAuthenticated) return;

    setError(null);
    try {
      await api.deleteAlert(alertId);
      await refreshCurrentWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete alert");
    }
  }, [isAuthenticated, refreshCurrentWatchlist]);

  return (
    <WatchlistContext.Provider
      value={{
        // ローカルウォッチリスト
        localWatchlist,
        addToLocalWatchlist,
        removeFromLocalWatchlist,
        isInLocalWatchlist,

        // サーバーウォッチリスト
        watchlists,
        currentWatchlist,
        isLoading,
        error,

        // サーバー操作
        fetchWatchlists,
        fetchWatchlist,
        createWatchlist,
        deleteWatchlist,
        addItem,
        removeItem,
        updateItem,

        // アラート
        createAlert,
        deleteAlert,

        // ユーティリティ
        isAuthenticated,
        setIsAuthenticated,
        refreshCurrentWatchlist,
      }}
    >
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const context = useContext(WatchlistContext);
  if (!context) {
    throw new Error("useWatchlist must be used within a WatchlistProvider");
  }
  return context;
}

// 後方互換性のための簡易フック（既存コードとの互換性）
export function useSimpleWatchlist() {
  const { localWatchlist, addToLocalWatchlist, removeFromLocalWatchlist, isInLocalWatchlist } = useWatchlist();

  return {
    watchlist: localWatchlist,
    addToWatchlist: addToLocalWatchlist,
    removeFromWatchlist: removeFromLocalWatchlist,
    isInWatchlist: isInLocalWatchlist,
  };
}
