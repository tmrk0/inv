"""
뉴스 수집기
- RSS 피드: 네이버 금융, 연합뉴스 등
- 키워드 기반 필터링
"""
import feedparser
import requests
from datetime import datetime
from typing import Optional
from loguru import logger


# 기본 금융 뉴스 RSS 피드 목록
DEFAULT_FEEDS = {
    "naver_finance": "https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258",
    "yonhap_economy": "https://www.yna.co.kr/rss/economy.xml",
    "hankyung": "https://www.hankyung.com/feed/economy",
    "mk_economy": "https://www.mk.co.kr/rss/30100041/",
}


def fetch_rss_news(
    feed_url: str,
    limit: int = 20,
    keywords: Optional[list[str]] = None,
) -> list[dict]:
    """RSS 피드에서 뉴스 수집

    Args:
        feed_url: RSS URL
        limit: 최대 기사 수
        keywords: 필터 키워드 리스트 (None이면 전체)

    Returns:
        뉴스 딕셔너리 리스트 [{title, summary, link, published}]
    """
    try:
        feed = feedparser.parse(feed_url)
        articles = []

        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")
            published = entry.get("published", str(datetime.now()))

            # 키워드 필터
            if keywords:
                text = f"{title} {summary}".lower()
                if not any(kw.lower() in text for kw in keywords):
                    continue

            articles.append({
                "title": title,
                "summary": summary[:500],  # 500자 제한
                "link": link,
                "published": published,
                "source": feed.feed.get("title", feed_url),
            })

        logger.info(f"Fetched {len(articles)} articles from {feed_url[:50]}")
        return articles

    except Exception as e:
        logger.error(f"RSS fetch failed {feed_url}: {e}")
        return []


def fetch_all_news(
    tickers: Optional[list[str]] = None,
    limit_per_feed: int = 10,
) -> list[dict]:
    """전체 피드에서 뉴스 수집

    Args:
        tickers: 관심 종목명/키워드 리스트 (예: ["삼성전자", "SK하이닉스"])
        limit_per_feed: 피드당 최대 기사 수

    Returns:
        전체 뉴스 리스트 (중복 제거)
    """
    all_articles = []
    seen_links = set()

    for name, url in DEFAULT_FEEDS.items():
        articles = fetch_rss_news(url, limit=limit_per_feed, keywords=tickers)
        for article in articles:
            if article["link"] not in seen_links:
                seen_links.add(article["link"])
                all_articles.append(article)

    logger.info(f"Total: {len(all_articles)} unique articles")
    return sorted(all_articles, key=lambda x: x["published"], reverse=True)


if __name__ == "__main__":
    news = fetch_all_news(tickers=["삼성전자", "반도체"], limit_per_feed=5)
    for article in news[:5]:
        print(f"[{article['source']}] {article['title']}")
        print(f"  → {article['link']}\n")
