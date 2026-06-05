from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ScriptType(str, Enum):
    """台本タイプ"""
    IR_DOCUMENT = "ir_document"
    MORNING_MARKET = "morning_market"
    EARNINGS_SEASON = "earnings_season"
    THEME_STOCK = "theme_stock"
    TECHNICAL_ANALYSIS = "technical_analysis"
    PORTFOLIO_REVIEW = "portfolio_review"
    FEAR_GREED_COMMENTARY = "fear_greed_commentary"


class CompanyInfo(BaseModel):
    """企業情報（台本生成用）"""
    name: str = Field(..., description="企業名")
    ticker_code: str = Field(..., description="証券コード")
    sector: Optional[str] = Field(None, description="業種")


class AnalysisResult(BaseModel):
    """分析結果（台本生成用）"""
    summary: str = Field(..., description="要約")
    sentiment: Dict[str, float] = Field(..., description="センチメント")
    key_points: List[str] = Field(..., description="重要ポイント")


class ScriptGenerationRequest(BaseModel):
    """台本生成リクエスト"""
    analysis_result: AnalysisResult = Field(..., description="分析結果")
    company_info: CompanyInfo = Field(..., description="企業情報")
    character_name: Optional[str] = Field(default="アイリス", description="キャラクター名")

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_result": {
                    "summary": "2024年度決算は好調で...",
                    "sentiment": {
                        "positive": 0.7,
                        "negative": 0.1,
                        "neutral": 0.2
                    },
                    "key_points": [
                        "1. 売上高15%増",
                        "2. 営業利益20%増",
                        "3. 配当金増額"
                    ]
                },
                "company_info": {
                    "name": "サンプル企業",
                    "ticker_code": "1234",
                    "sector": "テクノロジー"
                }
            }
        }


class ScriptGenerationFromDocumentRequest(BaseModel):
    """ドキュメントIDから台本生成リクエスト"""
    document_id: int = Field(..., description="ドキュメントID")
    character_name: Optional[str] = Field(default="アイリス", description="キャラクター名")


class ScriptGenerationResponse(BaseModel):
    """台本生成レスポンス"""
    script: str = Field(..., description="生成された台本")
    duration_estimate: str = Field(..., description="推定時間")
    character_name: str = Field(..., description="キャラクター名")
    company_name: str = Field(default="", description="企業名")
    script_type: str = Field(default="ir_document", description="台本タイプ")
    title: str = Field(default="", description="台本タイトル")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="生成日時")

    class Config:
        json_schema_extra = {
            "example": {
                "script": "皆さん、こんにちは！イリスです！...",
                "duration_estimate": "5分",
                "character_name": "イリス",
                "company_name": "サンプル企業",
                "script_type": "ir_document",
                "title": "サンプル企業の決算解説",
                "generated_at": "2024-01-01T12:00:00"
            }
        }


# 朝の市況サマリー用リクエスト
class MorningMarketScriptRequest(BaseModel):
    """朝の市況サマリー台本生成リクエスト"""
    previous_day_summary: Optional[str] = Field(None, description="前日のポイント")
    today_events: Optional[str] = Field(None, description="今日の注目イベント")


# 決算シーズン特集用リクエスト
class EarningsSeasonScriptRequest(BaseModel):
    """決算シーズン特集台本生成リクエスト"""
    tickers: List[str] = Field(..., description="対象銘柄のティッカーコードリスト")
    earnings_data: Optional[List[Dict[str, Any]]] = Field(None, description="決算データ")

    class Config:
        json_schema_extra = {
            "example": {
                "tickers": ["7203.T", "6758.T", "9984.T"],
                "earnings_data": [
                    {
                        "ticker": "7203.T",
                        "name": "トヨタ自動車",
                        "revenue": "45兆円",
                        "revenue_yoy": 15,
                        "operating_income": "5兆円",
                        "oi_yoy": 20,
                        "net_income": "4兆円",
                        "ni_yoy": 18,
                        "vs_consensus": "上回る"
                    }
                ]
            }
        }


# テーマ株特集用リクエスト
class ThemeStockScriptRequest(BaseModel):
    """テーマ株特集台本生成リクエスト"""
    theme: str = Field(..., description="テーマ名")
    theme_stocks: Optional[List[Dict[str, Any]]] = Field(None, description="関連銘柄データ")

    class Config:
        json_schema_extra = {
            "example": {
                "theme": "AI関連",
                "theme_stocks": [
                    {
                        "ticker": "6758.T",
                        "name": "ソニーグループ",
                        "sector": "電気機器",
                        "price": 15000,
                        "theme_relation": "AI搭載カメラ、センサー技術"
                    }
                ]
            }
        }


# テクニカル分析用リクエスト
class TechnicalAnalysisScriptRequest(BaseModel):
    """テクニカル分析台本生成リクエスト"""
    ticker: str = Field(..., description="ティッカーコード")
    stock_info: Optional[Dict[str, Any]] = Field(None, description="銘柄情報")
    chart_data: Optional[Dict[str, Any]] = Field(None, description="チャートデータ")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "7203.T",
                "stock_info": {
                    "name": "トヨタ自動車",
                    "price": 3000,
                    "change": 50,
                    "change_percent": 1.7
                },
                "chart_data": {
                    "ma5": 2950,
                    "ma25": 2900,
                    "ma75": 2800,
                    "rsi14": 55,
                    "macd": "ゴールデンクロス形成中",
                    "bollinger": "中央付近",
                    "volume_trend": "増加傾向",
                    "pattern": "上昇トレンド継続"
                }
            }
        }


# ポートフォリオレビュー用リクエスト
class PortfolioReviewScriptRequest(BaseModel):
    """ポートフォリオレビュー台本生成リクエスト"""
    positions: List[Dict[str, Any]] = Field(..., description="保有銘柄リスト")
    portfolio_summary: Dict[str, Any] = Field(..., description="ポートフォリオサマリー")

    class Config:
        json_schema_extra = {
            "example": {
                "positions": [
                    {
                        "ticker": "7203.T",
                        "name": "トヨタ自動車",
                        "quantity": 100,
                        "avg_cost": 2800,
                        "current_price": 3000,
                        "unrealized_pnl": 20000,
                        "pnl_percent": 7.14
                    }
                ],
                "portfolio_summary": {
                    "total_value": 1000000,
                    "weekly_pnl": 50000,
                    "weekly_return": 5.0,
                    "ytd_return": 15.0,
                    "max_drawdown": -8.0,
                    "sharpe_ratio": 1.5,
                    "beta": 0.9
                }
            }
        }


# 市場心理解説用リクエスト
class SentimentScriptRequest(BaseModel):
    """市場心理解説台本生成リクエスト"""
    fear_greed_index: Optional[int] = Field(50, description="恐怖強欲指数（0-100）")
    change: Optional[float] = Field(None, description="前日比")
    week_ago: Optional[int] = Field(None, description="1週間前の値")
    month_ago: Optional[int] = Field(None, description="1ヶ月前の値")
    momentum: Optional[str] = Field(None, description="株価モメンタム")
    strength: Optional[str] = Field(None, description="株価強度")
    breadth: Optional[str] = Field(None, description="株価幅")
    put_call: Optional[str] = Field(None, description="プット/コール比率")
    vix: Optional[float] = Field(None, description="VIX指数")
    safe_haven: Optional[str] = Field(None, description="セーフヘイブン需要")
    junk_bond: Optional[str] = Field(None, description="ジャンク債需要")

    class Config:
        json_schema_extra = {
            "example": {
                "fear_greed_index": 35,
                "change": -5,
                "week_ago": 45,
                "month_ago": 60,
                "momentum": "弱気",
                "vix": 22.5
            }
        }


# 台本タイプ情報
class ScriptTypeInfo(BaseModel):
    """台本タイプ情報"""
    id: str = Field(..., description="台本タイプID")
    name: str = Field(..., description="台本タイプ名")
    description: str = Field(..., description="説明")
    duration: str = Field(..., description="推定時間")
    required_inputs: List[str] = Field(..., description="必須入力項目")
    icon: str = Field(..., description="アイコン名")


class ScriptTypesResponse(BaseModel):
    """台本タイプ一覧レスポンス"""
    script_types: List[ScriptTypeInfo] = Field(..., description="台本タイプ一覧")
