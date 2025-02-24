from datetime import datetime
from json.decoder import JSONDecodeError
from time import time
from zoneinfo import ZoneInfo
import json

from flask import abort
import requests

from .rss import RSSEntry, RSSFeed

shows: dict[str, RSSFeed] = {}


def get_jsonblob(url: str) -> dict:
    """Gets the JSON blob from some DRTV page"""
    print("Fetching DRTV page", url)
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
    return json.loads(m[start:start+end])


def get_show(show: str) -> RSSFeed:
    show = show.split("_")[-1]
    if show not in shows or shows[show].age + 3600 < time():
        url = "https://www.dr.dk/drtv/serie/" + show
        parsed = get_jsonblob(url)
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


def get_shows() -> dict[str, RSSFeed]:
    return shows
