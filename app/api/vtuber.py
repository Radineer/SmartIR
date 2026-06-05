from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time
import logging

from app.core.database import get_db
from app.core.pdf_utils import PDFExtractor
from app.services.llm_analyzer import LLMAnalyzer
from app.services.vtuber_script import VTuberScriptGenerator
from app.services.market_data import market_data_service
from app.models.document import Document
from app.models.company import Company
from app.schemas.vtuber import (
    ScriptGenerationRequest,
    ScriptGenerationFromDocumentRequest,
    ScriptGenerationResponse,
    MorningMarketScriptRequest,
    EarningsSeasonScriptRequest,
    ThemeStockScriptRequest,
    TechnicalAnalysisScriptRequest,
    PortfolioReviewScriptRequest,
    SentimentScriptRequest,
    ScriptTypesResponse,
    ScriptTypeInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vtuber",
    tags=["vtuber"],
    responses={404: {"description": "Not found"}},
)

# サービスのインスタンス
llm_analyzer = LLMAnalyzer()
script_generator = VTuberScriptGenerator()


@router.post("/generate-script", response_model=ScriptGenerationResponse)
def generate_script(request: ScriptGenerationRequest):
    """分析結果から台本を生成"""
    # 分析結果を辞書形式に変換
    analysis_result = {
        "summary": request.analysis_result.summary,
        "sentiment": request.analysis_result.sentiment,
        "key_points": request.analysis_result.key_points,
    }

    # 企業情報を辞書形式に変換
    company_info = {
        "name": request.company_info.name,
        "ticker_code": request.company_info.ticker_code,
        "sector": request.company_info.sector or "不明",
    }

    result = script_generator.generate_script(analysis_result, company_info)

    if result is None:
        raise HTTPException(status_code=500, detail="Script generation failed")

    return ScriptGenerationResponse(
        script=result["script"],
        duration_estimate=result["duration_estimate"],
        character_name=result["character_name"],
        company_name=result["company_name"],
        script_type="ir_document",
        title=f"{result['company_name']}のIR解説",
    )


@router.post("/generate-script-from-document", response_model=ScriptGenerationResponse)
def generate_script_from_document(
    request: ScriptGenerationFromDocumentRequest,
    db: Session = Depends(get_db)
):
    """ドキュメントIDから台本を生成（PDF抽出→分析→台本生成）"""
    # ドキュメント取得
    document = db.query(Document).filter(Document.id == request.document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 企業情報取得
    company = db.query(Company).filter(Company.id == document.company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # テキスト取得または抽出
    text = document.raw_text
    if not text and document.source_url:
        text = PDFExtractor.extract_from_url(document.source_url)
        if text:
            document.raw_text = text
            document.is_processed = True
            db.commit()

    if not text:
        raise HTTPException(status_code=400, detail="No text available for analysis")

    # 分析実行
    analysis_result = llm_analyzer.analyze(text, document.doc_type.value)
    if analysis_result is None:
        raise HTTPException(status_code=500, detail="Analysis failed")

    # 企業情報を辞書形式に変換
    company_info = {
        "name": company.name,
        "ticker_code": company.ticker_code,
        "sector": company.sector or "不明",
    }

    # 台本生成
    result = script_generator.generate_script(analysis_result, company_info)

    if result is None:
        raise HTTPException(status_code=500, detail="Script generation failed")

    return ScriptGenerationResponse(
        script=result["script"],
        duration_estimate=result["duration_estimate"],
        character_name=result["character_name"],
        company_name=result["company_name"],
        script_type="ir_document",
        title=f"{result['company_name']}の決算解説",
    )


@router.get("/script-types", response_model=ScriptTypesResponse)
def get_script_types():
    """利用可能な台本タイプ一覧を取得"""
    types = script_generator.get_script_types()
    return ScriptTypesResponse(
        script_types=[ScriptTypeInfo(**t) for t in types]
    )


@router.post("/generate-morning-script", response_model=ScriptGenerationResponse)
async def generate_morning_script(request: MorningMarketScriptRequest):
    """朝の市況サマリー台本を生成"""
    try:
        # 市況データを取得
        market_summary = market_data_service.get_market_summary()

        # 指数と為替をdictに変換
        indices_data = [
            {
                "name": idx.name,
                "price": idx.price,
                "change": idx.change,
                "change_percent": idx.change_percent
            }
            for idx in market_summary.indices
        ]

        currencies_data = [
            {
                "name": curr.name,
                "price": curr.price,
                "change": curr.change,
                "change_percent": curr.change_percent
            }
            for curr in market_summary.currencies
        ]

        market_data = {
            "indices": indices_data,
            "currencies": currencies_data,
            "previous_day_summary": request.previous_day_summary or "",
            "today_events": request.today_events or "",
        }

        result = await script_generator.generate_morning_market_script(market_data)

        if result is None:
            raise HTTPException(status_code=500, detail="Morning script generation failed")

        return ScriptGenerationResponse(
            script=result["script"],
            duration_estimate=result["duration_estimate"],
            character_name=result["character_name"],
            company_name="",
            script_type=result["script_type"],
            title=result["title"],
        )
    except Exception as e:
        logger.error(f"Morning script generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-earnings-script", response_model=ScriptGenerationResponse)
async def generate_earnings_script(request: EarningsSeasonScriptRequest):
    """決算シーズン特集台本を生成"""
    try:
        # 決算データが提供されていない場合は空のリストを使用
        earnings_data = request.earnings_data or []

        result = await script_generator.generate_earnings_season_script(
            tickers=request.tickers,
            earnings_data=earnings_data
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Earnings script generation failed")

        return ScriptGenerationResponse(
            script=result["script"],
            duration_estimate=result["duration_estimate"],
            character_name=result["character_name"],
            company_name="",
            script_type=result["script_type"],
            title=result["title"],
        )
    except Exception as e:
        logger.error(f"Earnings script generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-theme-script", response_model=ScriptGenerationResponse)
async def generate_theme_script(request: ThemeStockScriptRequest):
    """テーマ株特集台本を生成"""
    try:
        # テーマ株データが提供されていない場合は空のリストを使用
        theme_stocks = request.theme_stocks or []

        result = await script_generator.generate_theme_stock_script(
            theme=request.theme,
            theme_stocks=theme_stocks
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Theme script generation failed")

        return ScriptGenerationResponse(
            script=result["script"],
            duration_estimate=result["duration_estimate"],
            character_name=result["character_name"],
            company_name="",
            script_type=result["script_type"],
            title=result["title"],
        )
    except Exception as e:
        logger.error(f"Theme script generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-technical-script", response_model=ScriptGenerationResponse)
async def generate_technical_script(request: TechnicalAnalysisScriptRequest):
    """テクニカル分析解説台本を生成"""
    try:
        # 銘柄情報を取得（提供されていない場合はmarket_dataから取得を試みる）
        stock_info = request.stock_info or {}
        if not stock_info:
            quote = market_data_service.get_quote(request.ticker)
            if quote:
                stock_info = {
                    "name": quote.name,
                    "price": quote.price,
                    "change": quote.change,
                    "change_percent": quote.change_percent,
                }

        # チャートデータ（提供されていない場合はダミーデータ）
        chart_data = request.chart_data or {}

        result = await script_generator.generate_technical_analysis_script(
            ticker=request.ticker,
            stock_info=stock_info,
            chart_data=chart_data
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Technical script generation failed")

        return ScriptGenerationResponse(
            script=result["script"],
            duration_estimate=result["duration_estimate"],
            character_name=result["character_name"],
            company_name=stock_info.get("name", ""),
            script_type=result["script_type"],
            title=result["title"],
        )
    except Exception as e:
        logger.error(f"Technical script generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-portfolio-script", response_model=ScriptGenerationResponse)
async def generate_portfolio_script(request: PortfolioReviewScriptRequest):
    """週間ポートフォリオレビュー台本を生成"""
    try:
        result = await script_generator.generate_weekly_portfolio_review_script(
            positions=request.positions,
            portfolio_summary=request.portfolio_summary
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Portfolio script generation failed")

        return ScriptGenerationResponse(
            script=result["script"],
            duration_estimate=result["duration_estimate"],
            character_name=result["character_name"],
            company_name="",
            script_type=result["script_type"],
            title=result["title"],
        )
    except Exception as e:
        logger.error(f"Portfolio script generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-sentiment-script", response_model=ScriptGenerationResponse)
async def generate_sentiment_script(request: SentimentScriptRequest):
    """市場心理解説台本を生成"""
    try:
        sentiment_data = {
            "fear_greed_index": request.fear_greed_index,
            "change": request.change,
            "week_ago": request.week_ago,
            "month_ago": request.month_ago,
            "momentum": request.momentum,
            "strength": request.strength,
            "breadth": request.breadth,
            "put_call": request.put_call,
            "vix": request.vix,
            "safe_haven": request.safe_haven,
            "junk_bond": request.junk_bond,
        }

        result = await script_generator.generate_fear_greed_commentary_script(sentiment_data)

        if result is None:
            raise HTTPException(status_code=500, detail="Sentiment script generation failed")

        return ScriptGenerationResponse(
            script=result["script"],
            duration_estimate=result["duration_estimate"],
            character_name=result["character_name"],
            company_name="",
            script_type=result["script_type"],
            title=result["title"],
        )
    except Exception as e:
        logger.error(f"Sentiment script generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
