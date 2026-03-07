"""
모멘텀 전략 모음

학술 근거:
  - Jegadeesh & Titman (1993): 12개월 과거 수익률로 미래 수익률 예측
  - Antonacci (2014): 듀얼 모멘텀 (절대+상대)
  - Barroso & Santa-Clara (2015): 변동성 조정 모멘텀

공통 규칙:
  - 최근 1개월 제외 (단기 반전 효과 회피)
  - 절대 모멘텀 음수면 현금 보유 (듀얼 모멘텀)
  - 변동성이 높을수록 신호 약화 (변동성 조정)
"""
import numpy as np
import pandas as pd
from core.strategies.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """12-1 모멘텀 전략 (표준 학술 모멘텀)

    - 과거 lookback일 수익률 계산, 최근 skip일 제외
    - 모멘텀 양수 → 매수, 음수 → 청산(현금)
    - 기본값: 252일(12개월) 기준, 최근 21일(1개월) 제외
    """

    name = "12-1 Momentum"
    description = "Buy if 12-1 month momentum is positive (Jegadeesh & Titman)"

    def __init__(self, lookback: int = 252, skip: int = 21):
        self.lookback = lookback
        self.skip = skip

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"].squeeze()

        # 12개월 전 종가 / 1개월 전 종가 - 1 (최근 1개월 반전 효과 제거)
        momentum = close.shift(self.skip) / close.shift(self.lookback) - 1

        signals = pd.Series(0, index=df.index)
        signals[momentum > 0] = 1    # 모멘텀 양수 → 매수
        signals[momentum <= 0] = -1  # 모멘텀 음수 → 현금 보유

        return signals


class DualMomentumStrategy(BaseStrategy):
    """듀얼 모멘텀 전략 (Gary Antonacci, 2014)

    1. 절대 모멘텀: 자산 수익률 > 무위험 이자율 → 진입 가능
    2. 절대 모멘텀이 무위험 이자율 미만이면 무조건 현금 보유
       (하락장에서 손실 방어 — 시장 중립)

    단일 종목 버전: 절대 모멘텀만 적용.
    다종목 버전에서는 상대 모멘텀으로 상위 종목 선택.
    """

    name = "Dual Momentum"
    description = "Absolute momentum vs risk-free rate (Antonacci 2014)"

    def __init__(self, lookback: int = 252, rf_annual: float = 0.035):
        self.lookback = lookback
        self.rf_period = (1 + rf_annual) ** (lookback / 252) - 1  # 기간 무위험 수익률

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"].squeeze()

        # 절대 모멘텀: 과거 12개월 수익률
        abs_momentum = close / close.shift(self.lookback) - 1

        signals = pd.Series(0, index=df.index)
        # 절대 모멘텀 > 무위험 수익률일 때만 매수
        signals[abs_momentum > self.rf_period] = 1
        # 절대 모멘텀 ≤ 무위험 수익률이면 현금 보유 (하락장 방어)
        signals[abs_momentum <= self.rf_period] = -1

        return signals


class VolAdjMomentumStrategy(BaseStrategy):
    """변동성 조정 모멘텀 전략 (Barroso & Santa-Clara, 2015)

    - 모멘텀 스코어 = 수익률 / 실현변동성
    - 변동성이 높은 시기에 신호 강도 자동 약화
    - 엔진의 ATR 사이징(use_atr_sizing=True)과 함께 사용 권장
    """

    name = "Vol-Adjusted Momentum"
    description = "Momentum / realized volatility (Barroso & Santa-Clara 2015)"

    def __init__(self, lookback: int = 126, vol_window: int = 21, threshold: float = 0.0):
        self.lookback = lookback    # 6개월 모멘텀
        self.vol_window = vol_window
        self.threshold = threshold  # 진입 임계값 (기본 0 = 양수면 매수)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"].squeeze()
        daily_ret = close.pct_change()

        # 6개월 모멘텀
        momentum = close / close.shift(self.lookback) - 1

        # 실현 변동성 (연환산)
        vol = daily_ret.rolling(self.vol_window).std() * np.sqrt(252)

        # 변동성 조정 스코어
        score = momentum / (vol + 1e-10)

        signals = pd.Series(0, index=df.index)
        signals[score > self.threshold] = 1
        signals[score <= self.threshold] = -1

        return signals


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

    from core.data.fetcher import fetch_ohlcv_global
    from core.backtester.engine import run_backtest, run_walkforward

    df = fetch_ohlcv_global("AAPL", "5y")
    if df.empty:
        print("데이터 수집 실패")
        sys.exit(1)

    print(f"데이터: {len(df)}일 ({df.index[0].date()} ~ {df.index[-1].date()})\n")

    strategies = [
        MomentumStrategy(),
        DualMomentumStrategy(),
        VolAdjMomentumStrategy(),
    ]

    for strat in strategies:
        print(f"{'='*50}")
        print(f"전략: {strat.name}")
        result = run_backtest(
            df, strat,
            commission=0.0015,
            slippage=0.001,
            stop_loss_pct=0.10,
            use_atr_sizing=True,
            atr_risk_pct=0.01,
        )
        print(f"  총 수익률:     {result.total_return:+.1f}%")
        print(f"  연환산:        {result.annualized_return:+.1f}%")
        print(f"  샤프:          {result.sharpe_ratio:.2f}")
        print(f"  소르티노:      {result.sortino_ratio:.2f}")
        print(f"  칼마:          {result.calmar_ratio:.2f}")
        print(f"  MDD:           {result.max_drawdown:.1f}%")
        print(f"  승률:          {result.win_rate:.1f}%")
        print(f"  거래 횟수:     {result.total_trades}회")

        print(f"\n  [워크포워드 — {strat.name}]")
        wf = run_walkforward(df, strat, train_periods=252, test_periods=63,
                             commission=0.0015, slippage=0.001, stop_loss_pct=0.10)
        print(f"  폴드 수:       {wf['total_folds']}")
        print(f"  OOS 평균 수익: {wf['avg_return']:+.1f}%")
        print(f"  OOS 평균 샤프: {wf['avg_sharpe']:.2f}")
        print(f"  OOS 평균 MDD:  {wf['avg_max_drawdown']:.1f}%")
