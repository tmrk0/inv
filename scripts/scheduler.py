"""
ETF 리밸런싱 스케줄러

매월 마지막 거래일 장 마감 후(한국 시간 07:00 = 미국 동부 17:00) 리밸런싱 실행.
'마지막 거래일' 판단: 매일 체크해서 다음 날이 다른 달이면 실행.

Usage:
    python scripts/scheduler.py            # 스케줄러 시작 (포그라운드)
    python scripts/scheduler.py --now      # 즉시 1회 실행 (테스트용)
    python scripts/scheduler.py --dry-run  # 즉시 1회 dry-run
"""
import sys
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import schedule
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.execution.kis import KISClient
from core.execution.rebalancer import ETFRebalancer


def _is_last_trading_day_of_month() -> bool:
    """오늘이 이번 달 마지막 거래일(월~금)인지 판단"""
    today = date.today()
    # 오늘이 주말이면 거래일 아님
    if today.weekday() >= 5:
        return False
    # 내일부터 다음 주 월요일까지 같은 달 거래일이 있는지 확인
    next_day = today + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.month != today.month


def run_rebalance(dry_run: bool = False):
    """리밸런싱 실행"""
    logger.info(f"=== 스케줄 리밸런싱 시작 (dry_run={dry_run}) ===")
    try:
        kis = KISClient()
        rb  = ETFRebalancer(kis=kis)
        result = rb.run(dry_run=dry_run)
        logger.info(f"목표 포트폴리오: {result['signal']['target']}")
        if not dry_run and result.get("executed_buys"):
            logger.info(f"매수 완료: {[b['ticker'] for b in result['executed_buys']]}")
    except Exception as e:
        logger.error(f"리밸런싱 실패: {e}")


def scheduled_job():
    """매일 07:00 KST 실행 — 마지막 거래일이면 리밸런싱"""
    if _is_last_trading_day_of_month():
        logger.info("이번 달 마지막 거래일 — 리밸런싱 실행")
        run_rebalance(dry_run=False)
    else:
        logger.debug(f"[{date.today()}] 리밸런싱 스킵 (마지막 거래일 아님)")


def main():
    parser = argparse.ArgumentParser(description="ETF 리밸런싱 스케줄러")
    parser.add_argument("--now",     action="store_true", help="즉시 1회 실행 (실제 주문)")
    parser.add_argument("--dry-run", action="store_true", help="즉시 1회 dry-run 실행")
    args = parser.parse_args()

    if args.now or args.dry_run:
        run_rebalance(dry_run=args.dry_run)
        return

    # 매일 07:00 KST 체크 (cron 대신 schedule 라이브러리)
    schedule.every().day.at("07:00").do(scheduled_job)
    logger.info("스케줄러 시작 — 매일 07:00 KST 체크 (월말 마지막 거래일에 리밸런싱)")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
