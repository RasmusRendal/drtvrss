from flask import Flask, Response, render_template
from flask import abort
from flask_caching import Cache

from .drtv import get_show, get_shows

app = Flask(__name__)
app.config.from_mapping({"CACHE_TYPE": "SimpleCache"})
cache = Cache(app)


@app.route("/")
def index():
    shows = get_shows()
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
