import type {
  Company,
  Document,
  AnalysisResult,
  VTuberScript,
  User,
  AuthToken,
  CrawlResponse,
  Watchlist,
  WatchlistWithPrices,
  WatchlistItem,
  PriceAlert,
  AlertType,
  TriggeredAlert,
  ScriptType,
  ScriptTypesResponse,
  MorningMarketScriptRequest,
  EarningsSeasonScriptRequest,
  ThemeStockScriptRequest,
  TechnicalAnalysisScriptRequest,
  PortfolioReviewScriptRequest,
  SentimentScriptRequest,
  MLPrediction,
  MLBatchPrediction,
  FeatureImportance,
  ModelEvaluation,
  IrisMLComment,
  BacktestStrategy,
  BacktestRequest,
  BacktestResult,
  OptimizeRequest,
  OptimizeResult,
  BacktestHistoryItem,
  PortfolioAnalysisPosition,
  PortfolioAnalysisResult,
  VaRResult,
  CorrelationResult,
  RebalanceMethod,
  RebalanceResult,
  EfficientFrontierResult,
  RiskDecompositionResult,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("token", token);
      } else {
        localStorage.removeItem("token");
      }
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== "undefined") {
      return localStorage.getItem("token");
    }
    return null;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = this.getToken();

    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    if (token) {
      (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  // 認証
  async register(email: string, password: string, name?: string): Promise<User> {
    return this.request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    });
  }

  async login(email: string, password: string): Promise<AuthToken> {
    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();
    this.setToken(data.access_token);
    return data;
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me");
  }

  logout() {
    this.setToken(null);
  }

  // 企業
  async getCompanies(skip = 0, limit = 100): Promise<Company[]> {
    return this.request<Company[]>(`/companies/?skip=${skip}&limit=${limit}`);
  }

  async getCompany(id: number): Promise<Company> {
    return this.request<Company>(`/companies/${id}`);
  }

  // ドキュメント
  async getDocuments(companyId?: number, days = 7): Promise<Document[]> {
    const params = new URLSearchParams();
    if (companyId) params.append("company_id", String(companyId));
    params.append("days", String(days));
    return this.request<Document[]>(`/documents/?${params}`);
  }

  async getDocument(id: number): Promise<Document> {
    return this.request<Document>(`/documents/${id}`);
  }

  // 分析
  async analyzeText(text: string, docType: string): Promise<AnalysisResult> {
    return this.request<AnalysisResult>("/analysis/analyze", {
      method: "POST",
      body: JSON.stringify({ text, doc_type: docType }),
    });
  }

  async analyzeDocument(documentId: number): Promise<AnalysisResult> {
    return this.request<AnalysisResult>("/analysis/analyze-document", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId }),
    });
  }

  async extractPdf(url: string): Promise<{ text: string }> {
    return this.request<{ text: string }>("/analysis/extract-pdf", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  }

  // VTuber
  async generateScript(
    analysisResult: AnalysisResult,
    companyInfo: { name: string; ticker_code: string; sector?: string }
  ): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-script", {
      method: "POST",
      body: JSON.stringify({
        analysis_result: analysisResult,
        company_info: companyInfo,
      }),
    });
  }

  async generateScriptFromDocument(documentId: number): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-script-from-document", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId }),
    });
  }

  // VTuber 台本タイプ
  async getScriptTypes(): Promise<ScriptType[]> {
    const response = await this.request<ScriptTypesResponse>("/vtuber/script-types");
    return response.script_types;
  }

  async generateMorningScript(request: MorningMarketScriptRequest): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-morning-script", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async generateEarningsScript(request: EarningsSeasonScriptRequest): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-earnings-script", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async generateThemeScript(request: ThemeStockScriptRequest): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-theme-script", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async generateTechnicalScript(request: TechnicalAnalysisScriptRequest): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-technical-script", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async generatePortfolioScript(request: PortfolioReviewScriptRequest): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-portfolio-script", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async generateSentimentScript(request: SentimentScriptRequest): Promise<VTuberScript> {
    return this.request<VTuberScript>("/vtuber/generate-sentiment-script", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // クローラー（管理者用）
  async runTdnetCrawler(days = 1): Promise<CrawlResponse> {
    return this.request<CrawlResponse>("/crawlers/tdnet/run", {
      method: "POST",
      body: JSON.stringify({ days }),
    });
  }

  async runEdinetCrawler(days = 1): Promise<CrawlResponse> {
    return this.request<CrawlResponse>("/crawlers/edinet/run", {
      method: "POST",
      body: JSON.stringify({ days }),
    });
  }

  // TTS（音声合成）
  async generateSpeech(
    text: string,
    speakerId?: number
  ): Promise<{ audioBase64: string; durationSeconds: number }> {
    const response = await this.request<{
      audio_base64: string;
      duration_seconds: number;
    }>("/tts/generate", {
      method: "POST",
      body: JSON.stringify({
        text,
        speaker_id: speakerId || 3,
      }),
    });
    return {
      audioBase64: response.audio_base64,
      durationSeconds: response.duration_seconds,
    };
  }

  async getTTSSpeakers(): Promise<
    Array<{
      name: string;
      speaker_uuid: string;
      styles: Array<{ id: number; name: string }>;
    }>
  > {
    return this.request("/tts/speakers");
  }

  async checkTTSHealth(): Promise<{
    status: string;
    voicevox_version?: string;
    voicevox_host: string;
    error?: string;
  }> {
    return this.request("/tts/health");
  }

  // ウォッチリスト
  async createWatchlist(name: string = "メインウォッチリスト"): Promise<Watchlist> {
    return this.request<Watchlist>("/watchlist/", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  }

  async getWatchlists(): Promise<Watchlist[]> {
    return this.request<Watchlist[]>("/watchlist/");
  }

  async getWatchlist(id: number): Promise<WatchlistWithPrices> {
    return this.request<WatchlistWithPrices>(`/watchlist/${id}`);
  }

  async deleteWatchlist(id: number): Promise<void> {
    await this.request(`/watchlist/${id}`, { method: "DELETE" });
  }

  async addWatchlistItem(
    watchlistId: number,
    tickerCode: string,
    targetPriceHigh?: number,
    targetPriceLow?: number,
    notes?: string
  ): Promise<WatchlistItem> {
    return this.request<WatchlistItem>(`/watchlist/${watchlistId}/items`, {
      method: "POST",
      body: JSON.stringify({
        ticker_code: tickerCode,
        target_price_high: targetPriceHigh,
        target_price_low: targetPriceLow,
        notes,
      }),
    });
  }

  async updateWatchlistItem(
    itemId: number,
    data: {
      target_price_high?: number;
      target_price_low?: number;
      notes?: string;
    }
  ): Promise<WatchlistItem> {
    return this.request<WatchlistItem>(`/watchlist/items/${itemId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async removeWatchlistItem(itemId: number): Promise<void> {
    await this.request(`/watchlist/items/${itemId}`, { method: "DELETE" });
  }

  async createAlert(
    itemId: number,
    alertType: AlertType,
    threshold: number
  ): Promise<PriceAlert> {
    return this.request<PriceAlert>(`/watchlist/items/${itemId}/alerts`, {
      method: "POST",
      body: JSON.stringify({ alert_type: alertType, threshold }),
    });
  }

  async deleteAlert(alertId: number): Promise<void> {
    await this.request(`/watchlist/alerts/${alertId}`, { method: "DELETE" });
  }

  async resetAlert(alertId: number): Promise<PriceAlert> {
    return this.request<PriceAlert>(`/watchlist/alerts/${alertId}/reset`, {
      method: "POST",
    });
  }

  async checkAlerts(): Promise<TriggeredAlert[]> {
    return this.request<TriggeredAlert[]>("/watchlist/alerts/check");
  }

  // ML予測
  async getMLPrediction(ticker: string): Promise<MLPrediction> {
    return this.request<MLPrediction>(`/ml/predict/${ticker}`);
  }

  async getMLBatchPrediction(tickers: string[]): Promise<MLBatchPrediction> {
    return this.request<MLBatchPrediction>("/ml/predict/batch", {
      method: "POST",
      body: JSON.stringify({ tickers }),
    });
  }

  async getFeatureImportance(ticker: string): Promise<FeatureImportance> {
    return this.request<FeatureImportance>(`/ml/features/${ticker}`);
  }

  async getModelEvaluation(ticker: string): Promise<ModelEvaluation> {
    return this.request<ModelEvaluation>(`/ml/evaluate/${ticker}`);
  }

  async getIrisMLComment(ticker: string): Promise<IrisMLComment> {
    return this.request<IrisMLComment>(`/ml/iris-comment/${ticker}`);
  }

  // バックテスト
  async getBacktestStrategies(): Promise<BacktestStrategy[]> {
    return this.request<BacktestStrategy[]>("/backtest/strategies");
  }

  async runBacktest(request: BacktestRequest): Promise<BacktestResult> {
    return this.request<BacktestResult>("/backtest/run", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async optimizeBacktest(request: OptimizeRequest): Promise<OptimizeResult> {
    return this.request<OptimizeResult>("/backtest/optimize", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async getBacktestHistory(limit = 20): Promise<BacktestHistoryItem[]> {
    return this.request<BacktestHistoryItem[]>(`/backtest/history?limit=${limit}`);
  }

  async getBacktestResult(id: number): Promise<BacktestResult> {
    return this.request<BacktestResult>(`/backtest/history/${id}`);
  }

  // ポートフォリオ分析
  async analyzePortfolio(positions: PortfolioAnalysisPosition[]): Promise<PortfolioAnalysisResult> {
    return this.request<PortfolioAnalysisResult>("/portfolio/analyze", {
      method: "POST",
      body: JSON.stringify({ positions }),
    });
  }

  async calculateVaR(
    positions: PortfolioAnalysisPosition[],
    confidenceLevel = 0.95,
    timeHorizon = 1,
    method: "historical" | "parametric" | "monte_carlo" = "parametric"
  ): Promise<VaRResult> {
    return this.request<VaRResult>("/portfolio/var", {
      method: "POST",
      body: JSON.stringify({
        positions,
        confidence_level: confidenceLevel,
        time_horizon: timeHorizon,
        method,
      }),
    });
  }

  async getCorrelation(positions: PortfolioAnalysisPosition[]): Promise<CorrelationResult> {
    return this.request<CorrelationResult>("/portfolio/correlation", {
      method: "POST",
      body: JSON.stringify({ positions }),
    });
  }

  async getRebalanceSuggestion(
    positions: PortfolioAnalysisPosition[],
    method: RebalanceMethod,
    constraints?: { max_weight?: number; min_weight?: number }
  ): Promise<RebalanceResult> {
    return this.request<RebalanceResult>("/portfolio/rebalance", {
      method: "POST",
      body: JSON.stringify({ positions, method, constraints }),
    });
  }

  async getEfficientFrontier(
    positions: PortfolioAnalysisPosition[],
    numPortfolios = 50
  ): Promise<EfficientFrontierResult> {
    return this.request<EfficientFrontierResult>("/portfolio/efficient-frontier", {
      method: "POST",
      body: JSON.stringify({ positions, num_portfolios: numPortfolios }),
    });
  }

  async getRiskDecomposition(positions: PortfolioAnalysisPosition[]): Promise<RiskDecompositionResult> {
    return this.request<RiskDecompositionResult>("/portfolio/risk-decomposition", {
      method: "POST",
      body: JSON.stringify({ positions }),
    });
  }
}

export const api = new ApiClient();
