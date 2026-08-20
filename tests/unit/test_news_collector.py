from src.collectors.news import NewsCollector


def test_parse_feed_and_prioritize_human_interest_story() -> None:
    feed = b"""<?xml version="1.0"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
      <item><title>Latest Hitter Power Rankings</title><link>https://example.com/rankings</link><pubDate>Thu</pubDate></item>
      <item><title>Rookie's remarkable journey makes history</title><link>https://example.com/rookie</link><pubDate>Thu</pubDate><dc:creator>Reporter</dc:creator></item>
    </channel></rss>"""
    collector = NewsCollector()
    items = collector._parse_feed(feed)

    assert len(items) == 2
    assert items[1]["author"] == "Reporter"
    assert collector._score(items[1]) > collector._score(items[0])
