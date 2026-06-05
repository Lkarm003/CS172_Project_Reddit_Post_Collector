import os
import sys
import json
from elasticsearch import Elasticsearch

def build_index(input_dir, index_name):
    es = Elasticsearch("http://localhost:9200")
    
    if not es.ping():
        print("ERROR: Could not connect to Elasticsearch. Make sure elasticsearch.bat is running.")
        sys.exit(1)

    mappings = {
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "external_title": {"type": "text"},
                "uri": {"type": "keyword"},
                "author": {"type": "keyword"},
                "created_at": {"type": "keyword"},
                "url": {"type": "keyword"}
            }
        }
    }

    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    es.indices.create(index=index_name, body=mappings)

    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory '{input_dir}' not found.")
        sys.exit(1)

    print(f"Building Elasticsearch index '{index_name}' from folder '{input_dir}'...")
    posts_indexed = 0

    for filename in sorted(os.listdir(input_dir)):
        if not filename.endswith(".jsonl"):
            continue
            
        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    post = json.loads(line)
                    
                    doc_body = {
                        "text": post.get("text", ""),
                        "external_title": post.get("external_title", ""),
                        "uri": post.get("uri", ""),
                        "author": post.get("author", ""),
                        "created_at": post.get("created_at", ""),
                        "url": post.get("url", "")
                    }
                    
                    es.index(index=index_name, body=doc_body)
                    posts_indexed += 1
                    
                    if posts_indexed % 1000 == 0:
                        print(f"Indexed {posts_indexed} posts...")

                except Exception as e:
                    continue
        
    print(f"Indexing complete. Total posts successfully indexed: {posts_indexed}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python indexer.py <input-dir> <index-name>")
        sys.exit(1)
    build_index(sys.argv[1], sys.argv[2])
