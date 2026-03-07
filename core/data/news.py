"""
뉴스 수집기
- 미국 금융 뉴스 RSS (기본)
- 한국 금융 뉴스 RSS (선택)
- 키워드 기반 필터링
"""
import feedparser
from datetime import datetime
from typing import Optional
from loguru import logger


# 미국 금융 뉴스 RSS
US_FEEDS = {
    "reuters_markets":   "https://feeds.reuters.com/reuters/businessNews",
    "seeking_alpha":     "https://seekingalpha.com/market_currents.xml",
    "marketwatch":       "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "yahoo_finance":     "https://finance.yahoo.com/news/rssindex",
}

# 한국 금융 뉴스 RSS
KR_FEEDS = {
    "yonhap_economy": "https://www.yna.co.kr/rss/economy.xml",
    "hankyung":       "https://www.hankyung.com/feed/economy",
    "mk_economy":     "https://www.mk.co.kr/rss/30100041/",
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
        keywords: 필터 키워드 (None이면 전체)

    Returns:
        [{title, summary, link, published, source}]
    """
    try:
        feed = feedparser.parse(feed_url)
        articles = []

        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")
            published = entry.get("published", str(datetime.now()))

            if keywords:
                text = f"{title} {summary}".lower()
                if not any(kw.lower() in text for kw in keywords):
                    continue

            articles.append({
                "title": title,
                "summary": summary[:500],
                "link": link,
                "published": published,
                "source": feed.feed.get("title", feed_url),
            })

        logger.info(f"Fetched {len(articles)} articles from {feed_url[:60]}")
        return articles

    except Exception as e:
        logger.error(f"RSS fetch failed {feed_url}: {e}")
        return []


def fetch_all_news(
    tickers: Optional[list[str]] = None,
    limit_per_feed: int = 10,
    market: str = "us",
) -> list[dict]:
    """전체 피드에서 뉴스 수집

    Args:
        tickers: 관심 종목/키워드 (예: ["AAPL", "nvidia"], ["삼성전자"])
        limit_per_feed: 피드당 최대 기사 수
        market: "us" (기본) | "kr" | "all"

    Returns:
        뉴스 리스트 (시간 역순, 중복 제거)
    """
    feeds = {}
    if market in ("us", "all"):
        feeds.update(US_FEEDS)
    if market in ("kr", "all"):
        feeds.update(KR_FEEDS)

    all_articles = []
    seen_links = set()

    for name, url in feeds.items():
        articles = fetch_rss_news(url, limit=limit_per_feed, keywords=tickers)
        for article in articles:
            if article["link"] not in seen_links:
                seen_links.add(article["link"])
                all_articles.append(article)

    logger.info(f"Total: {len(all_articles)} unique articles (market={market})")
    return sorted(all_articles, key=lambda x: x["published"], reverse=True)


if __name__ == "__main__":
    # 미국 뉴스 테스트
    news = fetch_all_news(tickers=["SPY", "QQQ", "nvidia"], limit_per_feed=5, market="us")
    for article in news[:5]:
        print(f"[{article['source']}] {article['title']}")
        print(f"  → {article['link']}\n")
