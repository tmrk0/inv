"""
매매 신호 실행 스크립트

사용법:
  python scripts/run_signal.py
  python scripts/run_signal.py --tickers AAPL NVDA TSLA --market us
  python scripts/run_signal.py --tickers 005930 000660 --names 삼성전자 SK하이닉스 --market kr --no-dart
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.sentiment_agent import run_sentiment_agent, print_report


def main():
    parser = argparse.ArgumentParser(description="감성 기반 매매 신호 생성")
    parser.add_argument("--tickers", nargs="+", default=["SPY", "QQQ", "AAPL", "NVDA"],
                        help="종목 코드 리스트")
    parser.add_argument("--names", nargs="+", default=None,
                        help="종목명 리스트 (기본: 티커와 동일)")
    parser.add_argument("--market", default="us", choices=["us", "kr", "all"],
                        help="뉴스 마켓 (us/kr/all, 기본: us)")
    parser.add_argument("--no-dart", action="store_true",
                        help="DART 공시 제외")
    parser.add_argument("--news-limit", type=int, default=10,
                        help="피드당 뉴스 수집 수")
    args = parser.parse_args()

    names = args.names or args.tickers

    print(f"분석 시작: {names} (market={args.market})")

    results = run_sentiment_agent(
        tickers=args.tickers,
        ticker_names=names,
        include_dart=not args.no_dart,
        news_limit=args.news_limit,
        market=args.market,
    )

    print_report(results)


if __name__ == "__main__":
    main()
