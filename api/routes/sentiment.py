"""
감성 분석 API 라우트
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.sentiment.analyzer import analyze_sentiment, analyze_batch, get_aggregate_signal
from core.data.news import fetch_all_news

router = APIRouter()


class SentimentRequest(BaseModel):
    text: str
    ticker: Optional[str] = None


class WatchlistRequest(BaseModel):
    tickers: list[str]
    ticker_names: list[str]
    news_limit: int = 10


@router.post("/analyze")
def analyze_text(req: SentimentRequest):
    """텍스트 직접 감성 분석"""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    result = analyze_sentiment(req.text, ticker=req.ticker)
    return result


@router.post("/watchlist")
def analyze_watchlist(req: WatchlistRequest):
    """관심 종목 감성 분석"""
    if len(req.tickers) != len(req.ticker_names):
        raise HTTPException(status_code=400, detail="tickers and ticker_names must have same length")

    results = {}
    for ticker, name in zip(req.tickers, req.ticker_names):
        articles = fetch_all_news(tickers=[name], limit_per_feed=req.news_limit)
        analyzed = analyze_batch(articles, ticker=ticker)
        aggregate = get_aggregate_signal(analyzed)
        aggregate["ticker"] = ticker
        aggregate["name"] = name
        results[ticker] = aggregate

    return results
