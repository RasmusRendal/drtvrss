import ssl
from time import time
from aiohttp import ClientSession, TCPConnector
import certifi

from .drtv import get_jsonblob

ssl_context = ssl.create_default_context(cafile=certifi.where())


class LiveChannel:
    def __init__(self, title, stream_url):
        self.title = title
        self.stream_url = stream_url


live_channels = None
last_fetch = 0


async def get_channels():
    global live_channels
    global last_fetch
    if last_fetch + 60 * 60 * 24 < time():
        async with ClientSession(connector=TCPConnector(ssl=ssl_context)) as session:
            blob = await get_jsonblob(session, "https://www.dr.dk/drtv/kanal/dr1_20875")
            blob = blob["cache"]["list"]
            blob = blob[list(blob.keys())[0]]["list"]["items"]
            channels = {}
            for channel in blob:
                channels[channel["channelShortCode"]] = LiveChannel(
                    channel["title"], channel["customFields"]["hlsURL"]
                )
            live_channels = channels
            last_fetch = time()
    return live_channels
