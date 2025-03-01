from datetime import datetime
from json.decoder import JSONDecodeError
from time import time
from zoneinfo import ZoneInfo
import json
import uuid

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

        feed = RSSFeed(series["show"]["title"],
                       description=series["show"]["description"], url=url)

        seasons = series["show"]["seasons"]["items"]
        for s in seasons:
            season_blob = get_jsonblob("https://www.dr.dk/drtv" + s["path"])
            season_episodes = season_blob["cache"]["page"][s["path"]
                                                           ]["item"]["episodes"]["items"]

            for ep in season_episodes:
                pubdate = datetime.now(tz=ZoneInfo("Europe/Copenhagen"))
                if "releaseYear" in ep:
                    pubdate = datetime(year=ep["releaseYear"], month=1, day=1)
                try:
                    pubdate = datetime.strptime(ep["customFields"]["ExtraDetails"].split(
                        " |")[0], "%d. %b %Y").astimezone(ZoneInfo("Europe/Copenhagen"))
                except:
                    pass
                try:
                    pubdate = datetime.fromisoformat(
                        ep["customFields"]["AvailableFrom"])
                except:
                    pass
                title = ep["id"]
                if "title" in ep:
                    title = ep["title"]
                if "contextualTitle" in ep:
                    title = ep["contextualTitle"]
                feed.add_entry(
                    RSSEntry(title, description=ep["shortDescription"], url=ep["path"], pubdate=pubdate))

        shows[show] = feed
    return shows[show]


def get_shows() -> dict[str, RSSFeed]:
    return shows


token: str = ""
token_expiry = datetime.fromisoformat("2025-02-20T03:16:49.1356687Z")


def get_token() -> str:
    global token, token_expiry
    if datetime.now(tz=ZoneInfo("UTC")) > token_expiry:
        # The api issues two tokens. UserProfile, the second one is used for search
        r = requests.post("https://isl.dr-massive.com/api/authorization/anonymous-sso?device=web_browser&lang=da&supportFallbackToken=true",
                          json={"deviceId": str(uuid.uuid4()), "scopes": ["Catalog"], "optout": True}).json()[1]
        token = r["value"]
        token_expiry = datetime.fromisoformat(r["expirationDate"])
    return token


def search(query: str):
    r = requests.get("https://prod95.dr-massive.com/api/search?device=web_browser&ff=idp%2Cldp%2Crpt&group=true&lang=da&segments=drtv%2Coptedout&term=" + query, headers={
        "X-Authorization": f"Bearer {get_token()}"}).json()
    return [(i["id"], i["title"]) for i in r["series"]["items"]]
