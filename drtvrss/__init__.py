from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, Response, render_template
from flask import abort
from flask_caching import Cache
from time import time
from yt_dlp import YoutubeDL
from zoneinfo import ZoneInfo
import requests

from .rss import RSSEntry, RSSFeed

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)


shows: dict[str, RSSFeed] = {}
stream_urls: dict[str, str] = {}


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


def get_show(show: str) -> RSSFeed:
    if show not in shows or shows[show].age + 3600 < time():
        url = "https://www.dr.dk/drtv/serie/" + show
        print("Fetching show", url)
        r = requests.get(url)
        if r.status_code != 200:
            abort(404)
        page = BeautifulSoup(r.text, features='html.parser')

        feed = parse_show(page, url)
        episodes_elem = page.find(class_="d1-drtv__episodes")
        if episodes_elem is not None:
            for e in episodes_elem.children:
                feed.add_entry(parse_episode(e))

        shows[show] = feed
    return shows[show]


@app.route("/")
def index():
    feed_list = "".join(
        [f"<li><a href='{name}'>{s.title}</a></li>" for name, s in shows.items()])
    return "Tilgængelig er blandt andet de følgende RSS feeds: <ul>" + feed_list + "</ul>" + "Andre serier kan sagtens findes, bare manipuler URLsene lidt. Kildekoden er at finde på <a href='https://github.com/RasmusRendal/drtvrss'>GitHub</a>"


@app.route("/favicon.ico")
def favicon():
    abort(404)


@app.route("/<showid>/<episode>")
@cache.cached(timeout=15 * 60)
def view_episode(showid, episode):
    show = get_show(showid)
    if episode not in stream_urls:
        url = "https://www.dr.dk/drtv/episode/" + episode
        ydl = YoutubeDL()
        i = ydl.extract_info(url, download=False)
        stream_urls[episode] = i["formats"][-1]["manifest_url"]
    videourl = stream_urls[episode]
    return render_template("video.html", s=show, videourl=videourl)


@app.route("/<showid>/")
@cache.cached(timeout=15 * 60)
def view_show(showid):
    show = get_show(showid)
    return render_template("show.html", s=show)


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
def get_feed(show):
    return Response(get_show(show).dump(), headers={"content-type": "application/rss+xml"})
