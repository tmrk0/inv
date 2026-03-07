"""
멀티자산 ETF 로테이션 백테스터

전략 근거:
  - Antonacci (2014) 듀얼 모멘텀: 절대 모멘텀 + 상대 모멘텀 결합
  - 절대 모멘텀 < 무위험 수익률 → 전액 현금(BIL) 보유 (하락장 방어)
  - 상대 모멘텀으로 유니버스 내 상위 N개 자산 선택
  - 월별 리밸런싱
  - 변동성 타겟팅: 포트폴리오 변동성이 목표 초과 시 비중 자동 축소

기본 유니버스 (SPY/QQQ/GLD/TLT/BIL):
  SPY — 미국 대형주 (S&P 500)
  QQQ — 미국 기술주 (나스닥 100)
  GLD — 금
  TLT — 미국 장기국채 (20년+)
  BIL — 단기국채 (현금 대용)

안전장치:
  1. 거래비용 + 슬리피지 반영
  2. 룩어헤드 방지 (모멘텀 계산 시 skip 적용)
  3. 절대 모멘텀 필터 (하락장 전액 현금 전환)
  4. 최대 보유 종목 수 제한 (top_n)
  5. 변동성 타겟팅 (vol_target) — 변동성 높으면 비중 자동 축소
  6. 동일 포트폴리오 시 리밸런싱 생략 (불필요한 거래비용 방지)
"""
import pandas as pd
import numpy as np
import yfinance as yf
from loguru import logger

DEFAULT_UNIVERSE = ["SPY", "QQQ", "GLD", "TLT", "BIL"]
CASH_TICKER = "BIL"


def fetch_prices(tickers: list[str], period: str = "10y") -> pd.DataFrame:
    """멀티 티커 종가 수집 (yfinance)"""
    raw = yf.download(tickers, period=period, progress=False, auto_adjust=True)

    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]] if "Close" in raw.columns else raw

    if isinstance(prices, pd.Series):
        prices = prices.to_frame(tickers[0])

    prices = prices.dropna(how="all")
    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        logger.warning(f"데이터 없는 티커: {missing}")

    logger.info(f"가격 데이터: {len(prices)}일 ({prices.index[0].date()} ~ {prices.index[-1].date()})")
    return prices


def _momentum_scores(prices: pd.DataFrame, lookback: int, skip: int) -> pd.Series:
    """현재 시점 모멘텀 스코어 (룩어헤드 방지: skip 적용)"""
    if len(prices) < lookback + skip:
        return pd.Series(dtype=float)
    recent = prices.iloc[-(skip + 1)]
    past = prices.iloc[-(lookback + skip + 1)]
    return recent / past - 1


def _realized_vol(prices: pd.DataFrame, tickers: list[str], window: int = 21) -> float:
    """선택된 포트폴리오의 최근 실현 변동성 (연환산, 균등 비중 가정)"""
    cols = [t for t in tickers if t in prices.columns]
    if not cols or len(prices) < window + 1:
        return float("inf")
    ret = prices[cols].pct_change().dropna().tail(window)
    port_ret = ret.mean(axis=1)  # 균등 비중 포트폴리오 일별 수익률
    return float(port_ret.std() * np.sqrt(252))


def run_etf_rotation(
    tickers: list[str] = None,
    period: str = "10y",
    top_n: int = 2,
    lookback: int = 126,
    skip: int = 21,
    commission: float = 0.001,
    slippage: float = 0.0005,
    initial_capital: float = 10_000_000,
    use_absolute_momentum: bool = True,
    rf_annual: float = 0.035,
    cash_ticker: str = CASH_TICKER,
    vol_target: float = None,        # 목표 연환산 변동성 (예: 0.20 = 20%). None이면 비활성
    vol_window: int = 21,            # 변동성 계산 윈도우 (거래일)
    vol_max_scale: float = 1.0,      # 최대 투자 비중 상한 (레버리지 방지)
) -> dict:
    """ETF 듀얼 모멘텀 로테이션 백테스트

    Args:
        tickers: 투자 유니버스
        period: yfinance 기간
        top_n: 매월 보유할 최대 ETF 수
        lookback: 모멘텀 계산 기간 (거래일)
        skip: 최근 제외 기간 (거래일)
        commission: 편도 수수료율
        slippage: 편도 슬리피지
        initial_capital: 초기 자본금
        use_absolute_momentum: True면 절대 모멘텀 음수 시 현금 전환
        rf_annual: 연 무위험 이자율
        cash_ticker: 현금 대용 ETF
        vol_target: 목표 연환산 변동성. 초과 시 비중 축소 (예: 0.20)
        vol_window: 변동성 측정 윈도우
        vol_max_scale: 최대 투자 비중 (기본 1.0 = 100%)

    Returns:
        {total_return, annualized_return, sharpe_ratio, sortino_ratio, calmar_ratio,
         max_drawdown, total_rebalances, equity_curve, rebalance_log}
    """
    if tickers is None:
        tickers = DEFAULT_UNIVERSE

    if cash_ticker not in tickers:
        tickers = list(tickers) + [cash_ticker]

    prices = fetch_prices(tickers, period)
    if prices.empty:
        logger.error("가격 데이터 수집 실패")
        return {}

    rf_period = (1 + rf_annual) ** (lookback / 252) - 1

    rebalance_dates = set(prices.resample("ME").last().index)

    cash = float(initial_capital)
    holdings: dict[str, float] = {}
    equity_curve: list[float] = []
    rebalance_log: list[dict] = []
    current_portfolio: set[str] = set()
    current_scale: float = 1.0      # 현재 투자 비중 (변동성 타겟 적용)

    cost_rate = (1 + slippage) * (1 + commission)
    recv_rate = (1 - slippage) * (1 - commission)

    for date in prices.index:
        day_prices = prices.loc[date]

        if date in rebalance_dates:
            hist = prices.loc[:date]

            if len(hist) >= lookback + skip + 1:
                mom = _momentum_scores(hist, lookback, skip).dropna()
                investable = mom.drop(labels=[cash_ticker], errors="ignore")

                if use_absolute_momentum:
                    investable = investable[investable > rf_period]

                if len(investable) == 0:
                    selected = [cash_ticker] if cash_ticker in prices.columns else []
                else:
                    selected = list(investable.sort_values(ascending=False).head(top_n).index)

                # 변동성 타겟팅: 투자 비중 계산
                if vol_target and selected and selected != [cash_ticker]:
                    rv = _realized_vol(hist, selected, vol_window)
                    if rv > 0:
                        scale = min(vol_target / rv, vol_max_scale)
                    else:
                        scale = vol_max_scale
                else:
                    scale = vol_max_scale

                portfolio_changed = set(selected) != current_portfolio
                scale_changed = abs(scale - current_scale) > 0.02  # 2% 이상 변화 시만 리밸런싱

                if (portfolio_changed or scale_changed) and selected:
                    portfolio_value = cash + sum(
                        shares * day_prices.get(t, 0)
                        for t, shares in holdings.items()
                    )

                    # 기존 포지션 전량 청산
                    for t, shares in holdings.items():
                        if t in day_prices and not pd.isna(day_prices[t]):
                            cash += shares * day_prices[t] * recv_rate

                    holdings = {}

                    # 신규 포지션 진입 (scale 적용)
                    invest_amount = portfolio_value * scale
                    alloc = invest_amount / len(selected)
                    for t in selected:
                        if t in day_prices and not pd.isna(day_prices[t]):
                            entry = day_prices[t] * cost_rate
                            holdings[t] = alloc / entry
                            cash -= alloc

                    current_portfolio = set(selected)
                    current_scale = scale

                    mom_snap = {t: round(float(mom.get(t, 0)), 4) for t in selected}
                    rebalance_log.append({
                        "date": date.date(),
                        "portfolio": selected,
                        "momentum": mom_snap,
                        "invest_scale": round(scale, 2),
                        "portfolio_value": round(portfolio_value, 0),
                    })
                    scale_str = f" | 투자비중: {scale:.0%}" if vol_target else ""
                    logger.info(f"리밸런싱 {date.date()} → {selected}{scale_str} | 자산: {portfolio_value:,.0f}원")

        # 일별 자산 평가 (mark-to-market)
        nav = cash + sum(
            shares * day_prices.get(t, 0)
            for t, shares in holdings.items()
            if not pd.isna(day_prices.get(t, float("nan")))
        )
        equity_curve.append(nav)

    equity = pd.Series(equity_curve, index=prices.index)

    # 성과 지표
    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    years = len(prices) / 252
    ann_return = ((equity.iloc[-1] / initial_capital) ** (1 / max(years, 0.1)) - 1) * 100

    daily_ret = equity.pct_change().fillna(0)
    excess = daily_ret - rf_annual / 252
    sharpe = (excess.mean() / (excess.std() + 1e-10)) * np.sqrt(252)

    downside_std = daily_ret[daily_ret < 0].std() + 1e-10
    sortino = (daily_ret.mean() / downside_std) * np.sqrt(252)

    rolling_max = equity.cummax()
    mdd = float(((equity - rolling_max) / rolling_max * 100).min())
    calmar = ann_return / (abs(mdd) + 1e-10)

    result = {
        "total_return": round(total_return, 2),
        "annualized_return": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "max_drawdown": round(mdd, 2),
        "total_rebalances": len(rebalance_log),
        "equity_curve": equity,
        "rebalance_log": rebalance_log,
    }

    logger.info(
        f"ETF 로테이션 완료 | 수익: {total_return:.1f}% | "
        f"연환산: {ann_return:.1f}% | 샤프: {sharpe:.2f} | MDD: {mdd:.1f}%"
    )
    return result


if __name__ == "__main__":
    result = run_etf_rotation(
        tickers=["SPY", "QQQ", "SSO", "QLD", "GLD", "UGL", "TLT", "BIL"],
        period="10y",
        top_n=2,
        vol_target=0.20,
    )
    print(f"수익률: {result['total_return']:+.1f}% | MDD: {result['max_drawdown']:.1f}%")
