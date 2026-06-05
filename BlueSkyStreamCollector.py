#EC portion: Multi-Crawler Architecture, implemented in Part B as an extension of Part A


import asyncio
#from requests import session
import websockets
import json
import os
import re
#import requests
import aiohttp
from bs4 import BeautifulSoup

OUTPUT_DIR = "data"
MAX_FILE_SIZE = 10 * 1024 * 1024

os.makedirs(OUTPUT_DIR, exist_ok=True)
post_queue = asyncio.Queue(maxsize=5000)
write_queue = asyncio.Queue(maxsize=5000)

def get_new_file(index):
    return open(f"{OUTPUT_DIR}/posts_{index}.jsonl", "a", encoding="utf-8")

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    if not match:
        return None
    return match.group(0).rstrip('.,!?)]}')

async def get_page_title(session, url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        async with session.get(url, headers=headers, timeout=3) as response:

            if response.status != 200:
                return None

            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
    except:
        return None
    return None

uri = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
async def worker(session):

    while True:

        post = await post_queue.get()

        url = post.get("url")

        if url and hash(url) % 10 == 0:
            title = await get_page_title(session, url)
            post["external_title"] = title
        else:
            post["external_title"] = None

        await write_queue.put(post)

        post_queue.task_done()
async def writer():

    file_index = 0
    current_file = get_new_file(file_index)

    count = 0

    while True:

        post = await write_queue.get()

        current_file.write(json.dumps(post, ensure_ascii=False) + "\n")
        current_file.flush()

        count += 1

        if count % 100 == 0:
            print(f"collected {count} posts")

        if current_file.tell() >= MAX_FILE_SIZE:
            current_file.close()

            file_index += 1

            current_file = get_new_file(file_index)

            print(f"created posts_{file_index}.jsonl")

        write_queue.task_done()

async def collect():

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
                        '''
                        if url and hash(url) % 10 == 0:
                            external_title = await get_page_title(url)
                        else:
                            external_title = None
                        '''

                        post = {
                            "text": text,
                            "created_at": record.get("createdAt"),
                            "author": data.get("did"),
                            "uri": commit.get("cid"),
                            "url": url,
                            "external_title": None
                        }

                        #current_file.write(json.dumps(post) + "\n")
                        await post_queue.put(post)

                        
                        '''
                        if count % 100 == 0:
                            print(f"collected {count} posts")

                        if current_file.tell() >= MAX_FILE_SIZE:
                            current_file.close()
                            file_index += 1
                            current_file = get_new_file(file_index)
                            print(f"created posts_{file_index}.jsonl")
                        '''
                    except asyncio.TimeoutError:
                        print("⚠️ timeout — reconnecting...")
                        break  

        except Exception:
            print("⚠️ connection error — retrying...")
            await asyncio.sleep(2)

#asyncio.run(collect())
NUM_WORKERS = 10

async def main():

    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        for _ in range(NUM_WORKERS):
            asyncio.create_task(worker(session))

        asyncio.create_task(writer())        
        await collect()

asyncio.run(main())
