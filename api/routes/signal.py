"""
매매 신호 API 라우트 (Phase 2에서 완성)
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{ticker}")
def get_signal(ticker: str):
    """종목 매매 신호 조회 — Phase 2에서 구현 예정"""
    return {
        "status": "coming_soon",
        "ticker": ticker,
        "message": "Signal API — Phase 2",
    }
