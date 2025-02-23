from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, Response
from flask_caching import Cache
from zoneinfo import ZoneInfo
import requests

from .rss import RSSEntry, RSSFeed

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)

shows = {}


def episodes(show: str):
    return BeautifulSoup(requests.get("https://www.dr.dk/drtv/serie/" + show).text).find(class_="d1-drtv__episodes")


def parse_episode(e) -> RSSEntry:
    extra_details = e.find(
        class_="d1-drtv-episode-title-and-details__contextual-title-extra-details").contents[0].split(" | ")
    title = e.find(
        class_="d1-drtv-episode-title-and-details__contextual-title").contents[0]
    time = datetime.strptime(extra_details[0], "%d. %b %Y").astimezone(
        ZoneInfo("Europe/Copenhagen"))
    description = e.find(
        class_="d1-drtv-episode-description__short-description").contents[0]
    url = e.find(
        class_="d1-drtv-episode-title-and-details d1-drtv-episode-description__title-and-details").attrs["href"]
    return RSSEntry(title, time=time, description=description, url=url)


def parse_show(s, url) -> RSSFeed:
    title = s.find(class_="dh1-drtv-hero__title").contents[0]
    description = s.find(class_="dh1-item-desc__short-description").contents[0]
    return RSSFeed(title, description=description, url=url)


@app.route("/")
def index():
    feed_list = "".join(
        [f"<li><a href='{name}.xml'>{s.title}</a></li>" for name, s in shows.items()])
    return "Tilgængelig er blandt andet de følgende RSS feeds: <ul>" + feed_list + "</ul>" + "Andre serier kan sagtens findes, bare manipuler URLsene lidt."


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
def get_feed(show):
    url = "https://www.dr.dk/drtv/serie/" + show
    print(url)
    page = BeautifulSoup(requests.get(url).text, features='html.parser')

    feed = parse_show(page, url)
    episodes_elem = page.find(class_="d1-drtv__episodes")
    if episodes_elem is not None:
        for e in episodes_elem.children:
            feed.add_entry(parse_episode(e))

    shows[show] = feed

    return Response(feed.dump(), headers={"content-type": "application/rss+xml"})
