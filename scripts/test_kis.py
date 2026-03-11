"""
KIS API 연결 테스트 스크립트

Usage:
    python scripts/test_kis.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.execution.kis import KISClient


def main():
    client = KISClient()

    print("\n=== 1. 토큰 발급 ===")
    token = client.get_token()
    print(f"토큰: {token[:20]}...")

    print("\n=== 2. 현재가 조회 (SPY) ===")
    price = client.get_price("SPY")
    print(f"SPY 현재가: ${price['price']:,.2f}")

    print("\n=== 3. 잔고 조회 ===")
    bal = client.get_balance()
    print(f"예수금(USD): ${bal['cash_usd']:,.2f}")
    print(f"보유종목: {len(bal['positions'])}개")
    for p in bal["positions"]:
        print(f"  {p['ticker']}: {p['qty']}주 @ avg ${p['avg_price']:,.2f}")


if __name__ == "__main__":
    main()
