from typing import Optional
import xml.etree.ElementTree as ET
from datetime import datetime
from time import time


class Episode:
    def __init__(self, title, description: Optional[str] = None, url: Optional[str] = None, pubdate: Optional[datetime] = None, wallpaper: Optional[str] = None, len_minutes: Optional[int] = None, geo_restricted: bool = False):
        self.title = title
        self.description = description
        self.url = url
        self.pubdate = pubdate
        self.wallpaper = wallpaper
        self.len_minutes = len_minutes
        self.geo_restricted = geo_restricted
        if url is not None:
            self.ep_link = url.split("/")[-1]


class Season:
    def __init__(self, title: str):
        self.title = title
        self.episodes = []

    def add_episode(self, episode: Episode):
        self.episodes.append(episode)


class Show:
    def __init__(self, title: str, description: Optional[str] = None, url: Optional[str] = None, wallpaper: Optional[str] = None, geo_restricted: bool = False, next_episode: Optional[datetime] = None):
        self.title = title
        self.description = description
        self.url = url
        self.seasons = []
        self.age = time()
        self.wallpaper = wallpaper
        self.geo_restricted = geo_restricted
        if url is not None:
            self.feed_url = "/" + url + ".xml"
        self.next_episode = next_episode

    def add_season(self, season: Season):
        self.seasons.append(season)

    def to_rss_feed(self) -> str:
        rss = ET.Element("rss", attrib={"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        title = ET.SubElement(channel, "title")
        title.text = self.title
        ttl = ET.SubElement(channel, "ttl")
        ttl.text = "60"
        if self.description is not None:
            description = ET.SubElement(channel, "description")
            description.text = self.description
        if self.url is not None:
            url = ET.SubElement(channel, "link")
            url.text = self.url

        for season in self.seasons:
            for entry in season.episodes:
                item = ET.SubElement(channel, "item")
                title = ET.SubElement(item, "title")
                title.text = entry.title
                if entry.description is not None:
                    description = ET.SubElement(item, "description")
                    description.text = entry.description
                if self.url is not None and entry.url is not None:
                    url = ET.SubElement(item, "link")
                    url.text = "/" + self.url + "/" + entry.ep_link
                if entry.pubdate is not None:
                    pub_date = ET.SubElement(item, "pubDate")
                    pub_date.text = entry.pubdate.strftime(
                        "%a, %d %b %Y %H:%M:%S %z")

        return ET.tostring(rss, xml_declaration=True, encoding="unicode")


class Program:
    def __init__(self, title: str, description: Optional[str] = None, url: Optional[str] = None):
        self.title = title
        self.description = description
        self.url = url
        self.age = time()
