"""
백테스팅 실행 스크립트
python scripts/run_backtest.py --ticker AAPL --strategy ma_cross --period 2y
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.fetcher import fetch_ohlcv_global, fetch_ohlcv_krx
from core.backtester.engine import run_backtest
from core.strategies.examples.ma_cross import MACrossStrategy, RSIStrategy


STRATEGIES = {
    "ma_cross": MACrossStrategy,
    "rsi": RSIStrategy,
}


def main():
    parser = argparse.ArgumentParser(description="백테스팅 실행")
    parser.add_argument("--ticker", default="AAPL", help="티커 (예: AAPL, 005930)")
    parser.add_argument("--market", choices=["global", "krx"], default="global")
    parser.add_argument("--strategy", choices=list(STRATEGIES.keys()), default="ma_cross")
    parser.add_argument("--period", default="2y", help="기간 (글로벌 전용)")
    parser.add_argument("--capital", type=float, default=10_000_000, help="초기 자본 (원)")
    args = parser.parse_args()

    print(f"📈 백테스팅 시작: {args.ticker} | 전략: {args.strategy}")

    # 데이터 수집
    if args.market == "krx":
        df = fetch_ohlcv_krx(args.ticker)
    else:
        df = fetch_ohlcv_global(args.ticker, args.period)

    if df.empty:
        print("❌ 데이터를 가져올 수 없습니다.")
        return

    print(f"✅ 데이터: {len(df)}일 ({df.index[0].date()} ~ {df.index[-1].date()})")

    # 전략 실행
    strategy_cls = STRATEGIES[args.strategy]
    strategy = strategy_cls()
    result = run_backtest(df, strategy, initial_capital=args.capital)

    # 결과 출력
    print("\n" + "="*40)
    print(f"📊 백테스팅 결과: {strategy.name}")
    print("="*40)
    print(f"  총 수익률:      {result.total_return:+.1f}%")
    print(f"  연환산 수익률:  {result.annualized_return:+.1f}%")
    print(f"  샤프 비율:      {result.sharpe_ratio:.2f}")
    print(f"  최대 낙폭(MDD): {result.max_drawdown:.1f}%")
    print(f"  승률:           {result.win_rate:.1f}%")
    print(f"  총 거래 횟수:   {result.total_trades}회")


if __name__ == "__main__":
    main()
