import asyncio
import json
import os
import re
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = "data"
MAX_FILE_SIZE = 10 * 1024 * 1024
TARGET_SIZE = 500 * 1024 * 1024 #500mb
FETCH_EXTERNAL_TITLES = False

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_new_file(index):
    return open(f"{OUTPUT_DIR}/posts_{index}.jsonl", "a", encoding="utf-8")

def get_total_output_size():
    total = 0
    for filename in os.listdir(OUTPUT_DIR):
        if filename.startswith("posts_") and filename.endswith(".jsonl"):
            total += os.path.getsize(os.path.join(OUTPUT_DIR, filename))
    return total

def get_latest_file_index():
    indexes = []
    for filename in os.listdir(OUTPUT_DIR):
        match = re.fullmatch(r"posts_(\d+)\.jsonl", filename)
        if match:
            indexes.append(int(match.group(1)))
    return max(indexes, default=0)

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    if not match:
        return None
    return match.group(0).rstrip('.,!?)]}')

def get_page_title(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
        }
        r = requests.get(url, headers=headers, timeout=2)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except requests.RequestException:
        return None
    return None

uri = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"

async def collect():
    file_index = get_latest_file_index()
    current_file = get_new_file(file_index)

    count = 0
    total_size = get_total_output_size()
    print(f"starting at {total_size / (1024 * 1024):.2f} MB collected")

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

                        if FETCH_EXTERNAL_TITLES and url and hash(url) % 10 == 0:
                            external_title = get_page_title(url)
                        else:
                            external_title = None

                        post = {
                            "text": text,
                            "created_at": record.get("createdAt"),
                            "author": data.get("did"),
                            "uri": commit.get("cid"),
                            "url": url,
                            "external_title": external_title,
                        }

                        line = json.dumps(post, ensure_ascii=False) + "\n"
                        current_file.write(line)

                        count += 1
                        total_size += len(line.encode("utf-8"))

                        if count % 100 == 0:
                            print(
                                f"collected {count} posts "
                                f"({total_size / (1024 * 1024):.2f} MB / "
                                f"{TARGET_SIZE / (1024 * 1024):.0f} MB)"
                            )

                        if current_file.tell() >= MAX_FILE_SIZE:
                            current_file.close()
                            file_index += 1
                            current_file = get_new_file(file_index)
                            print(f"created posts_{file_index}.jsonl")

                        if total_size >= TARGET_SIZE:
                            print(f"target reached: {total_size / (1024 * 1024):.2f} MB")
                            current_file.close()
                            return

                    except asyncio.TimeoutError:
                        print("⚠️ timeout — reconnecting...")
                        break  

        except Exception:
            print("⚠️ connection error — retrying...")
            await asyncio.sleep(2)

async def listen_to_websocket():
    await collect()


if __name__ == "__main__":
    asyncio.run(collect())