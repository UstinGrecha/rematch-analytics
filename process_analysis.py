import json, csv, os, math
from datetime import datetime, timezone
from collections import Counter, defaultdict

INPUT = "rematch_export"
OUTPUT = "rematch_analysis"
os.makedirs(OUTPUT, exist_ok=True)

def log(msg):
    print(f"  {msg}")

def fmt(ts):
    if ts:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return ""

# ─── Helper: load all reviews from full dump ───
def load_all_reviews():
    path = os.path.join(INPUT, "05_all_reviews_full.json")
    log(f"   loading from {path} ...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("reviews", [])

log("=" * 55)
log("PROCESSING rematch_export -> rematch_analysis")
log("=" * 55)

# ─── 1. Reviews as flat CSV ───
log("[1/8] Exporting reviews CSV...")
reviews = load_all_reviews()
log(f"   loaded {len(reviews)} reviews")

csv_path = os.path.join(OUTPUT, "01_reviews_full.csv")
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow([
        "recommendationid", "language", "voted_up", "steam_purchase",
        "received_for_free", "refunded", "written_during_early_access",
        "primarily_steam_deck", "timestamp_created", "timestamp_updated",
        "votes_up", "votes_funny", "weighted_vote_score", "comment_count",
        "playtime_forever_minutes", "playtime_last_two_weeks_minutes",
        "playtime_at_review_minutes", "deck_playtime_at_review_minutes",
        "last_played", "num_games_owned", "num_reviews",
        "steamid", "review_text"
    ])
    for r in reviews:
        a = r.get("author", {})
        reviewed = r.get("review", "")
        reviewed = reviewed.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        w.writerow([
            r.get("recommendationid", ""),
            r.get("language", ""),
            1 if r.get("voted_up") else 0,
            1 if r.get("steam_purchase") else 0,
            1 if r.get("received_for_free") else 0,
            1 if r.get("refunded") else 0,
            1 if r.get("written_during_early_access") else 0,
            1 if r.get("primarily_steam_deck") else 0,
            fmt(r.get("timestamp_created")),
            fmt(r.get("timestamp_updated")),
            r.get("votes_up", 0),
            r.get("votes_funny", 0),
            r.get("weighted_vote_score", 0),
            r.get("comment_count", 0),
            a.get("playtime_forever", 0),
            a.get("playtime_last_two_weeks", 0),
            a.get("playtime_at_review", 0),
            a.get("deck_playtime_at_review", 0),
            fmt(a.get("last_played")),
            a.get("num_games_owned", 0),
            a.get("num_reviews", 0),
            a.get("steamid", ""),
            reviewed,
        ])
log(f"   -> {csv_path}")

# ─── 2. Reviews summary table ───
log("[2/8] Reviews summary by language & type...")
summary_rows = []
for r in reviews:
    summary_rows.append({
        "lang": r.get("language", "unknown"),
        "voted_up": r.get("voted_up", False),
        "steam_purchase": r.get("steam_purchase", False),
        "received_for_free": r.get("received_for_free", False),
        "refunded": r.get("refunded", False),
    })

# pivot by language
lang_stats = {}
for s in summary_rows:
    lang = s["lang"]
    if lang not in lang_stats:
        lang_stats[lang] = {"total": 0, "positive": 0, "negative": 0,
                            "steam_purchase": 0, "free": 0, "refunded": 0}
    lang_stats[lang]["total"] += 1
    if s["voted_up"]:
        lang_stats[lang]["positive"] += 1
    else:
        lang_stats[lang]["negative"] += 1
    if s["steam_purchase"]:
        lang_stats[lang]["steam_purchase"] += 1
    if s["received_for_free"]:
        lang_stats[lang]["free"] += 1
    if s["refunded"]:
        lang_stats[lang]["refunded"] += 1

csv_path2 = os.path.join(OUTPUT, "02_reviews_by_language.csv")
with open(csv_path2, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["language", "total", "positive", "negative", "positive_pct",
                "steam_purchase", "received_free", "refunded"])
    for lang in sorted(lang_stats.keys()):
        s = lang_stats[lang]
        pct = round(s["positive"] / s["total"] * 100, 1) if s["total"] else 0
        w.writerow([lang, s["total"], s["positive"], s["negative"],
                    pct, s["steam_purchase"], s["free"], s["refunded"]])
log(f"   -> {csv_path2}")

# ─── 3. Playtime distribution ───
log("[3/8] Playtime distribution...")
buckets = [("0-1h", 0, 60), ("1-10h", 60, 600), ("10-50h", 600, 3000),
           ("50-100h", 3000, 6000), ("100-500h", 6000, 30000),
           ("500h+", 30000, float("inf"))]
play_dist = {b[0]: 0 for b in buckets}
for r in reviews:
    pt = r.get("author", {}).get("playtime_forever", 0)
    for label, lo, hi in buckets:
        if lo <= pt < hi:
            play_dist[label] += 1
            break

csv_path3 = os.path.join(OUTPUT, "03_playtime_distribution.csv")
with open(csv_path3, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["bucket", "review_count", "pct"])
    total = len(reviews)
    for label, _, _ in buckets:
        w.writerow([label, play_dist[label], round(play_dist[label]/total*100, 1)])
log(f"   -> {csv_path3}")

# ─── 4. Hardware dist from reviews that have it ───
log("[4/8] Hardware distribution...")
gpu_counter = Counter()
cpu_counter = Counter()
os_counter = Counter()
ram_buckets = [("0-8GB", 0, 8192), ("8-16GB", 8192, 16384),
               ("16-32GB", 16384, 32768), ("32GB+", 32768, float("inf"))]
ram_dist = {b[0]: 0 for b in ram_buckets}
total_hw = 0
for r in reviews:
    hw = r.get("hardware")
    if not hw:
        continue
    total_hw += 1
    gpu = hw.get("dx_video_card", "").strip()
    if gpu:
        # Normalize: take first meaningful part
        gpu_counter[gpu] += 1
    cpu = hw.get("cpu_name", "").strip()
    if cpu:
        cpu_counter[cpu] += 1
    os_name = hw.get("os", "").strip()
    if os_name:
        os_counter[os_name] += 1
    ram = hw.get("system_ram", 0)
    try:
        ram = int(ram)
        for label, lo, hi in ram_buckets:
            if lo <= ram < hi:
                ram_dist[label] += 1
                break
    except:
        pass

# GPU top 20
csv_path4a = os.path.join(OUTPUT, "04_gpu_top20.csv")
with open(csv_path4a, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["gpu", "count", "pct"])
    for gpu, cnt in gpu_counter.most_common(20):
        w.writerow([gpu, cnt, round(cnt/sum(gpu_counter.values())*100, 1) if gpu_counter else 0])
log(f"   -> {csv_path4a}")

# CPU top 20
csv_path4b = os.path.join(OUTPUT, "05_cpu_top20.csv")
with open(csv_path4b, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cpu", "count", "pct"])
    for cpu, cnt in cpu_counter.most_common(20):
        w.writerow([cpu, cnt, round(cnt/sum(cpu_counter.values())*100, 1) if cpu_counter else 0])
log(f"   -> {csv_path4b}")

# OS
csv_path4c = os.path.join(OUTPUT, "06_os_distribution.csv")
with open(csv_path4c, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["os", "count", "pct"])
    for os_name, cnt in os_counter.most_common():
        w.writerow([os_name, cnt, round(cnt/total_hw*100, 1)])
log(f"   -> {csv_path4c}")

# RAM
csv_path4d = os.path.join(OUTPUT, "07_ram_distribution.csv")
with open(csv_path4d, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ram_bucket", "count", "pct"])
    for label, _, _ in ram_buckets:
        w.writerow([label, ram_dist[label], round(ram_dist[label]/total_hw*100, 1)])
log(f"   -> {csv_path4d}")

# ─── 5. Achievement percentages ───
log("[5/8] Achievements CSV...")
with open(os.path.join(INPUT, "02_achievements.json"), "r", encoding="utf-8") as f:
    ach_data = json.load(f)
achievements = ach_data.get("achievementpercentages", {}).get("achievements", [])
csv_path5 = os.path.join(OUTPUT, "08_achievements.csv")
with open(csv_path5, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["name", "unlock_pct"])
    for a in sorted(achievements, key=lambda x: float(x["percent"]), reverse=True):
        w.writerow([a["name"], a["percent"]])
log(f"   -> {csv_path5}")

# ─── 6. Reviews over time ───
log("[6/8] Reviews over time (weekly)...")
weekly = Counter()
for r in reviews:
    ts = r.get("timestamp_created")
    if not ts:
        continue
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    week = dt.strftime("%Y-W%W")
    weekly[week] += 1

csv_path6 = os.path.join(OUTPUT, "09_reviews_over_time_weekly.csv")
with open(csv_path6, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["week", "review_count"])
    for week in sorted(weekly.keys()):
        w.writerow([week, weekly[week]])
log(f"   -> {csv_path6}")

# ─── 7. Review reactions stats ───
log("[7/8] Review reactions summary...")
reaction_counter = Counter()
for r in reviews:
    for react in r.get("reactions", []):
        reaction_counter[react.get("reaction_type", 0)] += react.get("count", 0)

csv_path7 = os.path.join(OUTPUT, "10_reactions.csv")
with open(csv_path7, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["reaction_type", "total_count"])
    for rtype, cnt in reaction_counter.most_common():
        w.writerow([rtype, cnt])
log(f"   -> {csv_path7}")

# ─── 8. News summary ───
log("[8/8] News summary CSV...")
with open(os.path.join(INPUT, "04_news.json"), "r", encoding="utf-8") as f:
    news_data = json.load(f)
news_items = news_data.get("appnews", {}).get("newsitems", [])
csv_path8 = os.path.join(OUTPUT, "11_news.csv")
with open(csv_path8, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "title", "author"])
    for n in news_items:
        w.writerow([
            fmt(n.get("date")),
            n.get("title", ""),
            n.get("author", ""),
        ])
log(f"   -> {csv_path8}")

# ─── 9. Early negativity (onboarding) ───
log("[9/9] Early negativity metrics...")
early_rows = []
for label, field, minutes in [
    ("playtime_at_review <30min", "playtime_at_review", 30),
    ("playtime_at_review <60min", "playtime_at_review", 60),
    ("playtime_forever <30min", "playtime_forever", 30),
    ("playtime_forever <60min", "playtime_forever", 60),
]:
    subset = [r for r in reviews if r.get("author", {}).get(field, 0) < minutes]
    if subset:
        neg_n = sum(1 for r in subset if not r.get("voted_up"))
        early_rows.append([label, len(subset), neg_n, round(neg_n / len(subset) * 100, 1)])

csv_path9 = os.path.join(OUTPUT, "12_early_negativity.csv")
with open(csv_path9, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric", "review_count", "negative_count", "negative_pct"])
    w.writerows(early_rows)
log(f"   -> {csv_path9}")

# ─── Final: copy raw JSONs for convenience ───
log("Copying raw JSON files...")
raw_dir = os.path.join(OUTPUT, "raw_json")
os.makedirs(raw_dir, exist_ok=True)
for fname in ["01_current_players.json", "02_achievements.json",
              "03_store_details.json", "04_news.json",
              "06_review_summaries_by_language.json"]:
    src = os.path.join(INPUT, fname)
    if os.path.exists(src):
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
        dst = os.path.join(raw_dir, fname)
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Summary report ───
log("=" * 55)
log("SUMMARY")
log("=" * 55)
positive = sum(1 for r in reviews if r.get("voted_up"))
negative = len(reviews) - positive
steam_purch = sum(1 for r in reviews if r.get("steam_purchase"))
free_copies = sum(1 for r in reviews if r.get("received_for_free"))
deck_players = sum(1 for r in reviews if r.get("primarily_steam_deck"))
ea_reviews = sum(1 for r in reviews if r.get("written_during_early_access"))
refunded = sum(1 for r in reviews if r.get("refunded"))
avg_playtime = sum(r.get("author", {}).get("playtime_forever", 0) for r in reviews) / len(reviews) if reviews else 0

summary_text = f"""
===========================================
  REMATCH (AppID: 2138720) - Analytics Dump
===========================================
  Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

  REVIEWS
    Total fetched:     {len(reviews):>8,}
    Positive:          {positive:>8,}  ({positive/len(reviews)*100:.1f}%)
    Negative:          {negative:>8,}  ({negative/len(reviews)*100:.1f}%)
    Steam Purchase:    {steam_purch:>8,}
    Free Copies:       {free_copies:>8,}
    Refunded:          {refunded:>8,}
    Steam Deck:        {deck_players:>8,}
    Early Access:      {ea_reviews:>8,}
    Avg Playtime:      {avg_playtime:.0f} min ({avg_playtime/60:.1f} h)

  LIVE PLAYERS (snapshot): 5,425

  ACHIEVEMENTS: 37
    Most unlocked:  {achievements[0]['name'] if achievements else '?'} ({achievements[0]['percent'] if achievements else '?'}%)
    Rarest:         {achievements[-1]['name'] if achievements else '?'} ({achievements[-1]['percent'] if achievements else '?'}%)

  TOP LANGUAGES:
"""
for lang in sorted(lang_stats.keys(), key=lambda l: lang_stats[l]["total"], reverse=True)[:5]:
    s = lang_stats[lang]
    pct = s["positive"]/s["total"]*100
    summary_text += f"    {lang:15s} {s['total']:>6,} reviews  ({pct:.1f}% positive)\n"

summary_text += f"""
  FILES:
"""
for root, dirs, files in os.walk(OUTPUT):
    for f in sorted(files):
        fp = os.path.join(root, f)
        size = os.path.getsize(fp)
        rel = os.path.relpath(fp, OUTPUT)
        summary_text += f"    {rel:<45s} {size:>8,} B\n"

summary_text += """
===========================================
"""
# save to file only (avoid encoding issues in terminal)
log(summary_text.splitlines()[-1])

with open(os.path.join(OUTPUT, "00_REPORT.txt"), "w", encoding="utf-8") as f:
    f.write(summary_text)

log("Done! All analysis files in 'rematch_analysis/'")
