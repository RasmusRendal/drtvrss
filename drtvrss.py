from flask import Flask, Response
from flask_caching import Cache
import requests
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)


rss_feed_template = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>FEED_TITLE</title>
 <description>FEED_DESCRIPTION</description>
 <link>FEED_URL</link>
 <ttl>60</ttl>

 EPISODES
 </channel>
</rss>"""

rss_item_template = """<item>
  <title>ENTRYTITLE</title>
  <description>ENTRYDESC</description>
  <link>ENTRYLINK</link>
  <pubDate>ENTRYPUBDATE</pubDate>
 </item>
"""


def episodes(show: str):
    return BeautifulSoup(requests.get("https://www.dr.dk/drtv/serie/" + show).text).find(class_="d1-drtv__episodes")


def parse_episode(e):
    extra_details = e.find(
        class_="d1-drtv-episode-title-and-details__contextual-title-extra-details").contents[0].split(" | ")
    return {
        "title": e.find(class_="d1-drtv-episode-title-and-details__contextual-title").contents[0],
        "time": datetime.strptime(extra_details[0], "%d. %b %Y"),
        "length": extra_details[1],
        "description": e.find(class_="d1-drtv-episode-description__short-description").contents[0],
        "url": e.find(class_="d1-drtv-episode-title-and-details d1-drtv-episode-description__title-and-details").attrs["href"]
    }


def parse_show(s):
    return {
        "title": s.find(class_="dh1-drtv-hero__title").contents[0],
        "description": s.find(class_="dh1-item-desc__short-description").contents[0]
    }


def episode_to_rss(e: dict) -> str:
    return rss_item_template.replace("ENTRYTITLE", e["title"]).replace("ENTRYDESC", e["description"]).replace("ENTRYLINK", e["url"]).replace("ENTRYPUBDATE", str(e["time"]))


@app.route("/<show>.xml")
@cache.cached(timeout=3600)
def hello_world(show):
    url = "https://www.dr.dk/drtv/serie/" + show
    page = BeautifulSoup(requests.get(url).text)
    children = page.find(class_="d1-drtv__episodes").children
    episodes_rss = "".join([episode_to_rss(parse_episode(e))
                           for e in children])
    metadata = parse_show(page)
    feed = rss_feed_template.replace("FEED_TITLE", metadata["title"]).replace(
        "FEED_DESCRIPTION", metadata["description"]).replace("FEED_URL", url).replace("EPISODES", episodes_rss)
    return Response(feed, headers={"content-type": "application/html"})
