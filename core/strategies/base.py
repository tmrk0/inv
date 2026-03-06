"""
전략 베이스 클래스 + 예제 전략들
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """전략 베이스 클래스. 모든 전략은 이를 상속."""

    name: str = "BaseStrategy"
    description: str = ""

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """신호 생성. 반드시 구현 필요.

        Args:
            df: OHLCV DataFrame

        Returns:
            Series: 1=매수, -1=매도, 0=홀드
        """
        pass

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        return self.generate_signals(df)
