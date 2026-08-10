"""
Collector Test
Her kaynağın tek tek çalışıp çalışmadığını gösterir.
"""

from sources.hn_fetcher import fetch_hacker_news
from sources.github_fetcher import fetch_github_trending
from sources.trends_fetcher import fetch_google_trends
from sources.lobsters_fetcher import fetch_lobsters
from sources.producthunt_fetcher import fetch_producthunt
from sources.betalists_fetcher import fetch_betalist
from sources.reddit_fetcher import fetch_reddit_posts


def run_source(name, func):
    print("=" * 60)
    print(name)

    try:
        posts = func(limit=3)

        print("Toplanan :", len(posts))

        for p in posts:
            print("-", p.get("title", "")[:70])

    except Exception as e:
        print("HATA:", e)


def main():

    run_source("Hacker News", fetch_hacker_news)

    run_source("GitHub Trending", fetch_github_trending)

    run_source("Google Trends", fetch_google_trends)

    run_source("Lobsters", fetch_lobsters)

    run_source("Product Hunt", fetch_producthunt)

    run_source("BetaList", fetch_betalist)

    run_source("Reddit", fetch_reddit_posts)


if __name__ == "__main__":
    main()
