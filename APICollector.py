'''
import requests
import json
import os
import time
from bs4 import BeautifulSoup

from atproto import Client

client = Client()
client.login('lahari.karmuchi@gmail.com', 'w4pm-vmf4-t5cn-ym2g')
client.app.bsky.feed.get_feed({'feed': feed_uri, 'limit': 30, 'cursor': cursor})

BlueSki_Post:client.app.bsky.feed.get_feed({'feed': feed_uri, 'limit': 30, 'cursor': cursor})
'''
import asyncio
import websockets
import json

uri = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"

async def listen_to_websocket():
  async with websockets.connect(uri) as websocket:
    while True:
      try:
        message = await websocket.recv()
        data = json.loads(message)

        if "commit" not in data:
            continue

        if "record" not in data["commit"]:
            continue

        record = data["commit"]["record"]
        post = {
            "uri": record.get("uri"),
            "text": record.get("text"),
            "createdAt": record.get("createdAt"),
            "cid": data["commit"].get("cid"),
        }
        print(post)
      except websockets.ConnectionClosed as e:
        print(f"Connection closed: {e}")
        break
      except Exception as e:
        print(f"Error: {e}")

asyncio.run(listen_to_websocket())