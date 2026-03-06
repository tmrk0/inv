"""
매매 신호 실행 스크립트
python scripts/run_signal.py --tickers 005930 000660 --names 삼성전자 SK하이닉스
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.sentiment_agent import run_sentiment_agent, print_report


def main():
    parser = argparse.ArgumentParser(description="감성 기반 매매 신호 생성")
    parser.add_argument("--tickers", nargs="+", default=["005930", "000660"],
                        help="종목 코드 리스트")
    parser.add_argument("--names", nargs="+", default=["삼성전자", "SK하이닉스"],
                        help="종목명 리스트")
    parser.add_argument("--no-dart", action="store_true",
                        help="DART 공시 제외")
    parser.add_argument("--news-limit", type=int, default=10,
                        help="피드당 뉴스 수집 수")
    args = parser.parse_args()

    print(f"🔍 분석 시작: {args.names}")

    results = run_sentiment_agent(
        tickers=args.tickers,
        ticker_names=args.names,
        include_dart=not args.no_dart,
        news_limit=args.news_limit,
    )

    print_report(results)


if __name__ == "__main__":
    main()
