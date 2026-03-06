"""
예제 전략: 이동평균 골든/데드크로스
"""
import pandas as pd
from core.strategies.base import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """단순 이동평균 크로스오버 전략
    
    - 단기 MA가 장기 MA를 상향 돌파 → 매수
    - 단기 MA가 장기 MA를 하향 돌파 → 매도
    """

    name = "MA Crossover"
    description = "Short-term MA crosses above/below long-term MA"

    def __init__(self, short_window: int = 20, long_window: int = 50):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"].squeeze()
        ma_short = close.rolling(self.short_window).mean()
        ma_long = close.rolling(self.long_window).mean()

        signals = pd.Series(0, index=df.index)
        signals[ma_short > ma_long] = 1   # 매수 포지션
        signals[ma_short < ma_long] = -1  # 매도 포지션

        return signals


class RSIStrategy(BaseStrategy):
    """RSI 과매수/과매도 반전 전략

    - RSI < 30 → 매수
    - RSI > 70 → 매도
    """

    name = "RSI Mean Reversion"
    description = "Buy oversold (RSI<30), sell overbought (RSI>70)"

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df["Close"].squeeze()
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        signals = pd.Series(0, index=df.index)
        signals[rsi < self.oversold] = 1    # 매수
        signals[rsi > self.overbought] = -1  # 매도

        return signals


if __name__ == "__main__":
    # 테스트
    import sys
    sys.path.insert(0, "../../..")
    from core.data.fetcher import fetch_ohlcv_global
    from core.backtester.engine import run_backtest

    df = fetch_ohlcv_global("AAPL", "2y")
    if not df.empty:
        strategy = MACrossStrategy(short_window=20, long_window=50)
        result = run_backtest(df, strategy)
        print(f"Total Return: {result.total_return:.1f}%")
        print(f"Sharpe: {result.sharpe_ratio:.2f}")
        print(f"MDD: {result.max_drawdown:.1f}%")
        print(f"Win Rate: {result.win_rate:.1f}%")
