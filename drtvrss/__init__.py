from flask import Flask, Response, render_template, redirect, abort, request
from flask_caching import Cache
import os

from .drtv import get_show, get_shows, search, get_program

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)

complaints_email = os.getenv("KLAGE_MAIL", None)
SERVICE_NAME = os.getenv("SERVICE_NAME", "Public Service")

for rec_show in os.getenv("RECOMMENDED_SHOWS", "").split(":"):
    if rec_show == "":
        continue
    get_show(rec_show)


@app.route("/")
def index():
    return render_template("index.html", shows=list(get_shows().items())[:9], complaints_email=complaints_email, SERVICE_NAME=SERVICE_NAME)


@app.route("/favicon.ico")
def favicon():
    abort(404)


@app.route("/program/<progid>")
def view_program(progid):
    return render_template("video.html", e=get_program(progid), SERVICE_NAME=SERVICE_NAME)


@app.route("/<showid>/<episode>")
@cache.cached(timeout=15 * 60)
def view_episode(showid, episode):
    show = get_show(showid)
    e = None
    for season in show.seasons:
        for entry in season.episodes:
            if episode in entry.url:
                e = entry
    return render_template("video.html", s=show, e=e, SERVICE_NAME=SERVICE_NAME)


@app.route("/<showid>/")
@cache.cached(timeout=15 * 60)
def view_show(showid):
    show = get_show(showid)
    return render_template("show.html", s=show, SERVICE_NAME=SERVICE_NAME)


@app.route("/drtv/serie/<showid>")
@app.route("/serie/<showid>")
def longlink(showid):
    return redirect(f"/{showid}/", code=302)


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
def get_feed(show):
    return Response(get_show(show).to_rss_feed(), headers={"content-type": "application/rss+xml"})


def make_search_cache_key():
    return request.args.get("query")


@app.route("/search/")
@cache.cached(timeout=15 * 60, make_cache_key=make_search_cache_key)
def search_view():
    query = request.args.get("query")
    results = search(query)
    return render_template("search.html", results=results, query=query, SERVICE_NAME=SERVICE_NAME)
