"""
ETF 듀얼 모멘텀 로테이션 백테스트 스크립트

사용법:
  python scripts/run_etf_rotation.py
  python scripts/run_etf_rotation.py --period 5y --top-n 1
  python scripts/run_etf_rotation.py --tickers SPY QQQ SSO QLD GLD UGL TLT BIL --vol-target 0.20
  python scripts/run_etf_rotation.py --period 10y --top-n 2 --log-rebalance
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.strategies.etf_rotation import run_etf_rotation, DEFAULT_UNIVERSE


def main():
    parser = argparse.ArgumentParser(description="ETF 듀얼 모멘텀 로테이션 백테스트")
    parser.add_argument("--tickers",    nargs="+", default=DEFAULT_UNIVERSE,
                        help="투자 유니버스 (기본: SPY QQQ GLD TLT BIL)")
    parser.add_argument("--period",     default="10y",
                        help="백테스트 기간 (5y/10y/15y)")
    parser.add_argument("--top-n",      type=int, default=2,
                        help="매월 보유 ETF 수 (기본: 2)")
    parser.add_argument("--lookback",   type=int, default=126,
                        help="모멘텀 기간 거래일 (기본: 126 = 6개월)")
    parser.add_argument("--skip",       type=int, default=21,
                        help="최근 제외 거래일 (기본: 21 = 1개월)")
    parser.add_argument("--capital",    type=float, default=10_000_000,
                        help="초기 자본금 (원, 기본: 1천만)")
    parser.add_argument("--commission", type=float, default=0.001,
                        help="편도 수수료율 (기본: 0.1%%)")
    parser.add_argument("--slippage",   type=float, default=0.0005,
                        help="편도 슬리피지 (기본: 0.05%%)")
    parser.add_argument("--no-abs-momentum", action="store_true",
                        help="절대 모멘텀 필터 비활성화")
    parser.add_argument("--vol-target", type=float, default=None,
                        help="목표 연환산 변동성 (예: 0.20 = 20%%). None이면 비활성")
    parser.add_argument("--vol-window", type=int, default=21,
                        help="변동성 측정 윈도우 거래일 (기본: 21)")
    parser.add_argument("--log-rebalance", action="store_true",
                        help="전체 리밸런싱 내역 출력")
    args = parser.parse_args()

    use_abs = not args.no_abs_momentum

    print(f"\nETF 듀얼 모멘텀 로테이션")
    print(f"   유니버스:       {args.tickers}")
    print(f"   기간:           {args.period}")
    print(f"   보유 종목 수:   {args.top_n}")
    print(f"   모멘텀:         {args.lookback}일 (최근 {args.skip}일 제외)")
    print(f"   절대 모멘텀:    {'ON (하락장 현금 전환)' if use_abs else 'OFF'}")
    if args.vol_target:
        print(f"   변동성 타겟:    {args.vol_target:.0%} (초과 시 비중 자동 축소)")
    print(f"   수수료:         {args.commission*100:.2f}% | 슬리피지: {args.slippage*100:.3f}%\n")

    result = run_etf_rotation(
        tickers=args.tickers,
        period=args.period,
        top_n=args.top_n,
        lookback=args.lookback,
        skip=args.skip,
        commission=args.commission,
        slippage=args.slippage,
        initial_capital=args.capital,
        use_absolute_momentum=use_abs,
        vol_target=args.vol_target,
        vol_window=args.vol_window,
    )

    if not result:
        print("백테스트 실패")
        return

    print("=" * 50)
    print("결과")
    print("=" * 50)
    print(f"  총 수익률:       {result['total_return']:+.1f}%")
    print(f"  연환산 수익률:   {result['annualized_return']:+.1f}%")
    print(f"  샤프 비율:       {result['sharpe_ratio']:.2f}")
    print(f"  소르티노 비율:   {result['sortino_ratio']:.2f}")
    print(f"  칼마 비율:       {result['calmar_ratio']:.2f}")
    print(f"  최대 낙폭(MDD):  {result['max_drawdown']:.1f}%")
    print(f"  리밸런싱 횟수:   {result['total_rebalances']}회")

    log = result["rebalance_log"]
    entries = log if args.log_rebalance else log[-6:]
    label = "전체" if args.log_rebalance else "최근 6회"
    print(f"\n  리밸런싱 내역 ({label}):")
    for r in entries:
        scale_str = f" [{r['invest_scale']:.0%}투자]" if args.vol_target else ""
        mom_str = " | ".join(f"{t}: {v:+.1%}" for t, v in r["momentum"].items())
        print(f"    {r['date']}  {str(r['portfolio']):<25}{scale_str}  {mom_str}")


if __name__ == "__main__":
    main()
