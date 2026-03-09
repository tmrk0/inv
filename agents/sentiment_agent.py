"""
감성 분석 에이전트
뉴스 수집 → Claude 감성 분석 → 종합 신호 생성 → 출력
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from core.data.news import fetch_all_news
from core.data.dart import fetch_recent_disclosures
from core.sentiment.analyzer import analyze_batch, get_aggregate_signal


def run_sentiment_agent(
    tickers: list[str],
    ticker_names: list[str],
    include_dart: bool = True,
    news_limit: int = 10,
    market: str = "us",
) -> dict:
    """감성 분석 에이전트 실행

    Args:
        tickers: 종목 코드 리스트 (예: ["SPY", "AAPL"])
        ticker_names: 종목명/키워드 리스트
        include_dart: DART 공시 포함 여부 (한국 종목만 해당)
        news_limit: 피드당 뉴스 수집 수
        market: "us" | "kr" | "all"

    Returns:
        종목별 신호 딕셔너리
    """
    results = {}

    for ticker, name in zip(tickers, ticker_names):
        logger.info(f"\n{'='*50}")
        logger.info(f"Analyzing: {name} ({ticker})")

        # 1. 뉴스 수집
        articles = fetch_all_news(tickers=[name], limit_per_feed=news_limit, market=market)
        logger.info(f"Found {len(articles)} news articles")

        # 2. DART 공시 수집 (선택)
        dart_texts = []
        if include_dart:
            disclosures = fetch_recent_disclosures(page_count=5)
            corp_disclosures = [d for d in disclosures if name in d.get("corp_name", "")]
            for d in corp_disclosures[:3]:
                dart_texts.append({
                    "title": d.get("report_nm", ""),
                    "summary": f"[공시] {d.get('corp_name')} — {d.get('report_nm')}",
                    "link": "",
                    "published": d.get("rcept_dt", ""),
                    "source": "DART",
                })
            logger.info(f"Found {len(dart_texts)} DART disclosures")

        all_texts = articles + dart_texts

        if not all_texts:
            logger.warning(f"No content found for {name}")
            results[ticker] = {"signal": "NEUTRAL", "reason": "No data"}
            continue

        # 3. 감성 분석
        analyzed = analyze_batch(all_texts, ticker=ticker)

        # 4. 종합 신호
        aggregate = get_aggregate_signal(analyzed)
        aggregate["ticker"] = ticker
        aggregate["name"] = name
        aggregate["analyzed_at"] = datetime.now().isoformat()
        aggregate["top_articles"] = [
            {
                "title": a["title"],
                "signal": a["sentiment"]["signal"],
                "score": a["sentiment"]["score"],
                "source": a.get("source", ""),
            }
            for a in sorted(analyzed, key=lambda x: abs(x["sentiment"]["score"]), reverse=True)[:3]
        ]

        results[ticker] = aggregate

    return results


def print_report(results: dict):
    """결과 리포트 출력"""
    print("\n" + "="*60)
    print(f"📊 감성 분석 리포트 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    for ticker, result in results.items():
        signal = result.get("signal", "NEUTRAL")
        score = result.get("avg_score", 0.0)
        name = result.get("name", ticker)

        emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"
        print(f"\n{emoji} {name} ({ticker})")
        print(f"   신호: {signal} | 스코어: {score:+.3f}")
        print(f"   분석 기사: {result.get('article_count', 0)}건 "
              f"(매수:{result.get('buy_count', 0)} "
              f"매도:{result.get('sell_count', 0)} "
              f"중립:{result.get('neutral_count', 0)})")

        top = result.get("top_articles", [])
        if top:
            print("   주요 기사:")
            for a in top[:2]:
                print(f"     [{a['signal']}] {a['title'][:50]}...")


if __name__ == "__main__":
    # 실행 예시
    watchlist_tickers = ["005930", "000660"]
    watchlist_names = ["삼성전자", "SK하이닉스"]

    results = run_sentiment_agent(
        tickers=watchlist_tickers,
        ticker_names=watchlist_names,
        include_dart=False,  # DART_API_KEY 없을 때 False
        news_limit=5,
    )

    print_report(results)

    # JSON 저장
    with open("sentiment_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print("\n✅ 결과 저장: sentiment_result.json")
