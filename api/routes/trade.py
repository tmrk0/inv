"""
거래 실행 API (KIS 연동)
"""
from fastapi import APIRouter, HTTPException, Query
from core.execution.kis import KISClient
from core.execution.rebalancer import ETFRebalancer

router = APIRouter()


def _get_client() -> KISClient:
    return KISClient()


@router.get("/balance")
def get_balance():
    """계좌 잔고 및 보유 포지션 조회"""
    try:
        return _get_client().get_balance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebalance")
def trigger_rebalance(
    dry_run: bool  = Query(True,  description="True=시뮬레이션, False=실제 주문"),
    top_n:   int   = Query(2,     description="보유 ETF 수"),
):
    """ETF 로테이션 리밸런싱 실행

    - dry_run=true (기본): 주문 목록만 반환, 실제 주문 없음
    - dry_run=false: KIS에 실제 주문 전송
    """
    try:
        kis = _get_client()
        rb  = ETFRebalancer(kis=kis, top_n=top_n)
        result = rb.run(dry_run=dry_run)

        # JSON 직렬화: signal momentum 소수점만 처리하면 됨
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
