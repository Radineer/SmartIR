"""
バックテストAPI
トレーディング戦略のバックテスト実行・管理
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.backtest import BacktestJob, BacktestStatus, BacktestTemplate
from app.models.user import User
from app.services.backtest_service import (
    backtest_service,
    BacktestConfig,
    BacktestResult,
    StrategyInfo,
    OptimizationResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])


# ===== Request/Response Models =====

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    """バックテスト実行リクエスト"""
    ticker: str = Field(..., description="ティッカーシンボル（例: 7203.T, ^N225）")
    start_date: str = Field(..., description="開始日（YYYY-MM-DD）")
    end_date: str = Field(..., description="終了日（YYYY-MM-DD）")
    initial_capital: float = Field(default=1000000, description="初期資金（円）")
    strategy: str = Field(..., description="戦略ID（sma_cross, rsi, macd等）")
    params: Dict[str, Any] = Field(default={}, description="戦略パラメータ")
    save_result: bool = Field(default=True, description="結果をDBに保存するか")


class BacktestResponse(BaseModel):
    """バックテスト結果レスポンス"""
    id: Optional[int] = None
    config: BacktestConfig
    result: BacktestResult
    iris_summary: str
    created_at: Optional[str] = None


class BacktestJobResponse(BaseModel):
    """バックテストジョブレスポンス"""
    id: int
    ticker: str
    strategy: str
    status: str
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    created_at: str


class OptimizeRequest(BaseModel):
    """パラメータ最適化リクエスト"""
    ticker: str
    start_date: str
    end_date: str
    initial_capital: float = 1000000
    strategy: str
    param_ranges: Dict[str, List] = Field(
        ...,
        description="最適化するパラメータ範囲（例: {\"short_window\": [5, 10, 15, 20]}）"
    )


class TemplateCreateRequest(BaseModel):
    """テンプレート作成リクエスト"""
    name: str
    description: Optional[str] = None
    strategy: str
    params: Dict[str, Any] = {}
    is_public: bool = False


class TemplateResponse(BaseModel):
    """テンプレートレスポンス"""
    id: int
    name: str
    description: Optional[str]
    strategy: str
    params: Dict[str, Any]
    is_public: bool
    created_at: str


# ===== API Endpoints =====

@router.get("/strategies", response_model=List[StrategyInfo])
async def get_strategies():
    """
    利用可能な戦略一覧を取得

    Returns:
        戦略情報のリスト
    """
    return backtest_service.get_available_strategies()


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRunRequest,
    db: Session = Depends(get_db)
):
    """
    バックテストを実行

    Args:
        request: バックテスト設定
        db: DBセッション

    Returns:
        バックテスト結果
    """
    try:
        # 設定を作成
        config = BacktestConfig(
            ticker=request.ticker,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            strategy=request.strategy,
            params=request.params
        )

        # バックテスト実行
        result = backtest_service.run_backtest(config)

        # イリス用サマリー生成
        iris_summary = backtest_service.generate_iris_summary(result, config)

        job_id = None
        created_at = None

        # DBに保存
        if request.save_result:
            job = BacktestJob(
                ticker=request.ticker,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                strategy=request.strategy,
                params=request.params,
                status=BacktestStatus.COMPLETED,
                total_return=result.total_return,
                annual_return=result.annual_return,
                max_drawdown=result.max_drawdown,
                sharpe_ratio=result.sharpe_ratio,
                win_rate=result.win_rate,
                total_trades=result.total_trades,
                result=result.model_dump(),
                iris_summary=iris_summary
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
            created_at = job.created_at.isoformat()

        return BacktestResponse(
            id=job_id,
            config=config,
            result=result,
            iris_summary=iris_summary,
            created_at=created_at
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {str(e)}")


@router.get("/history", response_model=List[BacktestJobResponse])
async def get_backtest_history(
    ticker: Optional[str] = Query(None, description="ティッカーでフィルタ"),
    strategy: Optional[str] = Query(None, description="戦略でフィルタ"),
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
    db: Session = Depends(get_db)
):
    """
    バックテスト履歴を取得

    Args:
        ticker: ティッカーフィルタ
        strategy: 戦略フィルタ
        limit: 取得件数
        offset: オフセット
        db: DBセッション

    Returns:
        バックテストジョブのリスト
    """
    query = db.query(BacktestJob)

    if ticker:
        query = query.filter(BacktestJob.ticker == ticker)
    if strategy:
        query = query.filter(BacktestJob.strategy == strategy)

    jobs = query.order_by(BacktestJob.created_at.desc()).offset(offset).limit(limit).all()

    return [
        BacktestJobResponse(
            id=job.id,
            ticker=job.ticker,
            strategy=job.strategy,
            status=job.status.value if isinstance(job.status, BacktestStatus) else job.status,
            total_return=job.total_return,
            sharpe_ratio=job.sharpe_ratio,
            created_at=job.created_at.isoformat()
        )
        for job in jobs
    ]


@router.get("/{job_id}", response_model=BacktestResponse)
async def get_backtest_result(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    バックテスト結果を取得

    Args:
        job_id: ジョブID
        db: DBセッション

    Returns:
        バックテスト結果
    """
    job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    if job.status != BacktestStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Backtest is not completed. Status: {job.status.value}"
        )

    config = BacktestConfig(
        ticker=job.ticker,
        start_date=job.start_date,
        end_date=job.end_date,
        initial_capital=job.initial_capital,
        strategy=job.strategy,
        params=job.params or {}
    )

    result = BacktestResult(**job.result)

    return BacktestResponse(
        id=job.id,
        config=config,
        result=result,
        iris_summary=job.iris_summary or "",
        created_at=job.created_at.isoformat()
    )


@router.delete("/{job_id}")
async def delete_backtest(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    バックテスト結果を削除

    Args:
        job_id: ジョブID
        db: DBセッション

    Returns:
        削除結果
    """
    job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    db.delete(job)
    db.commit()

    return {"message": "Backtest deleted successfully", "id": job_id}


@router.post("/optimize", response_model=OptimizationResult)
async def optimize_parameters(
    request: OptimizeRequest,
    db: Session = Depends(get_db)
):
    """
    パラメータ最適化を実行

    Args:
        request: 最適化設定
        db: DBセッション

    Returns:
        最適化結果
    """
    try:
        config = BacktestConfig(
            ticker=request.ticker,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            strategy=request.strategy,
            params={}
        )

        # パラメータ範囲を変換（リストをrangeに変換しない、そのまま使用）
        param_ranges = request.param_ranges

        result = backtest_service.optimize_parameters(config, param_ranges)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.get("/compare/{job_id1}/{job_id2}")
async def compare_backtests(
    job_id1: int,
    job_id2: int,
    db: Session = Depends(get_db)
):
    """
    2つのバックテスト結果を比較

    Args:
        job_id1: 比較対象ジョブID 1
        job_id2: 比較対象ジョブID 2
        db: DBセッション

    Returns:
        比較結果
    """
    job1 = db.query(BacktestJob).filter(BacktestJob.id == job_id1).first()
    job2 = db.query(BacktestJob).filter(BacktestJob.id == job_id2).first()

    if not job1 or not job2:
        raise HTTPException(status_code=404, detail="One or both backtest jobs not found")

    comparison = {
        "job1": {
            "id": job1.id,
            "ticker": job1.ticker,
            "strategy": job1.strategy,
            "total_return": job1.total_return,
            "annual_return": job1.annual_return,
            "max_drawdown": job1.max_drawdown,
            "sharpe_ratio": job1.sharpe_ratio,
            "win_rate": job1.win_rate,
            "total_trades": job1.total_trades
        },
        "job2": {
            "id": job2.id,
            "ticker": job2.ticker,
            "strategy": job2.strategy,
            "total_return": job2.total_return,
            "annual_return": job2.annual_return,
            "max_drawdown": job2.max_drawdown,
            "sharpe_ratio": job2.sharpe_ratio,
            "win_rate": job2.win_rate,
            "total_trades": job2.total_trades
        },
        "diff": {
            "total_return": (job1.total_return or 0) - (job2.total_return or 0),
            "annual_return": (job1.annual_return or 0) - (job2.annual_return or 0),
            "max_drawdown": (job1.max_drawdown or 0) - (job2.max_drawdown or 0),
            "sharpe_ratio": (job1.sharpe_ratio or 0) - (job2.sharpe_ratio or 0),
            "win_rate": (job1.win_rate or 0) - (job2.win_rate or 0),
        },
        "winner": {
            "by_return": job1.id if (job1.total_return or 0) > (job2.total_return or 0) else job2.id,
            "by_sharpe": job1.id if (job1.sharpe_ratio or 0) > (job2.sharpe_ratio or 0) else job2.id,
            "by_drawdown": job1.id if abs(job1.max_drawdown or 0) < abs(job2.max_drawdown or 0) else job2.id,
        }
    }

    return comparison


# ===== Template Endpoints =====

@router.post("/templates", response_model=TemplateResponse)
async def create_template(
    request: TemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    戦略テンプレートを作成

    Args:
        request: テンプレート作成リクエスト
        db: DBセッション
        current_user: 認証済みユーザー

    Returns:
        作成されたテンプレート
    """
    template = BacktestTemplate(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        strategy=request.strategy,
        params=request.params,
        is_public=1 if request.is_public else 0
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        strategy=template.strategy,
        params=template.params or {},
        is_public=template.is_public == 1,
        created_at=template.created_at.isoformat()
    )


@router.get("/templates", response_model=List[TemplateResponse])
async def get_templates(
    include_public: bool = Query(True, description="公開テンプレートを含める"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    戦略テンプレート一覧を取得

    Args:
        include_public: 公開テンプレートを含めるか
        db: DBセッション
        current_user: 認証済みユーザー

    Returns:
        テンプレートのリスト
    """
    query = db.query(BacktestTemplate)

    if include_public:
        query = query.filter(
            (BacktestTemplate.user_id == current_user.id) |
            (BacktestTemplate.is_public == 1)
        )
    else:
        query = query.filter(BacktestTemplate.user_id == current_user.id)

    templates = query.order_by(BacktestTemplate.created_at.desc()).all()

    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            strategy=t.strategy,
            params=t.params or {},
            is_public=t.is_public == 1,
            created_at=t.created_at.isoformat()
        )
        for t in templates
    ]


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    戦略テンプレートを削除

    Args:
        template_id: テンプレートID
        db: DBセッション
        current_user: 認証済みユーザー

    Returns:
        削除結果
    """
    template = db.query(BacktestTemplate).filter(
        BacktestTemplate.id == template_id,
        BacktestTemplate.user_id == current_user.id,
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()

    return {"message": "Template deleted successfully", "id": template_id}


@router.post("/templates/{template_id}/run", response_model=BacktestResponse)
async def run_from_template(
    template_id: int,
    ticker: str = Query(..., description="ティッカーシンボル"),
    start_date: str = Query(..., description="開始日（YYYY-MM-DD）"),
    end_date: str = Query(..., description="終了日（YYYY-MM-DD）"),
    initial_capital: float = Query(1000000, description="初期資金（円）"),
    db: Session = Depends(get_db)
):
    """
    テンプレートからバックテストを実行

    Args:
        template_id: テンプレートID
        ticker: ティッカーシンボル
        start_date: 開始日
        end_date: 終了日
        initial_capital: 初期資金
        db: DBセッション

    Returns:
        バックテスト結果
    """
    template = db.query(BacktestTemplate).filter(BacktestTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # テンプレートからリクエストを作成
    request = BacktestRunRequest(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        strategy=template.strategy,
        params=template.params or {},
        save_result=True
    )

    return await run_backtest(request, db)
