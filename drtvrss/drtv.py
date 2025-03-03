from collections import namedtuple
from datetime import datetime
from json.decoder import JSONDecodeError
from time import time
from zoneinfo import ZoneInfo
import json
import uuid

from flask import abort
import requests

from .show import Episode, Season, Show, Program

shows: dict[int, Show] = {}
programs: dict[int, Program] = {}

# Having some commonly used keys as constant is a good way to avoid typos
GEO_RESTRICTED = "IsGeoRestricted"
CUSTOM_FIELDS = "customFields"
RELEASE_YEAR = "releaseYear"
SHOW = "show"
TITLE = "title"
CACHE = "cache"
PAGE = "page"
ITEM = "item"
NEXT_EPISODE = "nextEpisode"


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
    try:
        showid = int(show.split("_")[-1])
    except ValueError:
        abort(404)
    if showid not in shows or shows[showid].age + 3600 < time():
        url = "https://www.dr.dk/drtv/serie/" + str(showid)
        parsed = get_jsonblob(url)
        page = parsed[CACHE][PAGE]
        series = page[list(page.keys())[0]][ITEM]

        geo_restricted = False
        if GEO_RESTRICTED in series[CUSTOM_FIELDS]:
            geo_restricted = series[CUSTOM_FIELDS][GEO_RESTRICTED].lower(
            ) == "true"

        next_episode = None
        if NEXT_EPISODE in series[SHOW]:
            next_episode = datetime.fromtimestamp(int(
                series[SHOW][NEXT_EPISODE]["availableUTC"]))

        feed = Show(series[SHOW][TITLE],
                    description=series[SHOW]["description"], url=series[SHOW]["path"].split("/")[-1], wallpaper=series["images"]["wallpaper"], geo_restricted=geo_restricted, next_episode=next_episode)

        seasons = series[SHOW]["seasons"]["items"]
        for s in seasons:
            title = s[TITLE]
            if title == feed.title:
                if "seasonNumber" in s:
                    title = "Sæson " + str(s["seasonNumber"])
                elif RELEASE_YEAR in s:
                    title = str(s[RELEASE_YEAR])

            season_blob = get_jsonblob(
                "https://www.dr.dk/drtv" + s["path"])
            season_episodes = season_blob[CACHE][PAGE][s["path"]
                                                       ][ITEM]["episodes"]["items"]

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
                if TITLE in ep:
                    title = ep[TITLE]
                if "contextualTitle" in ep:
                    title = ep["contextualTitle"]

                geo_restricted = False
                if GEO_RESTRICTED in ep[CUSTOM_FIELDS]:
                    geo_restricted = ep[CUSTOM_FIELDS][GEO_RESTRICTED].lower(
                    ) == "true"

                season.add_episode(
                    Episode(title, description=ep["shortDescription"], url=ep["path"], pubdate=pubdate, wallpaper=ep["images"]["wallpaper"], len_minutes=len_minutes, geo_restricted=geo_restricted))

            feed.add_season(season)

        shows[showid] = feed
    return shows[showid]


def get_shows() -> dict[int, Show]:
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


def get_program(prog: str) -> Program:
    try:
        progid = int(prog.split("_")[-1])
    except ValueError:
        abort(404)
    if progid not in programs or programs[progid].age + 3600 < time():
        jb = get_jsonblob(
            f"https://www.dr.dk/drtv/program/{str(progid)}")[CACHE][PAGE]
        program_blob = jb[list(jb.keys())[0]][ITEM]
        programs[progid] = Program(
            program_blob[TITLE], program_blob["shortDescription"], url=program_blob["path"])
    return programs[progid]


SearchResultItem = namedtuple(
    "SearchResultItem", ["title", "wallpaper", "description", "geo_restricted", "url"])


SearchResult = namedtuple("SearchResult", ["series", "movies"])


def search(query: str) -> SearchResult:
    r = requests.get("https://prod95.dr-massive.com/api/search?device=web_browser&ff=idp%2Cldp%2Crpt&group=true&lang=da&segments=drtv%2Coptedout&term=" + query, headers={
        "X-Authorization": f"Bearer {get_token()}"}).json()
    series = [(i["id"], SearchResultItem(i[TITLE], i["images"]["wallpaper"], i["shortDescription"],
                                         i[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true", "/" + i["path"].split("/")[-1] + "/")) for i in r["series"]["items"]]
    # The returned JSON object actually does have a "movies" key, but it's always empty for some reason
    # Movies are stored in "playable"
    movies = [(i["id"], SearchResultItem(i[TITLE], i["images"]["wallpaper"], i["shortDescription"],
                                         i[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true", i["path"])) for i in r["playable"]["items"] if "episode" not in i["path"]]
    return SearchResult(series, movies)
