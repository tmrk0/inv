"""
시세 데이터 수집기
- yfinance: 글로벌 주식
- pykrx: 한국 주식 (KRX)
"""
import os
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import yfinance as yf
from loguru import logger

try:
    from pykrx import stock as krx
    KRX_AVAILABLE = True
except ImportError:
    KRX_AVAILABLE = False
    logger.warning("pykrx not available — KRX data disabled")


def fetch_ohlcv_global(ticker: str, period: str = "1y") -> pd.DataFrame:
    """글로벌 주식 OHLCV 수집 (yfinance)

    Args:
        ticker: 티커 (예: "AAPL", "005930.KS")
        period: 기간 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    try:
        df = yf.download(ticker, period=period, progress=False)
        df.index = pd.to_datetime(df.index)
        logger.info(f"Fetched {len(df)} rows for {ticker}")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch {ticker}: {e}")
        return pd.DataFrame()


def fetch_ohlcv_krx(ticker: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    """KRX 한국 주식 OHLCV 수집 (pykrx)

    Args:
        ticker: 종목코드 6자리 (예: "005930" = 삼성전자)
        start: 시작일 "YYYYMMDD" (기본: 1년 전)
        end: 종료일 "YYYYMMDD" (기본: 오늘)

    Returns:
        DataFrame with OHLCV
    """
    if not KRX_AVAILABLE:
        logger.warning("pykrx not available — install with: pip install pykrx")
        return pd.DataFrame()

    if not end:
        end = datetime.today().strftime("%Y%m%d")
    if not start:
        start = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")

    try:
        df = krx.get_market_ohlcv_by_date(start, end, ticker)
        logger.info(f"Fetched KRX {ticker}: {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Failed KRX {ticker}: {e}")
        return pd.DataFrame()


def get_krx_ticker_name(ticker: str) -> str:
    """KRX 종목코드 → 종목명 변환"""
    if not KRX_AVAILABLE:
        return ticker
    try:
        return krx.get_market_ticker_name(ticker)
    except Exception:
        return ticker


if __name__ == "__main__":
    print("=== Global (AAPL) ===")
    df = fetch_ohlcv_global("AAPL", "3mo")
    print(df.tail(3))

    if KRX_AVAILABLE:
        print("\n=== KRX (삼성전자) ===")
        df_krx = fetch_ohlcv_krx("005930")
        print(df_krx.tail(3))
