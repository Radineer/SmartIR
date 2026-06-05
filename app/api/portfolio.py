"""
ポートフォリオ分析・リスク管理 API エンドポイント
PySystemTrade的アプローチでVaR、相関分析、リバランス提案を提供
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field

from app.services.portfolio_analyzer import (
    portfolio_analyzer,
    Position,
    PortfolioMetrics,
    CorrelationAnalysis,
    RebalanceSuggestion,
    EfficientFrontierPoint,
    RiskDecomposition,
    SECTOR_INFO,
    SECTOR_MAPPING,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# ==================== リクエスト/レスポンスモデル ====================

class PositionInput(BaseModel):
    """ポジション入力"""
    ticker: str = Field(..., description="ティッカーシンボル（例: 7203.T, AAPL）")
    shares: int = Field(..., gt=0, description="保有株数")
    avg_price: float = Field(..., gt=0, description="平均取得価格")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "7203.T",
                "shares": 100,
                "avg_price": 2500.0
            }
        }


class PortfolioRequest(BaseModel):
    """ポートフォリオ分析リクエスト"""
    positions: List[PositionInput] = Field(..., min_length=1, description="ポジションリスト")

    class Config:
        json_schema_extra = {
            "example": {
                "positions": [
                    {"ticker": "7203.T", "shares": 100, "avg_price": 2500.0},
                    {"ticker": "6758.T", "shares": 50, "avg_price": 12000.0},
                    {"ticker": "9984.T", "shares": 30, "avg_price": 8000.0}
                ]
            }
        }


class VaRRequest(BaseModel):
    """VaR計算リクエスト"""
    positions: List[PositionInput]
    confidence: float = Field(default=0.95, ge=0.9, le=0.99, description="信頼水準")
    method: str = Field(
        default="historical",
        description="計算方法: historical, parametric, montecarlo"
    )


class CorrelationRequest(BaseModel):
    """相関分析リクエスト"""
    tickers: List[str] = Field(..., min_length=2, description="ティッカーリスト")
    days: int = Field(default=252, ge=30, le=1260, description="分析期間（日数）")


class RebalanceRequest(BaseModel):
    """リバランス提案リクエスト"""
    positions: List[PositionInput]
    target_volatility: float = Field(
        default=0.15,
        ge=0.05,
        le=0.50,
        description="目標年率ボラティリティ"
    )
    method: str = Field(
        default="volatility_targeting",
        description="方法: volatility_targeting, equal_weight, risk_parity, min_variance"
    )


class EfficientFrontierRequest(BaseModel):
    """効率的フロンティアリクエスト"""
    tickers: List[str] = Field(..., min_length=2, description="ティッカーリスト")
    n_points: int = Field(default=30, ge=10, le=100, description="ポイント数")


class IrisReviewRequest(BaseModel):
    """イリス向けレビューリクエスト"""
    positions: List[PositionInput]


# ==================== レスポンスモデル ====================

class PortfolioAnalysisResponse(BaseModel):
    """ポートフォリオ分析レスポンス"""
    success: bool
    data: Optional[PortfolioMetrics] = None
    error: Optional[str] = None


class VaRResponse(BaseModel):
    """VaRレスポンス"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class CorrelationResponse(BaseModel):
    """相関分析レスポンス"""
    success: bool
    data: Optional[CorrelationAnalysis] = None
    error: Optional[str] = None


class RebalanceResponse(BaseModel):
    """リバランス提案レスポンス"""
    success: bool
    data: Optional[List[RebalanceSuggestion]] = None
    error: Optional[str] = None


class EfficientFrontierResponse(BaseModel):
    """効率的フロンティアレスポンス"""
    success: bool
    data: Optional[List[EfficientFrontierPoint]] = None
    error: Optional[str] = None


class RiskDecompositionResponse(BaseModel):
    """リスク分解レスポンス"""
    success: bool
    data: Optional[List[RiskDecomposition]] = None
    error: Optional[str] = None


class SectorInfoResponse(BaseModel):
    """セクター情報レスポンス"""
    success: bool
    data: dict


class IrisReviewResponse(BaseModel):
    """イリス向けレビューレスポンス"""
    success: bool
    script: Optional[str] = None
    metrics: Optional[PortfolioMetrics] = None
    suggestions: Optional[List[RebalanceSuggestion]] = None
    error: Optional[str] = None


# ==================== エンドポイント ====================

@router.post("/analyze", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(request: PortfolioRequest):
    """
    ポートフォリオの総合分析

    ポートフォリオの価値、リターン、リスク指標（VaR、ボラティリティ）、
    シャープレシオ、セクター配分などを一括で分析します。

    Args:
        request: ポジションリスト

    Returns:
        ポートフォリオメトリクス

    Example:
        ```json
        {
          "positions": [
            {"ticker": "7203.T", "shares": 100, "avg_price": 2500.0},
            {"ticker": "6758.T", "shares": 50, "avg_price": 12000.0}
          ]
        }
        ```
    """
    try:
        positions = [
            Position(
                ticker=p.ticker,
                shares=p.shares,
                avg_price=p.avg_price
            )
            for p in request.positions
        ]

        metrics = await portfolio_analyzer.analyze_portfolio(positions)

        return PortfolioAnalysisResponse(success=True, data=metrics)

    except ValueError as e:
        return PortfolioAnalysisResponse(success=False, error=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析に失敗しました: {str(e)}")


@router.post("/var", response_model=VaRResponse)
async def calculate_var(request: VaRRequest):
    """
    Value at Risk (VaR) 計算

    指定された信頼水準でのVaR（最大予想損失額）を計算します。

    Args:
        request: ポジションリスト、信頼水準、計算方法

    Methods:
        - historical: ヒストリカルシミュレーション法
        - parametric: パラメトリック法（正規分布仮定）
        - montecarlo: モンテカルロシミュレーション法

    Returns:
        VaR金額と関連情報

    Note:
        VaRは「通常の市場環境下で、指定された信頼水準（例: 95%）で
        1日に被る可能性のある最大損失額」を表します。
    """
    try:
        if request.method not in ["historical", "parametric", "montecarlo"]:
            return VaRResponse(
                success=False,
                error="無効な計算方法です。historical, parametric, montecarlo のいずれかを指定してください"
            )

        positions = [
            Position(
                ticker=p.ticker,
                shares=p.shares,
                avg_price=p.avg_price
            )
            for p in request.positions
        ]

        var_amount = await portfolio_analyzer.calculate_var(
            positions,
            confidence=request.confidence,
            method=request.method
        )

        # 総資産価値も計算
        metrics = await portfolio_analyzer.analyze_portfolio(positions)

        return VaRResponse(
            success=True,
            data={
                "var_amount": var_amount,
                "confidence": request.confidence,
                "method": request.method,
                "portfolio_value": metrics.total_value,
                "var_percentage": round(var_amount / metrics.total_value * 100, 2) if metrics.total_value > 0 else 0,
                "interpretation": f"{request.confidence*100:.0f}%の確率で、1日の損失は{var_amount:,.0f}円以内に収まると推計されます"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VaR計算に失敗しました: {str(e)}")


@router.post("/correlation", response_model=CorrelationResponse)
async def get_correlation_matrix(request: CorrelationRequest):
    """
    相関分析

    指定された銘柄間の相関行列を計算し、分散効果を分析します。

    Args:
        request: ティッカーリスト、分析期間

    Returns:
        相関行列、高相関ペア、分散スコア

    Analysis:
        - highly_correlated_pairs: 相関係数0.7以上の銘柄ペア（分散効果が低い）
        - low_correlated_pairs: 相関係数-0.3〜0.3の銘柄ペア（分散効果が高い）
        - diversification_score: 0-100のスコア（高いほど分散効果が高い）
    """
    try:
        analysis = await portfolio_analyzer.get_correlation_matrix(
            request.tickers,
            days=request.days
        )

        return CorrelationResponse(success=True, data=analysis)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"相関分析に失敗しました: {str(e)}")


@router.post("/rebalance", response_model=RebalanceResponse)
async def suggest_rebalance(request: RebalanceRequest):
    """
    リバランス提案

    指定された方法に基づいてポートフォリオのリバランスを提案します。

    Args:
        request: ポジションリスト、目標ボラティリティ、リバランス方法

    Methods:
        - volatility_targeting: 目標ボラティリティに基づく逆ボラティリティ加重
        - equal_weight: 均等配分
        - risk_parity: リスクパリティ（各銘柄のリスク寄与度を均等化）
        - min_variance: 最小分散ポートフォリオ

    Returns:
        各銘柄の現在ウェイト、目標ウェイト、アクション（buy/sell/hold）、金額
    """
    try:
        if request.method not in ["volatility_targeting", "equal_weight", "risk_parity", "min_variance"]:
            return RebalanceResponse(
                success=False,
                error="無効なリバランス方法です"
            )

        positions = [
            Position(
                ticker=p.ticker,
                shares=p.shares,
                avg_price=p.avg_price
            )
            for p in request.positions
        ]

        suggestions = await portfolio_analyzer.suggest_rebalance(
            positions,
            target_volatility=request.target_volatility,
            method=request.method
        )

        return RebalanceResponse(success=True, data=suggestions)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"リバランス提案に失敗しました: {str(e)}")


@router.post("/efficient-frontier", response_model=EfficientFrontierResponse)
async def calculate_efficient_frontier(request: EfficientFrontierRequest):
    """
    効率的フロンティア計算

    指定された銘柄で構成可能な効率的フロンティアを計算します。

    Args:
        request: ティッカーリスト、ポイント数

    Returns:
        効率的フロンティア上の各ポイント（期待リターン、ボラティリティ、シャープレシオ、ウェイト）

    Theory:
        効率的フロンティアとは、与えられたリスク水準で最大のリターンを達成する
        ポートフォリオの集合です。現代ポートフォリオ理論（MPT）の基礎概念です。
    """
    try:
        frontier = await portfolio_analyzer.calculate_efficient_frontier(
            request.tickers,
            n_points=request.n_points
        )

        return EfficientFrontierResponse(success=True, data=frontier)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"効率的フロンティア計算に失敗しました: {str(e)}")


@router.post("/risk-decomposition", response_model=RiskDecompositionResponse)
async def get_risk_decomposition(request: PortfolioRequest):
    """
    リスク分解分析

    ポートフォリオのリスクを各銘柄に分解し、リスク寄与度を分析します。

    Args:
        request: ポジションリスト

    Returns:
        各銘柄のウェイト、限界VaR、成分VaR、リスク寄与率

    Metrics:
        - marginal_var: 限界VaR（ポジションを1単位増やした時のリスク増加）
        - component_var: 成分VaR（各銘柄のリスク寄与額）
        - contribution_pct: リスク寄与率（%）
    """
    try:
        positions = [
            Position(
                ticker=p.ticker,
                shares=p.shares,
                avg_price=p.avg_price
            )
            for p in request.positions
        ]

        decomposition = await portfolio_analyzer.calculate_risk_decomposition(positions)

        return RiskDecompositionResponse(success=True, data=decomposition)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"リスク分解に失敗しました: {str(e)}")


@router.get("/sectors", response_model=SectorInfoResponse)
async def get_sectors():
    """
    セクター情報一覧

    利用可能なセクター分類とその特性を取得します。

    Returns:
        セクター名、リスク特性、説明
    """
    return SectorInfoResponse(
        success=True,
        data={
            "sector_info": SECTOR_INFO,
            "sector_mapping": SECTOR_MAPPING,
            "total_sectors": len(SECTOR_INFO),
            "total_mapped_tickers": len(SECTOR_MAPPING)
        }
    )


@router.post("/iris-review", response_model=IrisReviewResponse)
async def generate_iris_review(request: IrisReviewRequest):
    """
    イリス向けポートフォリオレビュー生成

    AIキャラクター「イリス」がポートフォリオレビューを行うための
    スクリプトを自動生成します。

    Args:
        request: ポジションリスト

    Returns:
        イリス用スクリプト、メトリクス、リバランス提案
    """
    try:
        positions = [
            Position(
                ticker=p.ticker,
                shares=p.shares,
                avg_price=p.avg_price
            )
            for p in request.positions
        ]

        # 分析実行
        metrics = await portfolio_analyzer.analyze_portfolio(positions)
        suggestions = await portfolio_analyzer.suggest_rebalance(
            positions,
            target_volatility=0.15,
            method="volatility_targeting"
        )

        # スクリプト生成
        script = portfolio_analyzer.generate_iris_portfolio_review(metrics, suggestions)

        return IrisReviewResponse(
            success=True,
            script=script,
            metrics=metrics,
            suggestions=suggestions
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"レビュー生成に失敗しました: {str(e)}")


@router.get("/methods")
async def get_available_methods():
    """
    利用可能な分析・リバランス方法の一覧

    APIで利用可能な各種計算方法とその説明を取得します。

    Returns:
        VaR計算方法、リバランス方法の一覧
    """
    return {
        "var_methods": {
            "historical": {
                "name": "ヒストリカルシミュレーション",
                "description": "過去の実際のリターン分布を使用。分布の形状を仮定しない"
            },
            "parametric": {
                "name": "パラメトリック法",
                "description": "リターンが正規分布に従うと仮定。計算が高速"
            },
            "montecarlo": {
                "name": "モンテカルロシミュレーション",
                "description": "多数のシナリオをシミュレーション。柔軟性が高い"
            }
        },
        "rebalance_methods": {
            "volatility_targeting": {
                "name": "ボラティリティターゲティング",
                "description": "目標ボラティリティに基づき、低ボラ銘柄に多く配分"
            },
            "equal_weight": {
                "name": "均等配分",
                "description": "全銘柄に同じウェイトを配分。シンプルで透明性が高い"
            },
            "risk_parity": {
                "name": "リスクパリティ",
                "description": "各銘柄のリスク寄与度を均等化。分散効果を最大化"
            },
            "min_variance": {
                "name": "最小分散",
                "description": "ポートフォリオ全体の分散を最小化。リスク回避的"
            }
        }
    }
