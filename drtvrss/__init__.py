from datetime import datetime
from typing import Optional
import os

import asyncio

from flask import Flask, Response, render_template, redirect, request, send_from_directory
from flask_caching import Cache

from .drtv import get_show, get_shows, search, get_program, get_long_description

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)

complaints_email = os.getenv("KLAGE_MAIL", None)
SERVICE_NAME = os.getenv("SERVICE_NAME", "Public Service")

def birthday() -> Optional[int]:
    """If today is April 1st, returns the age of Danmarks Radio in years.
    On any other day of the year, return None"""
    n = datetime.now()
    if n.month == 4 and n.day == 1:
        return n.year - 1925
    return None


@app.route("/")
async def index():
    return render_template("index.html", shows=list(get_shows().items())[:9], complaints_email=complaints_email, SERVICE_NAME=SERVICE_NAME, birthday=birthday())


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "templates"), "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/program/<progid>")
async def view_program(progid):
    return render_template("video.html", e=await get_program(progid), SERVICE_NAME=SERVICE_NAME, birthday=birthday())


@app.route("/<showid>/<episode>")
@cache.cached(timeout=15 * 60)
async def view_episode(showid, episode):
    show = await get_show(showid)
    e = None
    for season in show.seasons:
        for entry in season.episodes:
            if episode in entry.url:
                e = entry
    await get_long_description(e)
    return render_template("video.html", s=show, e=e, SERVICE_NAME=SERVICE_NAME, birthday=birthday())


@app.route("/<showid>/")
@cache.cached(timeout=15 * 60)
async def view_show(showid):
    show = await get_show(showid)
    return render_template("show.html", s=show, SERVICE_NAME=SERVICE_NAME, birthday=birthday())


@app.route("/drtv/serie/<showid>")
@app.route("/serie/<showid>")
async def longlink(showid):
    return redirect(f"/{showid}/", code=302)


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
async def get_feed(show):
    return Response((await get_show(show)).to_rss_feed(), headers={"content-type": "application/rss+xml"})


def make_search_cache_key():
    return request.args.get("query")


@app.route("/search/")
@cache.cached(timeout=15 * 60, make_cache_key=make_search_cache_key)
async def search_view():
    query = request.args.get("query")
    results = await search(query)
    return render_template("search.html", results=results, query=query, SERVICE_NAME=SERVICE_NAME, birthday=birthday())

# Taken from SO: https://stackoverflow.com/a/77949082
@app.before_request
async def fetch_recommended_shows():
    app.before_request_funcs[None].remove(fetch_recommended_shows)
    recommended_shows = os.getenv("RECOMMENDED_SHOWS", "")
    print(f"Fetching recommended shows {recommended_shows}")
    for rec_show in recommended_shows.split(":"):
        if rec_show == "":
            continue
        await get_show(rec_show)
