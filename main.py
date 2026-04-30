import asyncio
import websockets
import json
import os
import requests
from bs4 import BeautifulSoup

# --- Settings ---
OUTPUT_DIR = "collected_data"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
seen_cids = set()  # for deduplication

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_current_file():
    i = 0
    while True:
        path = os.path.join(OUTPUT_DIR, f"posts_{i}.jsonl")
        if not os.path.exists(path) or os.path.getsize(path) < MAX_FILE_SIZE:
            return path
        i += 1

def fetch_url_title(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        return soup.title.string.strip() if soup.title else None
    except:
        return None

def extract_url(record):
    try:
        for facet in record.get("facets", []):
            for feature in facet.get("features", []):
                if feature.get("$type") == "app.bsky.richtext.facet#link":
                    return feature.get("uri")
    except:
        pass
    return None

uri = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"

async def listen_to_websocket():
    print("Starting to collect Bluesky posts...")
    async with websockets.connect(uri) as websocket:
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                if "commit" not in data or "record" not in data["commit"]:
                    continue

                record = data["commit"]["record"]
                cid = data["commit"].get("cid")

                # Skip duplicates
                if cid in seen_cids:
                    continue
                seen_cids.add(cid)

                post = {
                    "uri": data.get("did"),
                    "text": record.get("text"),
                    "createdAt": record.get("createdAt"),
                    "cid": cid,
                    "url_title": None
                }

                # URL enrichment
                url = extract_url(record)
                if url:
                    post["url"] = url
                    post["url_title"] = fetch_url_title(url)

                # Save to file
                out_file = get_current_file()
                with open(out_file, "a") as f:
                    f.write(json.dumps(post) + "\n")

                print(f"Saved post: {post['text'][:50] if post['text'] else '(no text)'}")

            except websockets.ConnectionClosed as e:
                print(f"Connection closed: {e}")
                break
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(listen_to_websocket())