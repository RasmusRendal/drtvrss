from datetime import datetime
from json.decoder import JSONDecodeError
from time import time
from zoneinfo import ZoneInfo
import json

from flask import Flask, Response, render_template
from flask import abort
from flask_caching import Cache
import requests

from .rss import RSSEntry, RSSFeed

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)


shows: dict[str, RSSFeed] = {}
stream_urls: dict[str, str] = {}


def get_show(show: str) -> RSSFeed:
    show = show.split("_")[-1]
    if show not in shows or shows[show].age + 3600 < time():
        url = "https://www.dr.dk/drtv/serie/" + show
        print("Fetching show", url)
        r = requests.get(url, timeout=2)
        if r.status_code != 200:
            abort(404)
        m = r.text
        snippet = "window.__data = "
        start = m.find(snippet) + len(snippet)
        end = len(m[start:])
        try:
            json.loads(m[start:])
        except JSONDecodeError as e:
            end = e.pos
        parsed = json.loads(m[start:start+end])
        page = parsed["cache"]["page"]
        series = page[list(page.keys())[0]]["item"]

        feed = RSSFeed(series["title"],
                       description=series["description"], url=url)

        for ep in series["episodes"]["items"]:
            # print(json.dumps(ep, indent=4))
            pubdate = datetime(year=ep["releaseYear"], month=1, day=1)
            try:
                pubdate = datetime.strptime(ep["customFields"]["ExtraDetails"].split(
                    " |")[0], "%d. %b %Y").astimezone(ZoneInfo("Europe/Copenhagen"))
            except:
                pass
            feed.add_entry(
                RSSEntry(ep["title"], description=ep["shortDescription"], url=ep["path"], pubdate=pubdate))

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
    e = None
    for entry in show.entries:
        if episode in entry.url:
            e = entry
    return render_template("video.html", s=show, e=e)


@app.route("/<showid>/")
@cache.cached(timeout=15 * 60)
def view_show(showid):
    show = get_show(showid)
    return render_template("show.html", s=show)


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
def get_feed(show):
    return Response(get_show(show).dump(), headers={"content-type": "application/rss+xml"})
