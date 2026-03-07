"""
백테스팅 실행 스크립트

사용법:
  python scripts/run_backtest.py --ticker AAPL --strategy momentum --period 5y
  python scripts/run_backtest.py --ticker 005930 --market krx --strategy dual_momentum
  python scripts/run_backtest.py --ticker AAPL --walkforward
  python scripts/run_backtest.py --ticker AAPL --strategy vol_momentum --atr-sizing
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.fetcher import fetch_ohlcv_global, fetch_ohlcv_krx
from core.backtester.engine import run_backtest, run_walkforward
from core.strategies.examples.ma_cross import MACrossStrategy, RSIStrategy
from core.strategies.examples.momentum import (
    MomentumStrategy,
    DualMomentumStrategy,
    VolAdjMomentumStrategy,
)

STRATEGIES = {
    "ma_cross":      MACrossStrategy,
    "rsi":           RSIStrategy,
    "momentum":      MomentumStrategy,
    "dual_momentum": DualMomentumStrategy,
    "vol_momentum":  VolAdjMomentumStrategy,
}


def print_result(strategy_name: str, result):
    print("\n" + "=" * 45)
    print(f"📊 백테스팅 결과: {strategy_name}")
    print("=" * 45)
    print(f"  총 수익률:       {result.total_return:+.1f}%")
    print(f"  연환산 수익률:   {result.annualized_return:+.1f}%")
    print(f"  샤프 비율:       {result.sharpe_ratio:.2f}")
    print(f"  소르티노 비율:   {result.sortino_ratio:.2f}")
    print(f"  칼마 비율:       {result.calmar_ratio:.2f}")
    print(f"  최대 낙폭(MDD):  {result.max_drawdown:.1f}%")
    print(f"  승률:            {result.win_rate:.1f}%")
    print(f"  평균 거래 수익:  {result.avg_trade_return:+.2f}%")
    print(f"  손익비(PF):      {result.profit_factor:.2f}")
    print(f"  총 거래 횟수:    {result.total_trades}회")

    if result.trades:
        stop_count = sum(1 for t in result.trades if t.get("stop_loss"))
        print(f"  손절 발동:       {stop_count}회")


def print_walkforward(wf: dict):
    print("\n" + "=" * 45)
    print(f"🔄 워크포워드 테스트 결과 ({wf['total_folds']}폴드)")
    print("=" * 45)
    print(f"  OOS 평균 수익률: {wf['avg_return']:+.1f}%")
    print(f"  OOS 평균 샤프:   {wf['avg_sharpe']:.2f}")
    print(f"  OOS 평균 MDD:    {wf['avg_max_drawdown']:.1f}%")
    print()
    for f in wf["folds"]:
        sign = "+" if f["return_pct"] >= 0 else ""
        print(
            f"  Fold {f['fold']+1} [{f['test_start']}~{f['test_end']}] "
            f"수익:{sign}{f['return_pct']:.1f}% 샤프:{f['sharpe']:.2f} "
            f"MDD:{f['max_drawdown']:.1f}% 거래:{f['trades']}회"
        )


def main():
    parser = argparse.ArgumentParser(description="백테스팅 실행")
    parser.add_argument("--ticker",    default="AAPL",  help="티커 (예: AAPL, 005930)")
    parser.add_argument("--market",    choices=["global", "krx"], default="global")
    parser.add_argument("--strategy",  choices=list(STRATEGIES.keys()), default="momentum")
    parser.add_argument("--period",    default="5y",    help="기간 (글로벌 전용: 1y/2y/5y)")
    parser.add_argument("--capital",   type=float, default=10_000_000, help="초기 자본 (원)")
    parser.add_argument("--commission",type=float, default=0.0015, help="편도 수수료율")
    parser.add_argument("--slippage",  type=float, default=0.001,  help="편도 슬리피지")
    parser.add_argument("--stop-loss", type=float, default=0.05,   help="손절 비율 (0.05=5%%)")
    parser.add_argument("--max-pos",   type=float, default=1.0,    help="종목당 최대 비중 (0~1)")
    parser.add_argument("--atr-sizing",action="store_true",         help="ATR 기반 포지션 사이징")
    parser.add_argument("--walkforward",action="store_true",        help="워크포워드 테스트 실행")
    parser.add_argument("--wf-train",  type=int, default=252,  help="워크포워드 훈련 구간(일)")
    parser.add_argument("--wf-test",   type=int, default=63,   help="워크포워드 테스트 구간(일)")
    args = parser.parse_args()

    print(f"📈 백테스팅: {args.ticker} | 전략: {args.strategy} | 기간: {args.period}")
    print(f"   수수료: {args.commission*100:.2f}% | 슬리피지: {args.slippage*100:.2f}% | "
          f"손절: {args.stop_loss*100:.0f}% | ATR사이징: {args.atr_sizing}")

    # 데이터 수집
    if args.market == "krx":
        df = fetch_ohlcv_krx(args.ticker)
    else:
        df = fetch_ohlcv_global(args.ticker, args.period)

    if df.empty:
        print("❌ 데이터를 가져올 수 없습니다.")
        return

    print(f"✅ 데이터: {len(df)}일 ({df.index[0].date()} ~ {df.index[-1].date()})")

    strategy = STRATEGIES[args.strategy]()

    backtest_kwargs = dict(
        initial_capital=args.capital,
        commission=args.commission,
        slippage=args.slippage,
        stop_loss_pct=args.stop_loss,
        max_position_pct=args.max_pos,
        use_atr_sizing=args.atr_sizing,
    )

    # 백테스팅
    result = run_backtest(df, strategy, **backtest_kwargs)
    print_result(strategy.name, result)

    # 워크포워드
    if args.walkforward:
        wf = run_walkforward(
            df, strategy,
            train_periods=args.wf_train,
            test_periods=args.wf_test,
            **backtest_kwargs,
        )
        print_walkforward(wf)


if __name__ == "__main__":
    main()
