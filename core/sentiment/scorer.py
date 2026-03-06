"""
매매 신호 생성기
감성 분석 스코어 + 기술적 지표 → 최종 매매 신호
"""
import pandas as pd
import numpy as np
from typing import Optional
from loguru import logger


def compute_technical_score(df: pd.DataFrame) -> dict:
    """기술적 지표 기반 스코어 계산

    Args:
        df: OHLCV DataFrame (Close 컬럼 필수)

    Returns:
        {score: -1~1, signals: {...}}
    """
    if df.empty or "Close" not in df.columns:
        return {"score": 0.0, "signals": {}}

    close = df["Close"].squeeze()
    signals = {}
    scores = []

    # 1. 이동평균 골든/데드크로스
    if len(close) >= 50:
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        if ma20.iloc[-1] > ma50.iloc[-1]:
            signals["ma_cross"] = "GOLDEN"
            scores.append(0.5)
        else:
            signals["ma_cross"] = "DEAD"
            scores.append(-0.5)

    # 2. RSI (14일)
    if len(close) >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        signals["rsi"] = round(rsi_val, 1)

        if rsi_val < 30:
            scores.append(0.7)   # 과매도 → 매수 신호
        elif rsi_val > 70:
            scores.append(-0.7)  # 과매수 → 매도 신호
        else:
            scores.append(0.0)

    # 3. 볼린저 밴드
    if len(close) >= 20:
        ma = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = ma + 2 * std
        lower = ma - 2 * std
        current = close.iloc[-1]

        if current < lower.iloc[-1]:
            signals["bollinger"] = "OVERSOLD"
            scores.append(0.6)
        elif current > upper.iloc[-1]:
            signals["bollinger"] = "OVERBOUGHT"
            scores.append(-0.6)
        else:
            signals["bollinger"] = "NORMAL"
            scores.append(0.0)

    avg_score = float(np.mean(scores)) if scores else 0.0
    return {"score": round(avg_score, 3), "signals": signals}


def combine_signals(
    sentiment_score: float,
    technical_score: float,
    sentiment_weight: float = 0.4,
    technical_weight: float = 0.6,
) -> dict:
    """감성 스코어 + 기술적 스코어 결합 → 최종 신호

    Args:
        sentiment_score: 감성 분석 스코어 (-1 ~ 1)
        technical_score: 기술적 지표 스코어 (-1 ~ 1)
        sentiment_weight: 감성 가중치 (기본 0.4)
        technical_weight: 기술적 가중치 (기본 0.6)

    Returns:
        {final_signal, final_score, breakdown}
    """
    total_weight = sentiment_weight + technical_weight
    final_score = (
        sentiment_score * sentiment_weight + technical_score * technical_weight
    ) / total_weight

    if final_score >= 0.35:
        signal = "BUY"
        strength = "STRONG" if final_score >= 0.65 else "WEAK"
    elif final_score <= -0.35:
        signal = "SELL"
        strength = "STRONG" if final_score <= -0.65 else "WEAK"
    else:
        signal = "NEUTRAL"
        strength = "NEUTRAL"

    result = {
        "final_signal": signal,
        "signal_strength": strength,
        "final_score": round(final_score, 3),
        "breakdown": {
            "sentiment_score": sentiment_score,
            "technical_score": technical_score,
            "sentiment_weight": sentiment_weight,
            "technical_weight": technical_weight,
        },
    }

    logger.info(f"Combined signal: {signal} ({strength}) score={final_score:.3f}")
    return result


if __name__ == "__main__":
    # 테스트
    tech = compute_technical_score(pd.DataFrame())  # 빈 데이터 테스트
    result = combine_signals(sentiment_score=0.7, technical_score=0.4)
    print(result)
