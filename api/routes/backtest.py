"""
백테스팅 API 라우트 (Phase 2에서 완성)
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class BacktestRequest(BaseModel):
    ticker: str
    strategy: str = "ma_cross"   # ma_cross | rsi
    period: str = "1y"
    short_window: int = 20
    long_window: int = 50
    initial_capital: float = 10_000_000


@router.post("/run")
def run_backtest_api(req: BacktestRequest):
    """백테스팅 실행 — Phase 2에서 구현 예정"""
    # TODO: Phase 2 구현
    return {
        "status": "coming_soon",
        "message": "Backtest API — Phase 2",
        "request": req.dict(),
    }
