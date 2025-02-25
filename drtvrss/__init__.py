from flask import Flask, Response, render_template, redirect, abort, request
from flask_caching import Cache

from .drtv import get_show, get_shows, search

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
@app.route("/serie/<showid>")
def longlink(showid):
    return redirect(f"/{showid}/", code=302)


@app.route("/<show>.xml")
@cache.cached(timeout=15 * 60)
def get_feed(show):
    return Response(get_show(show).dump(), headers={"content-type": "application/rss+xml"})


def make_search_cache_key():
    return request.args.get("query")


@app.route("/search/")
@cache.cached(timeout=15 * 60, make_cache_key=make_search_cache_key)
def search_view():
    query = request.args.get("query")
    results = search(query)
    print(results)
    return render_template("search.html", results=results, query=query)
