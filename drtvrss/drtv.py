from collections import namedtuple
from datetime import datetime
from json.decoder import JSONDecodeError
from time import time
from zoneinfo import ZoneInfo
import json
import uuid

from flask import abort
import requests

from .show import Episode, Season, Show

shows: dict[str, Show] = {}

# Having some commonly used keys as constant is a good way to avoid typos
GEO_RESTRICTED = "IsGeoRestricted"
CUSTOM_FIELDS = "customFields"
RELEASE_YEAR = "releaseYear"


def get_jsonblob(url: str) -> dict:
    """Gets the JSON blob from some DRTV page"""
    print("Fetching DRTV page", url)
    r = requests.get(url, timeout=5)
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


def parse_len(s: str) -> int:
    t = 0
    if "T" in s:
        hours, s = s.split("T")
        t += int(hours) * 60
    while len(s) > 0 and s[0] == " ":
        s = s[1:]
    if s[-1] == "M":
        t += int(s[:-1])
    return t


def get_show(show: str) -> Show:
    show = show.split("_")[-1]
    if show not in shows or shows[show].age + 3600 < time():
        url = "https://www.dr.dk/drtv/serie/" + show
        parsed = get_jsonblob(url)
        page = parsed["cache"]["page"]
        series = page[list(page.keys())[0]]["item"]

        geo_restricted = False
        if GEO_RESTRICTED in series[CUSTOM_FIELDS]:
            geo_restricted = series[CUSTOM_FIELDS][GEO_RESTRICTED].lower(
            ) == "true"

        feed = Show(series["show"]["title"],
                    description=series["show"]["description"], url=url, wallpaper=series["images"]["wallpaper"], geo_restricted=geo_restricted)

        seasons = series["show"]["seasons"]["items"]
        for s in seasons:
            title = s["title"]
            if title == feed.title:
                if "seasonNumber" in s:
                    title = "Sæson " + str(s["seasonNumber"])
                elif RELEASE_YEAR in s:
                    title = str(s[RELEASE_YEAR])

            season_blob = get_jsonblob(
                "https://www.dr.dk/drtv" + s["path"])
            season_episodes = season_blob["cache"]["page"][s["path"]
                                                           ]["item"]["episodes"]["items"]

            season = Season(title)

            for ep in season_episodes:
                pubdate = datetime.now(tz=ZoneInfo("Europe/Copenhagen"))
                len_minutes = None
                if RELEASE_YEAR in ep:
                    try:
                        pubdate = datetime(
                            year=ep[RELEASE_YEAR], month=1, day=1)
                    except ValueError:
                        # Sometimes, they set RELEASE_YEAR to zero.
                        pass
                try:
                    date_part, len_part = ep[CUSTOM_FIELDS]["ExtraDetails"].split(
                        " | ")
                    len_minutes = parse_len(len_part)
                    pubdate = datetime.strptime(date_part, "%d. %b %Y").astimezone(
                        ZoneInfo("Europe/Copenhagen"))
                except:
                    pass
                try:
                    pubdate = datetime.fromisoformat(
                        ep[CUSTOM_FIELDS]["AvailableFrom"])
                except:
                    pass
                title = ep["id"]
                if "title" in ep:
                    title = ep["title"]
                if "contextualTitle" in ep:
                    title = ep["contextualTitle"]

                geo_restricted = False
                if GEO_RESTRICTED in ep[CUSTOM_FIELDS]:
                    geo_restricted = ep[CUSTOM_FIELDS][GEO_RESTRICTED].lower(
                    ) == "true"

                season.add_episode(
                    Episode(title, description=ep["shortDescription"], url=ep["path"], pubdate=pubdate, wallpaper=ep["images"]["wallpaper"], len_minutes=len_minutes, geo_restricted=geo_restricted))

            feed.add_season(season)

        shows[show] = feed
    return shows[show]


def get_shows() -> dict[str, Show]:
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


SearchResult = namedtuple(
    "SearchResult", ["title", "wallpaper", "description", "geo_restricted"])


def search(query: str):
    r = requests.get("https://prod95.dr-massive.com/api/search?device=web_browser&ff=idp%2Cldp%2Crpt&group=true&lang=da&segments=drtv%2Coptedout&term=" + query, headers={
        "X-Authorization": f"Bearer {get_token()}"}).json()
    return [(i["id"], SearchResult(i["title"], i["images"]["wallpaper"], i["shortDescription"], i[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true")) for i in r["series"]["items"]]
