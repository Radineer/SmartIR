"""
機械学習予測API
株価方向性予測のエンドポイント
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging

from app.services.ml_predictor import (
    ml_predictor_service,
    PredictionResult,
    ModelEvaluation,
    TrainedModelInfo
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml-prediction"])


# Request/Response Models
class TrainRequest(BaseModel):
    """訓練リクエスト"""
    days: int = 756  # 約3年分
    horizon: int = 1  # 1=翌日、5=翌週
    n_splits: int = 5  # クロスバリデーション分割数


class TrainResponse(BaseModel):
    """訓練レスポンス"""
    ticker: str
    accuracy: float
    f1_score: float
    feature_count: int
    train_samples: int
    walk_forward_results: List[dict]
    top_features: dict
    trained_at: str


class BatchPredictionRequest(BaseModel):
    """バッチ予測リクエスト"""
    tickers: List[str]
    horizon: str = "1d"


class BatchPredictionResponse(BaseModel):
    """バッチ予測レスポンス"""
    predictions: List[PredictionResult]
    failed: List[dict]
    timestamp: str


class IrisCommentResponse(BaseModel):
    """イリス向けコメントレスポンス"""
    ticker: str
    comment: str
    prediction: PredictionResult


# Endpoints

@router.get("/predict/{ticker}", response_model=PredictionResult)
async def get_prediction(
    ticker: str,
    horizon: str = Query("1d", description="予測期間: 1d(翌日) or 1w(翌週)")
):
    """
    個別銘柄の方向性予測を取得

    - ticker: ティッカーシンボル（例: 7203.T, AAPL）
    - horizon: 予測期間（1d=翌日、1w=翌週）

    モデルが存在しない場合は自動的に訓練を行います（時間がかかる場合があります）
    """
    try:
        result = await ml_predictor_service.predict(ticker, horizon)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction failed for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post("/predict/batch", response_model=BatchPredictionResponse)
async def batch_prediction(request: BatchPredictionRequest):
    """
    複数銘柄の一括予測

    最大10銘柄まで同時に予測可能
    """
    if len(request.tickers) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 tickers allowed per batch request"
        )

    predictions = []
    failed = []

    for ticker in request.tickers:
        try:
            result = await ml_predictor_service.predict(ticker, request.horizon)
            predictions.append(result)
        except Exception as e:
            failed.append({
                "ticker": ticker,
                "error": str(e)
            })

    return BatchPredictionResponse(
        predictions=predictions,
        failed=failed,
        timestamp=datetime.now().isoformat()
    )


@router.post("/train/{ticker}", response_model=TrainResponse)
async def train_model(
    ticker: str,
    request: TrainRequest = TrainRequest()
):
    """
    モデルの訓練（管理者用）

    ウォークフォワード法で時系列クロスバリデーションを行い、
    XGBoostとLightGBMのアンサンブルモデルを訓練します。

    - ticker: ティッカーシンボル
    - days: 訓練データ期間（デフォルト756日=約3年）
    - horizon: 予測期間（1=翌日、5=翌週）
    - n_splits: クロスバリデーション分割数
    """
    try:
        result = await ml_predictor_service.train_model(
            ticker=ticker,
            days=request.days,
            horizon=request.horizon,
            n_splits=request.n_splits
        )
        return TrainResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Training failed for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Training failed: {str(e)}"
        )


@router.post("/train/{ticker}/background")
async def train_model_background(
    ticker: str,
    background_tasks: BackgroundTasks,
    request: TrainRequest = TrainRequest()
):
    """
    バックグラウンドでモデルを訓練

    訓練はバックグラウンドで実行され、即座にレスポンスが返されます。
    訓練完了後は /api/ml/models エンドポイントで確認できます。
    """
    async def train_task():
        try:
            await ml_predictor_service.train_model(
                ticker=ticker,
                days=request.days,
                horizon=request.horizon,
                n_splits=request.n_splits
            )
            logger.info(f"Background training completed for {ticker}")
        except Exception as e:
            logger.error(f"Background training failed for {ticker}: {e}")

    background_tasks.add_task(train_task)

    return {
        "message": f"Training started for {ticker}",
        "ticker": ticker,
        "status": "training",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/features/{ticker}")
async def get_feature_importance(ticker: str):
    """
    特徴量重要度の取得

    訓練済みモデルの特徴量重要度を返します。
    どのテクニカル指標が予測に寄与しているかを確認できます。
    """
    try:
        importance = await ml_predictor_service.get_feature_importance(ticker)
        return {
            "ticker": ticker,
            "feature_importance": importance,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get feature importance for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feature importance: {str(e)}"
        )


@router.get("/evaluate/{ticker}", response_model=ModelEvaluation)
async def evaluate_model(ticker: str):
    """
    モデル評価指標の取得

    訓練済みモデルの精度、F1スコア、混同行列等を返します。
    ウォークフォワードバリデーションの各フォールド結果も含まれます。
    """
    try:
        evaluation = await ml_predictor_service.evaluate_model(ticker)
        return evaluation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Model evaluation failed for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


@router.get("/models", response_model=List[TrainedModelInfo])
async def list_models():
    """
    利用可能なモデル一覧

    訓練済みの全モデル情報を返します。
    """
    try:
        models = await ml_predictor_service.list_models()
        return models
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/iris-comment/{ticker}", response_model=IrisCommentResponse)
async def get_iris_comment(
    ticker: str,
    horizon: str = Query("1d", description="予測期間")
):
    """
    イリス（AI VTuber）向けの予測コメント取得

    予測結果を自然言語で解説したコメントを生成します。
    AI VTuber配信用のスクリプト素材として使用できます。
    """
    try:
        prediction = await ml_predictor_service.predict(ticker, horizon)
        comment = ml_predictor_service.generate_iris_prediction_comment(prediction)

        return IrisCommentResponse(
            ticker=ticker,
            comment=comment,
            prediction=prediction
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate Iris comment for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate comment: {str(e)}"
        )


@router.get("/health")
async def ml_health_check():
    """
    MLサービスのヘルスチェック
    """
    try:
        models = await ml_predictor_service.list_models()
        return {
            "status": "healthy",
            "models_available": len(models),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
