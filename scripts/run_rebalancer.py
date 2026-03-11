"""
ETF 리밸런서 실행 스크립트

Usage:
    python scripts/run_rebalancer.py              # dry-run (시뮬레이션)
    python scripts/run_rebalancer.py --live       # 실제 주문
    python scripts/run_rebalancer.py --top-n 3    # 보유 ETF 수 변경
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.execution.kis import KISClient
from core.execution.rebalancer import ETFRebalancer


def main():
    parser = argparse.ArgumentParser(description="ETF 듀얼 모멘텀 리밸런서")
    parser.add_argument("--live",   action="store_true", help="실제 주문 실행 (기본: dry-run)")
    parser.add_argument("--top-n",  type=int, default=2, help="보유 ETF 수 (기본: 2)")
    parser.add_argument("--tickers", nargs="+", default=None, help="투자 유니버스 커스텀")
    args = parser.parse_args()

    dry_run = not args.live
    if not dry_run:
        confirm = input("실제 주문을 실행합니다. 계속하시겠습니까? (yes 입력): ")
        if confirm.strip().lower() != "yes":
            print("취소됨.")
            return

    client = KISClient()
    rb = ETFRebalancer(client, tickers=args.tickers, top_n=args.top_n)
    result = rb.run(dry_run=dry_run)

    print("\n=== 결과 ===")
    print(f"목표 포트폴리오: {result['signal']['target']}")
    print(f"현금 전환: {result['signal']['in_cash']}")
    print("\n모멘텀 스코어:")
    for t, m in sorted(result["signal"]["momentum"].items(), key=lambda x: -x[1]):
        print(f"  {t:6s}: {m:+.2%}")

    if result.get("skipped"):
        print("\n포트폴리오 변경 없음 — 리밸런싱 스킵")
        return

    orders = result["orders"]
    if orders["sells"]:
        print(f"\n매도 ({len(orders['sells'])}건):")
        for s in orders["sells"]:
            print(f"  SELL {s['ticker']} {s['qty']}주")
    if orders["buys"]:
        print(f"\n매수 ({len(orders['buys'])}건):")
        for b in orders["buys"]:
            print(f"  BUY  {b['ticker']} {b['qty']}주 @ ${b['estimated_price']:.2f}")

    print(f"\n포트폴리오 총 가치: ${orders['portfolio_value_usd']:,.2f}")


if __name__ == "__main__":
    main()
