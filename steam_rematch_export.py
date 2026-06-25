import httpx
import time
import json
import os
from datetime import datetime

APP_ID = 2138720
OUTPUT_DIR = "rematch_export"
MAX_RPS = 5
MIN_INTERVAL = 1.0 / MAX_RPS

os.makedirs(OUTPUT_DIR, exist_ok=True)

client = httpx.Client(timeout=30)
_last_req = 0.0

def rate_limited():
    global _last_req
    now = time.monotonic()
    elapsed = now - _last_req
    if elapsed < MIN_INTERVAL:
        sleep = MIN_INTERVAL - elapsed
        time.sleep(sleep)
    _last_req = time.monotonic()

def get_json(url, params=None):
    rate_limited()
    r = client.get(url, params=params)
    r.raise_for_status()
    return r.json()

def save_json(name, data):
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> saved {path}  ({len(json.dumps(data, ensure_ascii=False))} bytes)")
    return path

# ─── 1. Current player count ───
print("[1/6] Current player count...")
data = get_json("https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/", {"appid": APP_ID})
save_json("01_current_players.json", data)

# ─── 2. Achievement percentages ───
print("[2/6] Achievement percentages...")
data = get_json("https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/", {"gameid": APP_ID})
save_json("02_achievements.json", data)

# ─── 3. Store details ───
print("[3/6] Store details...")
data = get_json("https://store.steampowered.com/api/appdetails", {"appids": APP_ID})
save_json("03_store_details.json", data)

# ─── 4. News ───
print("[4/6] News (latest 20)...")
data = get_json("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/", {"appid": APP_ID, "count": 20, "maxlength": 500})
save_json("04_news.json", data)

# ─── 5. All reviews with full data (save incrementally) ───
print("[5/6] All reviews (paginating, saving every 20 pages)...")
CHUNK_SIZE = 20  # save every N pages
SAVE_DIR = os.path.join(OUTPUT_DIR, "reviews_chunks")
os.makedirs(SAVE_DIR, exist_ok=True)

all_reviews = []
cursor = "*"
page = 0
chunk_idx = 0

while cursor:
    page += 1
    params = {
        "json": 1,
        "filter": "recent",
        "language": "all",
        "review_type": "all",
        "purchase_type": "all",
        "num_per_page": 100,
        "cursor": cursor,
    }
    resp = get_json("https://store.steampowered.com/appreviews/2138720", params)
    reviews_batch = resp.get("reviews", [])
    all_reviews.extend(reviews_batch)
    print(f"   page {page}: got {len(reviews_batch)} reviews (total: {len(all_reviews)})")

    if page % CHUNK_SIZE == 0:
        chunk_idx += 1
        chunk_start = page - CHUNK_SIZE + 1
        chunk_reviews = all_reviews[-(CHUNK_SIZE * 100):]
        save_json(f"reviews_chunks/chunk_{chunk_idx:04d}_pages{chunk_start}-{page}.json",
                  {"chunk": chunk_idx, "pages": f"{chunk_start}-{page}",
                   "count": len(chunk_reviews), "reviews": chunk_reviews})
        # also save cumulative checkpoint
        save_json(f"reviews_chunks/checkpoint_{chunk_idx:04d}_total{len(all_reviews)}.json",
                  {"total": len(all_reviews), "last_page": page})

    cursor = resp.get("cursor", "")
    if not reviews_batch:
        break

# save final partial chunk
if page % CHUNK_SIZE != 0:
    chunk_idx += 1
    chunk_start = page - (page % CHUNK_SIZE) + 1
    chunk_reviews = all_reviews[-(page % CHUNK_SIZE * 100):]
    save_json(f"reviews_chunks/chunk_{chunk_idx:04d}_pages{chunk_start}-{page}.json",
              {"chunk": chunk_idx, "pages": f"{chunk_start}-{page}",
               "count": len(chunk_reviews), "reviews": chunk_reviews})

# save full dump
print(f"   saving full dump ({len(all_reviews)} reviews)...")
save_json("05_all_reviews_full.json", {
    "total_fetched": len(all_reviews),
    "total_pages": page,
    "reviews": all_reviews,
})

save_json("05_all_reviews_meta.json", {
    "total_fetched": len(all_reviews),
    "total_pages": page,
    "total_chunks": chunk_idx,
})

# ─── 6. Reviews summary by language ───
print("[6/6] Review summaries by language...")
langs = ["english", "russian", "brazilian", "turkish", "spanish", "french",
         "german", "polish", "latam", "schinese", "italian", "koreana",
         "japanese", "tchinese", "portuguese"]
lang_summaries = {}
for lang in langs:
    try:
        data = get_json("https://store.steampowered.com/appreviews/2138720", {
            "json": 1, "filter": "all", "language": lang,
            "review_type": "all", "purchase_type": "all",
            "num_per_page": 1, "cursor": "*"
        })
        lang_summaries[lang] = data.get("query_summary", {})
        qs = lang_summaries[lang]
        print(f"   {lang}: total={qs.get('total_reviews')}, "
              f"positive={qs.get('total_positive')}, "
              f"negative={qs.get('total_negative')}, "
              f"score={qs.get('review_score_desc')}")
    except Exception as e:
        print(f"   {lang}: error - {e}")
save_json("06_review_summaries_by_language.json", lang_summaries)

# ─── Save metadata ───
all_files = []
for root, dirs, files in os.walk(OUTPUT_DIR):
    for f in sorted(files):
        if f.endswith(".json") and f != "_metadata.json":
            full = os.path.join(root, f)
            rel = os.path.relpath(full, OUTPUT_DIR)
            size = os.path.getsize(full)
            all_files.append({"file": rel, "bytes": size, "kb": round(size/1024, 1)})

meta = {
    "app_id": APP_ID,
    "app_name": "REMATCH",
    "export_time": datetime.utcnow().isoformat() + "Z",
    "total_reviews_fetched": len(all_reviews) if all_reviews else 0,
    "files": all_files,
}
save_json("_metadata.json", meta)

print(f"\nDone! All data saved to '{OUTPUT_DIR}/'")
print(f"Total reviews fetched: {len(all_reviews)}")
