from collections import namedtuple
from datetime import datetime
from json.decoder import JSONDecodeError
from time import time
from zoneinfo import ZoneInfo
import json
import ssl
import uuid

import asyncio
import certifi
from aiohttp import ClientSession, TCPConnector

from flask import abort

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

ssl_context = ssl.create_default_context(cafile=certifi.where())


async def get_jsonblob(session: ClientSession, url: str) -> dict:
    """Gets the JSON blob from some DRTV page"""
    print("Fetching DRTV page", url)
    async with session.get(url, timeout=5) as r:
        if r.status != 200:
            abort(404)
        m = await r.text()
        snippet = "window.__data = "
        start = m.find(snippet) + len(snippet)
        end = len(m[start:])
        try:
            json.loads(m[start:])
        except JSONDecodeError as e:
            end = e.pos
        return json.loads(m[start : start + end])


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


async def get_show(show: str) -> Show:
    try:
        showid = int(show.split("_")[-1])
    except ValueError:
        abort(404)
    if showid not in shows or shows[showid].age + 3600 < time():
        async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
            url = "https://www.dr.dk/drtv/serie/" + str(showid)
            parsed = await get_jsonblob(session, url)
            page = parsed[CACHE]["itemDetail"]
            series = page[list(page.keys())[-1]][ITEM]

            geo_restricted = False
            if GEO_RESTRICTED in series[CUSTOM_FIELDS]:
                geo_restricted = series[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true"

            next_episode = None
            if NEXT_EPISODE in series[SHOW]:
                next_episode = datetime.fromtimestamp(
                    int(series[SHOW][NEXT_EPISODE]["availableUTC"])
                )

            feed = Show(
                series[SHOW][TITLE],
                description=series[SHOW]["description"],
                url=series[SHOW]["path"].split("/")[-1],
                wallpaper=series["images"]["wallpaper"],
                geo_restricted=geo_restricted,
                next_episode=next_episode,
            )

            seasons = series[SHOW]["seasons"]["items"]
            season_blob_urls = ["https://www.dr.dk/drtv" + s["path"] for s in seasons]

            async def fetch_season_blob(session, url):
                return (url, await get_jsonblob(session, url))

            tasks = [fetch_season_blob(session, url) for url in season_blob_urls]
            season_blobs = dict(await asyncio.gather(*tasks))

            for s in seasons:
                title = s[TITLE]
                if title == feed.title:
                    if "seasonNumber" in s:
                        title = "Sæson " + str(s["seasonNumber"])
                    elif RELEASE_YEAR in s:
                        title = str(s[RELEASE_YEAR])

                season_blob = season_blobs["https://www.dr.dk/drtv" + s["path"]]
                season_episodes = season_blob[CACHE][PAGE][s["path"]][ITEM]["episodes"][
                    "items"
                ]

                season = Season(title)

                for ep in season_episodes:
                    pubdate = datetime.now(tz=ZoneInfo("Europe/Copenhagen"))
                    len_minutes = None
                    if RELEASE_YEAR in ep:
                        try:
                            pubdate = datetime(year=ep[RELEASE_YEAR], month=1, day=1)
                        except ValueError:
                            # Sometimes, they set RELEASE_YEAR to zero.
                            pass
                    try:
                        date_part, len_part = ep[CUSTOM_FIELDS]["ExtraDetails"].split(
                            " | "
                        )
                        len_minutes = parse_len(len_part)
                        pubdate = datetime.strptime(date_part, "%d. %b %Y").astimezone(
                            ZoneInfo("Europe/Copenhagen")
                        )
                    except:
                        pass
                    try:
                        pubdate = datetime.fromisoformat(
                            ep[CUSTOM_FIELDS]["AvailableFrom"]
                        )
                    except:
                        pass
                    title = ep["id"]
                    if TITLE in ep:
                        title = ep[TITLE]
                    if "contextualTitle" in ep:
                        title = ep["contextualTitle"]

                    geo_restricted = False
                    if GEO_RESTRICTED in ep[CUSTOM_FIELDS]:
                        geo_restricted = (
                            ep[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true"
                        )

                    season.add_episode(
                        Episode(
                            title,
                            short_description=ep["shortDescription"],
                            url=ep["path"],
                            pubdate=pubdate,
                            wallpaper=ep["images"]["wallpaper"],
                            len_minutes=len_minutes,
                            geo_restricted=geo_restricted,
                        )
                    )

                feed.add_season(season)

            shows[showid] = feed
    return shows[showid]


def get_shows() -> dict[int, Show]:
    return shows


async def get_long_description(episode: Episode):
    if episode.description != "":
        return
    async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
        try:
            jb = await get_jsonblob(session, "https://dr.dk/drtv/" + episode.url)
            jb = jb[CACHE][PAGE]
            episode_blob = jb[list(jb.keys())[0]][ITEM]
            episode.description = episode_blob["description"]
        except:
            episode.description = episode.short_description


token: str = ""
token_expiry = datetime.fromisoformat("2025-02-20T03:16:49.1356687Z")


async def get_token() -> str:
    global token, token_expiry
    if datetime.now(tz=ZoneInfo("UTC")) > token_expiry:
        async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
            # The api issues two tokens. UserProfile, the second one is used for search
            async with session.post(
                "https://isl.dr-massive.com/api/authorization/anonymous-sso?device=web_browser&lang=da&supportFallbackToken=true",
                json={
                    "deviceId": str(uuid.uuid4()),
                    "scopes": ["Catalog"],
                    "optout": True,
                },
            ) as r:
                r = (await r.json())[1]
                token = r["value"]
                token_expiry = datetime.fromisoformat(r["expirationDate"])
    return token


async def get_program(prog: str) -> Program:
    async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
        try:
            progid = int(prog.split("_")[-1])
        except ValueError:
            abort(404)
        if progid not in programs or programs[progid].age + 3600 < time():
            jb = await get_jsonblob(
                session, f"https://www.dr.dk/drtv/program/{str(progid)}"
            )
            jb = jb[CACHE][PAGE]
            program_blob = jb[list(jb.keys())[0]][ITEM]
            programs[progid] = Program(
                program_blob[TITLE],
                program_blob["shortDescription"],
                url=program_blob["path"],
            )
        return programs[progid]


SearchResultItem = namedtuple(
    "SearchResultItem", ["title", "wallpaper", "description", "geo_restricted", "url"]
)


SearchResult = namedtuple("SearchResult", ["series", "movies"])


async def search(query: str) -> SearchResult:
    async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
        async with session.get(
            "https://prod95.dr-massive.com/api/search?device=web_browser&ff=idp%2Cldp%2Crpt&group=true&lang=da&segments=drtv%2Coptedout&term="
            + query,
            headers={"X-Authorization": f"Bearer {await get_token()}"},
        ) as r:
            r = await r.json()
            series = [
                (
                    i["id"],
                    SearchResultItem(
                        i[TITLE],
                        i["images"]["wallpaper"],
                        i["shortDescription"],
                        i[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true",
                        "/" + i["path"].split("/")[-1] + "/",
                    ),
                )
                for i in r["series"]["items"]
            ]
            # The returned JSON object actually does have a "movies" key, but it's always empty for some reason
            # Movies are stored in "playable"
            movies = [
                (
                    i["id"],
                    SearchResultItem(
                        i[TITLE],
                        i["images"]["wallpaper"],
                        i["shortDescription"],
                        i[CUSTOM_FIELDS][GEO_RESTRICTED].lower() == "true",
                        i["path"],
                    ),
                )
                for i in r["playable"]["items"]
                if "episode" not in i["path"]
            ]
            return SearchResult(series, movies)
