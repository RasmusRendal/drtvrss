from typing import Optional
import xml.etree.ElementTree as ET
from datetime import datetime
from time import time


class RSSEntry:
    def __init__(self, title, description: Optional[str] = None, url: Optional[str] = None, pubdate: Optional[datetime] = None, wallpaper: Optional[str] = None, len_minutes: Optional[int] = None):
        self.title = title
        self.description = description
        self.url = url
        self.pubdate = pubdate
        self.wallpaper = wallpaper
        self.len_minutes = len_minutes
        if url is not None:
            self.ep_link = url.split("/")[-1]


class RSSFeed:
    def __init__(self, title: str, description: Optional[str] = None, url: Optional[str] = None, wallpaper: Optional[str] = None):
        self.title = title
        self.description = description
        self.url = url
        self.entries = []
        self.age = time()
        self.wallpaper = wallpaper
        if url is not None:
            self.feed_url = url.split("/")[-1]

    def add_entry(self, entry: RSSEntry):
        self.entries.append(entry)

    def dump(self) -> str:
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

        for entry in self.entries:
            item = ET.SubElement(channel, "item")
            title = ET.SubElement(item, "title")
            title.text = entry.title
            if entry.description is not None:
                description = ET.SubElement(item, "description")
                description.text = entry.description
            if entry.url is not None:
                url = ET.SubElement(item, "link")
                url.text = entry.url
            if entry.pubdate is not None:
                pub_date = ET.SubElement(item, "pubDate")
                pub_date.text = entry.pubdate.strftime(
                    "%a, %d %b %Y %H:%M:%S %z")

        return ET.tostring(rss, xml_declaration=True, encoding="unicode")
