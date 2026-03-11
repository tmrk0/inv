"""
매매 신호 API
"""
from fastapi import APIRouter, HTTPException, Query
from core.execution.rebalancer import ETFRebalancer

router = APIRouter()


@router.get("/etf")
def get_etf_signal(
    top_n:    int   = Query(2,     description="보유 ETF 수"),
    lookback: int   = Query(126,   description="모멘텀 계산 기간 (거래일)"),
    skip:     int   = Query(21,    description="최근 제외 기간 (거래일)"),
):
    """ETF 듀얼 모멘텀 현재 신호 조회"""
    try:
        rb = ETFRebalancer(top_n=top_n, lookback=lookback, skip=skip)
        return rb.get_signal()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
