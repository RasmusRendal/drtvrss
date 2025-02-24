from flask import Flask, Response, render_template, redirect, abort
from flask_caching import Cache

from .drtv import get_show, get_shows

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)


@app.route("/")
def index():
    return render_template("index.html", shows=get_shows().items())


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


@app.route("/drtv/serie/<showid>")
def longestlink(showid):
    return redirect(f"/{showid}/", code=302)


@app.route("/serie/<showid>")
def longlink(showid):
    return redirect(f"/{showid}/", code=302)


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
def get_feed(show):
    return Response(get_show(show).dump(), headers={"content-type": "application/rss+xml"})
