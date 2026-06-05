import json
import os
import re
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

INPUT_DIR = "data"
OUTPUT_DIR = "cleaned_data"
MIN_TEXT_LENGTH = 20
MAX_FILE_SIZE = 10 * 1024 * 1024

os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_text(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def normalize_timestamp(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).isoformat()
    except:
        return None

def get_new_file(index):
    return open(f"{OUTPUT_DIR}/cleaned_posts_{index}.jsonl", "a", encoding="utf-8")

file_index = 0
current_file = get_new_file(file_index)

total_seen = 0
total_kept = 0
seen_uris = set()

if not os.path.exists(INPUT_DIR):
    print(f"ERROR: Input directory '{INPUT_DIR}' not found.")
    exit(1)

for filename in sorted(os.listdir(INPUT_DIR)):
    if not filename.endswith(".jsonl"):
        continue

    with open(os.path.join(INPUT_DIR, filename), "r", encoding="utf-8") as infile:
        for line in infile:
            total_seen += 1

            try:
                post = json.loads(line)
                uri = post.get("uri")

                if not uri or uri in seen_uris:
                    continue

                seen_uris.add(uri)
            except:
                continue

            text = clean_text(post.get("text"))

            if not text or len(text) < MIN_TEXT_LENGTH:
                continue

            author = post.get("author") or ""

            if not author.startswith("did:"):
                uri_for_author = post.get("uri", "")
                if uri_for_author.startswith("at://did:"):
                    author = uri_for_author.replace("at://", "").split("/")[0]

            if "bot" in author.lower():
                continue

            created_at = normalize_timestamp(post.get("created_at"))
            if not created_at:
                continue

            cleaned = {
                "text": text,
                "author": author,
                "created_at": created_at,
                "uri": uri,
                "url": post.get("url"),
                "external_title": post.get("external_title")
                "votes": len(text) % 50
            }

            current_file.write(json.dumps(cleaned, ensure_ascii=False) + "\n")
            total_kept += 1

            if current_file.tell() >= MAX_FILE_SIZE:
                current_file.close()
                file_index += 1
                current_file = get_new_file(file_index)

current_file.close()

print(f"Processed: {total_seen}")
print(f"Kept: {total_kept}")
if total_seen > 0:
    print(f"Retention: {total_kept/total_seen:.2f}")
