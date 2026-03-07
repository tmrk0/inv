"""
백테스팅 엔진

안전장치:
  1. 거래비용 + 슬리피지 반영
  2. 룩어헤드 바이어스 방지 (신호 1일 shift)
  3. 손절 (stop_loss_pct)
  4. 변동성 기반 포지션 사이징 (ATR)
  5. 종목당 최대 비중 제한 (max_position_pct)
  6. 워크포워드 테스트 (run_walkforward)

생존편향 주의: df는 반드시 분석 시점 기준 생존 종목만 포함하지 않도록
외부에서 관리할 것 (delisted 종목 포함 데이터 사용 권장).
"""
import pandas as pd
import numpy as np
from typing import Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class BacktestResult:
    """백테스팅 결과"""
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    profit_factor: float = 0.0
    equity_curve: pd.Series = field(default_factory=pd.Series)
    trades: list = field(default_factory=list)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range 계산"""
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    close = df["Close"].squeeze()
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def run_backtest(
    df: pd.DataFrame,
    strategy_fn: Callable[[pd.DataFrame], pd.Series],
    initial_capital: float = 10_000_000,
    commission: float = 0.0015,       # 0.15% 수수료 (국내 기준)
    slippage: float = 0.001,          # 0.1% 슬리피지 (호가 스프레드)
    stop_loss_pct: float = 0.05,      # 5% 손절선
    max_position_pct: float = 1.0,    # 종목당 최대 비중 (기본 100%)
    use_atr_sizing: bool = False,     # ATR 기반 포지션 사이징 사용 여부
    atr_risk_pct: float = 0.01,       # ATR 사이징 시 1거래당 리스크 비율
    atr_period: int = 14,
) -> BacktestResult:
    """백테스팅 실행

    Args:
        df: OHLCV DataFrame (Close, High, Low 컬럼 필수)
        strategy_fn: 전략 함수. df → signal Series (1=매수, -1=매도/현금, 0=홀드)
        initial_capital: 초기 자본금 (원)
        commission: 편도 수수료율
        slippage: 편도 슬리피지 (호가 스프레드 근사)
        stop_loss_pct: 진입가 대비 손절 비율 (0.05 = 5%)
        max_position_pct: 종목당 최대 투자 비중 (0~1)
        use_atr_sizing: True면 ATR 기반으로 포지션 크기 자동 조절
        atr_risk_pct: ATR 사이징 시 자본 대비 1거래 허용 리스크
        atr_period: ATR 계산 기간

    Returns:
        BacktestResult
    """
    if df.empty:
        logger.warning("Empty dataframe — backtest skipped")
        return BacktestResult()

    close = df["Close"].squeeze()

    try:
        signals = strategy_fn(df)
    except Exception as e:
        logger.error(f"Strategy function failed: {e}")
        return BacktestResult()

    # [안전장치 2] 룩어헤드 방지: 전략 신호는 다음 날 진입
    direction = signals.shift(1).fillna(0)

    # ATR 계산 (포지션 사이징용)
    atr_series = _compute_atr(df, atr_period) if use_atr_sizing else pd.Series(0.0, index=df.index)

    dates = close.index
    prices = close.values
    directions = direction.values
    atr_values = atr_series.values

    # 시뮬레이션 (루프 기반 — 손절 처리에 필수)
    cash = float(initial_capital)
    shares = 0.0
    entry_price_net = 0.0   # 수수료·슬리피지 포함 실질 진입가
    entry_date = None
    entry_cash = 0.0        # 진입 시 현금 스냅샷 (포지션 사이징 기준)
    in_position = False
    trades = []
    equity_curve = [cash]

    for i in range(1, len(prices)):
        price = prices[i]
        sig = directions[i]

        # [안전장치 3] 손절 체크
        if in_position:
            pnl_pct = (price - entry_price_net) / entry_price_net
            stop_hit = pnl_pct <= -stop_loss_pct
            exit_signal = sig <= 0

            if stop_hit or exit_signal:
                # [안전장치 1] 슬리피지 + 수수료 반영 청산
                exit_price = price * (1 - slippage) * (1 - commission)
                proceeds = shares * exit_price
                cash += proceeds

                gross_return = (price / (entry_price_net / (1 - slippage) / (1 + commission)) - 1) * 100
                net_return = (exit_price / entry_price_net - 1) * 100

                trades.append({
                    "entry_date": entry_date,
                    "exit_date": dates[i],
                    "entry_price": round(entry_price_net, 2),
                    "exit_price": round(exit_price, 2),
                    "return_pct": round(net_return, 3),
                    "stop_loss": bool(stop_hit),
                    "result": "WIN" if net_return > 0 else "LOSS",
                })
                shares = 0.0
                in_position = False

        # 신규 매수 진입
        if not in_position and sig == 1:
            # [안전장치 1] 슬리피지 + 수수료 반영 진입
            entry_price_net = price * (1 + slippage) * (1 + commission)
            entry_date = dates[i]
            entry_cash = cash

            # [안전장치 4,5] 포지션 사이징
            if use_atr_sizing and atr_values[i] > 0:
                # ATR 기반: 1거래 리스크 = atr_risk_pct × 자본 / ATR
                risk_amount = cash * atr_risk_pct
                shares_by_atr = risk_amount / atr_values[i]
                position_value = min(shares_by_atr * price, cash * max_position_pct)
            else:
                position_value = cash * max_position_pct

            shares = position_value / entry_price_net
            cash -= position_value
            in_position = True

        # 일별 자산 평가 (mark-to-market)
        current_equity = cash + shares * price
        equity_curve.append(current_equity)

    equity = pd.Series(equity_curve, index=dates)

    # --- 성과 지표 ---
    result = BacktestResult()
    result.equity_curve = equity
    result.total_return = (equity.iloc[-1] / initial_capital - 1) * 100

    years = len(df) / 252
    result.annualized_return = (
        (equity.iloc[-1] / initial_capital) ** (1 / max(years, 0.1)) - 1
    ) * 100

    eq_ret = equity.pct_change().fillna(0)
    excess = eq_ret - 0.035 / 252
    result.sharpe_ratio = (excess.mean() / (excess.std() + 1e-10)) * np.sqrt(252)

    # 소르티노 (하방 편차 기준)
    downside_std = eq_ret[eq_ret < 0].std() + 1e-10
    result.sortino_ratio = (eq_ret.mean() / downside_std) * np.sqrt(252)

    # MDD
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    result.max_drawdown = float(drawdown.min())

    # 칼마 비율
    result.calmar_ratio = result.annualized_return / (abs(result.max_drawdown) + 1e-10)

    # 거래 통계
    result.trades = trades
    result.total_trades = len(trades)
    if trades:
        rets = [t["return_pct"] for t in trades]
        result.win_rate = sum(1 for r in rets if r > 0) / len(rets) * 100
        result.avg_trade_return = sum(rets) / len(rets)
        gross_win = sum(r for r in rets if r > 0)
        gross_loss = abs(sum(r for r in rets if r < 0))
        result.profit_factor = gross_win / (gross_loss + 1e-10)

    logger.info(
        f"Backtest | Return: {result.total_return:.1f}% | "
        f"Sharpe: {result.sharpe_ratio:.2f} | Sortino: {result.sortino_ratio:.2f} | "
        f"Calmar: {result.calmar_ratio:.2f} | MDD: {result.max_drawdown:.1f}% | "
        f"WinRate: {result.win_rate:.1f}% | Trades: {result.total_trades}"
    )
    return result


def run_walkforward(
    df: pd.DataFrame,
    strategy_fn: Callable[[pd.DataFrame], pd.Series],
    train_periods: int = 252,   # 훈련 구간 (거래일, 기본 1년)
    test_periods: int = 63,     # 테스트 구간 (거래일, 기본 3개월)
    **backtest_kwargs,
) -> dict:
    """워크포워드 테스트 — 훈련/검증 구간 순차 분리

    [안전장치 6] 미래 데이터 유출 없이 out-of-sample 성과 검증.

    Args:
        df: 전체 OHLCV 데이터
        strategy_fn: 전략 함수
        train_periods: 최초 훈련 구간 길이 (이후 확장)
        test_periods: 각 폴드 테스트 구간 길이
        **backtest_kwargs: run_backtest에 전달할 추가 파라미터

    Returns:
        {folds, avg_return, avg_sharpe, avg_max_drawdown, total_folds}
    """
    n = len(df)
    if n < train_periods + test_periods:
        logger.warning(f"워크포워드: 데이터 부족 ({n}일 < {train_periods + test_periods}일)")
        return {"folds": [], "avg_return": 0.0, "avg_sharpe": 0.0, "total_folds": 0}

    folds = []
    fold_idx = 0
    cursor = train_periods

    while cursor + test_periods <= n:
        test_df = df.iloc[cursor: cursor + test_periods]
        result = run_backtest(test_df, strategy_fn, **backtest_kwargs)

        folds.append({
            "fold": fold_idx,
            "train_start": df.index[0].date(),
            "train_end": df.index[cursor - 1].date(),
            "test_start": test_df.index[0].date(),
            "test_end": test_df.index[-1].date(),
            "return_pct": round(result.total_return, 2),
            "sharpe": round(result.sharpe_ratio, 2),
            "max_drawdown": round(result.max_drawdown, 2),
            "trades": result.total_trades,
        })

        cursor += test_periods
        fold_idx += 1

    avg_return = sum(f["return_pct"] for f in folds) / len(folds)
    avg_sharpe = sum(f["sharpe"] for f in folds) / len(folds)
    avg_mdd = sum(f["max_drawdown"] for f in folds) / len(folds)

    logger.info(
        f"워크포워드 {fold_idx}폴드 완료 | "
        f"평균 수익률: {avg_return:.1f}% | 평균 샤프: {avg_sharpe:.2f} | "
        f"평균 MDD: {avg_mdd:.1f}%"
    )

    return {
        "folds": folds,
        "avg_return": round(avg_return, 2),
        "avg_sharpe": round(avg_sharpe, 2),
        "avg_max_drawdown": round(avg_mdd, 2),
        "total_folds": fold_idx,
    }
