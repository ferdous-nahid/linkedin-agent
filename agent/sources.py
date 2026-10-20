"""News sources. Each entry: (niche, feed_url). Add/remove freely — broken feeds are skipped."""
from urllib.parse import quote_plus

NICHES = {
    "tracking": "Marketing tracking & analytics (GA4, GTM, server-side tagging, Meta CAPI, privacy/cookies, attribution, ad platform updates)",
    "growth": "Business growth (growth strategy, SMB trends, AI for business, sales & lead generation)",
    "realestate": "Real estate marketing (agent/agency marketing, proptech, property lead generation, listing portals)",
}

DIRECT_FEEDS = [
    # Tracking / analytics / ad platforms
    ("tracking", "https://ppc.land/rss/"),
    ("tracking", "https://searchengineland.com/feed"),
    ("tracking", "https://www.searchenginejournal.com/feed/"),
    ("tracking", "https://martech.org/feed/"),
    ("tracking", "https://www.simoahava.com/index.xml"),
    ("tracking", "https://www.analyticsmania.com/feed/"),
    ("tracking", "https://digiday.com/feed/"),
    ("tracking", "https://www.adexchanger.com/feed/"),
    ("tracking", "https://www.socialmediatoday.com/feeds/news/"),
    # Business growth
    ("growth", "https://www.entrepreneur.com/latest.rss"),
    ("growth", "https://smallbiztrends.com/feed"),
    ("growth", "https://techcrunch.com/category/startups/feed/"),
    ("growth", "https://feeds.hbr.org/harvardbusiness"),
    ("growth", "https://blog.hubspot.com/marketing/rss.xml"),
    # Real estate marketing
    ("realestate", "https://www.inman.com/feed/"),
    ("realestate", "https://www.housingwire.com/feed/"),
    ("realestate", "https://www.realtrends.com/feed/"),
    ("realestate", "https://therealdeal.com/feed/"),
    ("realestate", "https://propertyindustryeye.com/feed/"),
]

GOOGLE_NEWS_QUERIES = [
    ("tracking", '"Google Analytics" OR GA4 update'),
    ("tracking", '"Google Tag Manager" OR "server-side tagging" OR "Conversions API"'),
    ("tracking", '"Google Ads" OR "Meta Ads" new feature advertisers'),
    ("tracking", 'cookie consent tracking privacy advertisers'),
    ("growth", '"small business" growth strategy'),
    ("growth", 'AI marketing business growth'),
    ("realestate", '"real estate marketing"'),
    ("realestate", 'proptech OR "estate agents" marketing leads'),
]


def google_news_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(query + " when:2d")
        + "&hl=en-GB&gl=GB&ceid=GB:en"
    )


def all_feeds():
    feeds = list(DIRECT_FEEDS)
    feeds += [(n, google_news_url(q)) for n, q in GOOGLE_NEWS_QUERIES]
    return feeds
