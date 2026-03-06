"""
백테스팅 엔진
전략 함수를 받아 과거 데이터로 성과를 시뮬레이션
"""
import pandas as pd
import numpy as np
from typing import Callable, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class BacktestResult:
    """백테스팅 결과"""
    total_return: float = 0.0        # 총 수익률 (%)
    annualized_return: float = 0.0   # 연환산 수익률 (%)
    sharpe_ratio: float = 0.0        # 샤프 지수
    max_drawdown: float = 0.0        # 최대 낙폭 (%)
    win_rate: float = 0.0            # 승률 (%)
    total_trades: int = 0            # 총 거래 횟수
    equity_curve: pd.Series = field(default_factory=pd.Series)  # 자산 곡선
    trades: list = field(default_factory=list)                   # 거래 내역


def run_backtest(
    df: pd.DataFrame,
    strategy_fn: Callable[[pd.DataFrame], pd.Series],
    initial_capital: float = 10_000_000,  # 1천만원
    commission: float = 0.0015,           # 0.15% 수수료
) -> BacktestResult:
    """백테스팅 실행

    Args:
        df: OHLCV DataFrame (Close 컬럼 필수)
        strategy_fn: 전략 함수. df를 받아 signal Series 반환
                     signal: 1=매수, -1=매도, 0=홀드
        initial_capital: 초기 자본금 (원)
        commission: 거래 수수료율

    Returns:
        BacktestResult
    """
    if df.empty:
        logger.warning("Empty dataframe — backtest skipped")
        return BacktestResult()

    close = df["Close"].squeeze()

    # 전략 신호 생성
    try:
        signals = strategy_fn(df)
    except Exception as e:
        logger.error(f"Strategy function failed: {e}")
        return BacktestResult()

    # 포지션 계산 (신호 기반)
    position = signals.shift(1).fillna(0)  # 다음 날 진입 (룩어헤드 방지)

    # 수익률 계산
    daily_returns = close.pct_change().fillna(0)
    strategy_returns = position * daily_returns - abs(position.diff().fillna(0)) * commission

    # 자산 곡선
    equity = (1 + strategy_returns).cumprod() * initial_capital

    # 성과 지표
    result = BacktestResult()
    result.equity_curve = equity
    result.total_return = (equity.iloc[-1] / initial_capital - 1) * 100

    # 연환산 수익률
    years = len(df) / 252
    result.annualized_return = ((equity.iloc[-1] / initial_capital) ** (1 / max(years, 0.1)) - 1) * 100

    # 샤프 비율 (연환산, 무위험이자율 3.5% 가정)
    excess_returns = strategy_returns - 0.035 / 252
    result.sharpe_ratio = (excess_returns.mean() / (excess_returns.std() + 1e-10)) * np.sqrt(252)

    # 최대 낙폭 (MDD)
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    result.max_drawdown = drawdown.min()

    # 거래 내역 집계
    trades = []
    in_position = False
    entry_price = 0.0
    entry_date = None

    for date, (sig, price) in enumerate(zip(position, close)):
        if sig == 1 and not in_position:
            in_position = True
            entry_price = price
            entry_date = close.index[date]
        elif sig <= 0 and in_position:
            exit_price = price
            trade_return = (exit_price / entry_price - 1) * 100
            trades.append({
                "entry_date": entry_date,
                "exit_date": close.index[date],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return_pct": trade_return,
                "result": "WIN" if trade_return > 0 else "LOSS",
            })
            in_position = False

    result.trades = trades
    result.total_trades = len(trades)
    result.win_rate = (
        sum(1 for t in trades if t["result"] == "WIN") / len(trades) * 100
        if trades else 0.0
    )

    logger.info(
        f"Backtest done | Return: {result.total_return:.1f}% | "
        f"Sharpe: {result.sharpe_ratio:.2f} | MDD: {result.max_drawdown:.1f}% | "
        f"WinRate: {result.win_rate:.1f}%"
    )
    return result
