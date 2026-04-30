import asyncio
import websockets
import json
import os
import re
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = "data"
MAX_FILE_SIZE = 10 * 1024 * 1024

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_new_file(index):
    return open(f"{OUTPUT_DIR}/posts_{index}.jsonl", "a", encoding="utf-8")

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    if not match:
        return None
    return match.group(0).rstrip('.,!?)]}')

def get_page_title(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        r = requests.get(url, headers=headers, timeout=2)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except:
        return None
    return None

uri = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"

async def collect():
    file_index = 0
    current_file = get_new_file(file_index)

    count = 0

    while True: 
        try:
            print("connecting...")
            async with websockets.connect(uri) as websocket:
                print("connected!")

                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=20)

                        data = json.loads(message)

                        if "commit" not in data:
                            continue

                        commit = data["commit"]
                        record = commit.get("record", {})

                        text = record.get("text", "")
                        if not text.strip():
                            continue

                        url = extract_url(text)

                        if url and hash(url) % 10 == 0:
                            external_title = get_page_title(url)
                        else:
                            external_title = None

                        post = {
                            "text": text,
                            "created_at": record.get("createdAt"),
                            "author": data.get("did"),
                            "uri": commit.get("cid"),
                            "url": url,
                            "external_title": external_title
                        }

                        current_file.write(json.dumps(post) + "\n")

                        count += 1

                        if count % 100 == 0:
                            print(f"collected {count} posts")

                        if current_file.tell() >= MAX_FILE_SIZE:
                            current_file.close()
                            file_index += 1
                            current_file = get_new_file(file_index)
                            print(f"created posts_{file_index}.jsonl")

                    except asyncio.TimeoutError:
                        print("⚠️ timeout — reconnecting...")
                        break  

        except Exception:
            print("⚠️ connection error — retrying...")
            await asyncio.sleep(2)

asyncio.run(collect())