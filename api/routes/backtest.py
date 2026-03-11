"""
백테스팅 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.strategies.etf_rotation import run_etf_rotation

router = APIRouter()


class ETFBacktestRequest(BaseModel):
    tickers:                list[str] = ["SPY", "QQQ", "GLD", "TLT", "BIL"]
    period:                 str       = "10y"
    top_n:                  int       = 2
    lookback:               int       = 126
    skip:                   int       = 21
    commission:             float     = 0.001
    slippage:               float     = 0.0005
    initial_capital:        float     = 10_000_000
    use_absolute_momentum:  bool      = True
    rf_annual:              float     = 0.035
    vol_target:             Optional[float] = None


@router.post("/run")
def run_backtest(req: ETFBacktestRequest):
    """ETF 듀얼 모멘텀 로테이션 백테스트 실행"""
    try:
        result = run_etf_rotation(
            tickers               = req.tickers,
            period                = req.period,
            top_n                 = req.top_n,
            lookback              = req.lookback,
            skip                  = req.skip,
            commission            = req.commission,
            slippage              = req.slippage,
            initial_capital       = req.initial_capital,
            use_absolute_momentum = req.use_absolute_momentum,
            rf_annual             = req.rf_annual,
            vol_target            = req.vol_target,
        )
        if not result:
            raise HTTPException(status_code=500, detail="백테스트 실패")

        # equity_curve (pandas Series) → JSON 직렬화
        equity = result["equity_curve"]
        equity_data = [
            {"date": str(d.date()), "value": round(v, 0)}
            for d, v in equity.items()
        ]

        return {
            "total_return":       result["total_return"],
            "annualized_return":  result["annualized_return"],
            "sharpe_ratio":       result["sharpe_ratio"],
            "sortino_ratio":      result["sortino_ratio"],
            "calmar_ratio":       result["calmar_ratio"],
            "max_drawdown":       result["max_drawdown"],
            "total_rebalances":   result["total_rebalances"],
            "rebalance_log":      [
                {**log, "date": str(log["date"])}
                for log in result["rebalance_log"]
            ],
            "equity_curve":       equity_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
