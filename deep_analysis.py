import json, os, math
from datetime import datetime, timezone
from collections import Counter, defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INPUT = "rematch_export"
OUTPUT = "rematch_deep_analysis"
os.makedirs(OUTPUT, exist_ok=True)
CHARTS_DIR = os.path.join(OUTPUT, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

def log(msg):
    print(f"  {msg}")

def fmt(ts):
    if ts:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return ""

# ─── Load data ───
log("Loading data...")
with open(os.path.join(INPUT, "05_all_reviews_full.json"), "r", encoding="utf-8") as f:
    reviews = json.load(f)["reviews"]
with open(os.path.join(INPUT, "02_achievements.json"), "r", encoding="utf-8") as f:
    ach_data = json.load(f)
achievements = ach_data.get("achievementpercentages", {}).get("achievements", [])
with open(os.path.join(INPUT, "03_store_details.json"), "r", encoding="utf-8") as f:
    store = json.load(f)
log(f"Loaded {len(reviews)} reviews, {len(achievements)} achievements")

# ─── Statistical helpers (no scipy) ───
def ttest_ind(a, b):
    """Welch's t-test"""
    n1, n2 = len(a), len(b)
    m1, m2 = np.mean(a), np.mean(b)
    v1, v2 = np.var(a, ddof=1), np.var(b, ddof=1)
    se = math.sqrt(v1/n1 + v2/n2)
    if se == 0:
        return 0, 1.0
    t = (m1 - m2) / se
    # approximate df (Welch-Satterthwaite)
    num = (v1/n1 + v2/n2)**2
    denom = (v1/n1)**2/(n1-1) + (v2/n2)**2/(n2-1)
    df = num / denom if denom > 0 else 1
    # approximate p-value using normal (large df approximation)
    p = 2 * (1 - normal_cdf(abs(t)))
    return t, p, df

def normal_cdf(x):
    """standard normal CDF (Abramowitz & Stegun approximation)"""
    if x < 0:
        return 1 - normal_cdf(-x)
    k = 1 / (1 + 0.2316419 * x)
    c = k * (0.319381530 + k * (-0.356563782 + k * (1.781477937 + k * (-1.821255978 + 1.330274429 * k))))
    return 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-x*x/2) * c

def chi2_contingency(observed):
    """chi-square test for independence on 2x2 table"""
    obs = np.array(observed, dtype=float)
    row_sums = obs.sum(axis=1)
    col_sums = obs.sum(axis=0)
    total = obs.sum()
    expected = np.outer(row_sums, col_sums) / total
    chi2 = ((obs - expected) ** 2 / expected).sum()
    # 1 degree of freedom for 2x2
    p = 1 - chi2_cdf(chi2, 1)
    return chi2, p

def chi2_cdf(x, k):
    """chi-square CDF for k degrees of freedom"""
    if x <= 0:
        return 0
    # regularized lower incomplete gamma function (series approximation)
    return gamma_inc_lower(k/2, x/2) / math.gamma(k/2)

def gamma_inc_lower(a, x, eps=1e-10, max_iter=200):
    """lower incomplete gamma function (series)"""
    if x == 0:
        return 0
    s = 1 / a
    term = 1 / a
    for n in range(1, max_iter):
        term *= x / (a + n)
        s += term
        if abs(term) < eps * abs(s):
            break
    return math.exp(-x) * x**a * s

def z_test_prop(s1, n1, s2, n2):
    """two-proportion z-test"""
    p1 = s1 / n1
    p2 = s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
    if se == 0:
        return 0, 1.0
    z = (p1 - p2) / se
    p = 2 * (1 - normal_cdf(abs(z)))
    return z, p

def cohens_h(p1, p2):
    """Cohen's h effect size for proportions"""
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))

def cohens_d(a, b):
    """Cohen's d effect size"""
    n1, n2 = len(a), len(b)
    v1, v2 = np.var(a, ddof=1), np.var(b, ddof=1)
    s_pool = math.sqrt(((n1-1)*v1 + (n2-1)*v2) / (n1 + n2 - 2))
    if s_pool == 0:
        return 0
    return (np.mean(a) - np.mean(b)) / s_pool

def interpret_p(p):
    if p < 0.001:
        return "*** p<0.001"
    elif p < 0.01:
        return "** p<0.01"
    elif p < 0.05:
        return "* p<0.05"
    else:
        return "ns p>=0.05"

def interpret_d(d):
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    elif ad < 0.5:
        return "small"
    elif ad < 0.8:
        return "medium"
    else:
        return "large"

def interpret_h(h):
    ah = abs(h)
    if ah < 0.2:
        return "negligible"
    elif ah < 0.5:
        return "small"
    elif ah < 0.8:
        return "medium"
    else:
        return "large"

# ================================================================
# SECTION 1: A/B TESTS
# ================================================================
log("=" * 60)
log("SECTION 1: A/B TESTS")
log("=" * 60)

results = []

# ─── Helper arrays ───
pos_reviews = [r for r in reviews if r.get("voted_up")]
neg_reviews = [r for r in reviews if not r.get("voted_up")]
steam_purch = [r for r in reviews if r.get("steam_purchase")]
free_reviews = [r for r in reviews if r.get("received_for_free")]
deck_reviews = [r for r in reviews if r.get("primarily_steam_deck")]
non_deck = [r for r in reviews if not r.get("primarily_steam_deck")]

n_pos, n_neg = len(pos_reviews), len(neg_reviews)

# ─── Test 1: Playtime: positive vs negative ───
log("\n[Test 1] Playtime: positive vs negative reviewers")
pt_pos = np.array([r.get("author", {}).get("playtime_forever", 0) for r in pos_reviews], dtype=float)
pt_neg = np.array([r.get("author", {}).get("playtime_forever", 0) for r in neg_reviews], dtype=float)
t, p_val, df = ttest_ind(pt_pos, pt_neg)
d = cohens_d(pt_pos, pt_neg)
sig = interpret_p(p_val)
es = interpret_d(d)
log(f"   Positive: mean={np.mean(pt_pos)/60:.1f}h, median={np.median(pt_pos)/60:.1f}h")
log(f"   Negative: mean={np.mean(pt_neg)/60:.1f}h, median={np.median(pt_neg)/60:.1f}h")
log(f"   t={t:.3f}, p={p_val:.6f} {sig}, Cohen's d={d:.3f} ({es})")
results.append(("A1", "Playtime (min)", "Positive vs Negative", np.mean(pt_pos), np.mean(pt_neg), t, p_val, d, es))

# ─── Test 2: Steam Purchase vs Free copies ───
log("\n[Test 2] Sentiment: Steam purchasers vs free copies")
sp_pos = sum(1 for r in steam_purch if r.get("voted_up"))
sp_neg = len(steam_purch) - sp_pos
fr_pos = sum(1 for r in free_reviews if r.get("voted_up"))
fr_neg = len(free_reviews) - fr_pos
z, p_val2 = z_test_prop(sp_pos, len(steam_purch), fr_pos, len(free_reviews))
h = cohens_h(sp_pos/len(steam_purch), fr_pos/len(free_reviews))
sig2 = interpret_p(p_val2)
es2 = interpret_h(h)
log(f"   Steam purch: {sp_pos}/{len(steam_purch)} = {sp_pos/len(steam_purch)*100:.1f}% positive")
log(f"   Free copies: {fr_pos}/{len(free_reviews)} = {fr_pos/len(free_reviews)*100:.1f}% positive")
log(f"   z={z:.3f}, p={p_val2:.6f} {sig2}, Cohen's h={h:.3f} ({es2})")
results.append(("A2", "Positive rate", "Steam Purchase vs Free", sp_pos/len(steam_purch), fr_pos/len(free_reviews), z, p_val2, h, es2))

# ─── Test 3: Refunded vs not refunded ───
log("\n[Test 3] Playtime: refunded vs not refunded")
refunded = [r for r in reviews if r.get("refunded")]
not_refunded = [r for r in reviews if not r.get("refunded")]
pt_ref = np.array([r.get("author", {}).get("playtime_forever", 0) for r in refunded], dtype=float)
pt_nref = np.array([r.get("author", {}).get("playtime_forever", 0) for r in not_refunded], dtype=float)
t3, p3, _ = ttest_ind(pt_ref, pt_nref)
d3 = cohens_d(pt_ref, pt_nref)
sig3 = interpret_p(p3)
es3 = interpret_d(d3)
log(f"   Refunded: mean={np.mean(pt_ref)/60:.1f}h, median={np.median(pt_ref)/60:.1f}h, n={len(refunded)}")
log(f"   Not refunded: mean={np.mean(pt_nref)/60:.1f}h, median={np.median(pt_nref)/60:.1f}h")
log(f"   t={t3:.3f}, p={p3:.6f} {sig3}, d={d3:.3f} ({es3})")
results.append(("A3", "Playtime (min)", "Refunded vs Not", np.mean(pt_ref), np.mean(pt_nref), t3, p3, d3, es3))

# ─── Test 4: Steam Deck vs non-Deck ───
log("\n[Test 4] Sentiment: Steam Deck vs non-Deck")
deck_pos = sum(1 for r in deck_reviews if r.get("voted_up"))
deck_neg = len(deck_reviews) - deck_pos
nd_pos = sum(1 for r in non_deck if r.get("voted_up"))
nd_neg = len(non_deck) - nd_pos
z4, p4 = z_test_prop(deck_pos, len(deck_reviews), nd_pos, len(non_deck))
h4 = cohens_h(deck_pos/len(deck_reviews), nd_pos/len(non_deck))
sig4 = interpret_p(p4)
es4 = interpret_h(h4)
log(f"   Steam Deck: {deck_pos}/{len(deck_reviews)} = {deck_pos/len(deck_reviews)*100:.1f}%")
log(f"   Non-Deck: {nd_pos}/{len(non_deck)} = {nd_pos/len(non_deck)*100:.1f}%")
log(f"   z={z4:.3f}, p={p4:.6f} {sig4}, h={h4:.3f} ({es4})")
results.append(("A4", "Positive rate", "Steam Deck vs Non-Deck", deck_pos/len(deck_reviews), nd_pos/len(non_deck), z4, p4, h4, es4))

# ─── Test 5: Recent reviews (last 30d) vs older ───
log("\n[Test 5] Sentiment: recent (last 30d) vs older reviews")
now = datetime.now(timezone.utc).timestamp()
cutoff = now - 30 * 86400
recent = [r for r in reviews if r.get("timestamp_created", 0) >= cutoff]
older = [r for r in reviews if r.get("timestamp_created", 0) < cutoff]
rec_pos = sum(1 for r in recent if r.get("voted_up"))
rec_neg = len(recent) - rec_pos
old_pos = sum(1 for r in older if r.get("voted_up"))
old_neg = len(older) - old_pos
z5, p5 = z_test_prop(rec_pos, len(recent), old_pos, len(older))
h5 = cohens_h(rec_pos/len(recent), old_pos/len(older))
sig5 = interpret_p(p5)
es5 = interpret_h(h5)
log(f"   Recent: {rec_pos}/{len(recent)} = {rec_pos/len(recent)*100:.1f}% (n={len(recent)})")
log(f"   Older: {old_pos}/{len(older)} = {old_pos/len(older)*100:.1f}% (n={len(older)})")
log(f"   z={z5:.3f}, p={p5:.6f} {sig5}, h={h5:.3f} ({es5})")
results.append(("A5", "Positive rate", "Recent vs Older", rec_pos/len(recent), old_pos/len(older), z5, p5, h5, es5))

# ─── Test 6: English vs non-English ───
log("\n[Test 6] Sentiment: English vs non-English")
en_reviews = [r for r in reviews if r.get("language") == "english"]
non_en = [r for r in reviews if r.get("language") != "english"]
en_pos = sum(1 for r in en_reviews if r.get("voted_up"))
en_neg = len(en_reviews) - en_pos
ne_pos = sum(1 for r in non_en if r.get("voted_up"))
ne_neg = len(non_en) - ne_pos
z6, p6 = z_test_prop(en_pos, len(en_reviews), ne_pos, len(non_en))
h6 = cohens_h(en_pos/len(en_reviews), ne_pos/len(non_en))
sig6 = interpret_p(p6)
es6 = interpret_h(h6)
log(f"   English: {en_pos}/{len(en_reviews)} = {en_pos/len(en_reviews)*100:.1f}%")
log(f"   Non-English: {ne_pos}/{len(non_en)} = {ne_pos/len(non_en)*100:.1f}%")
log(f"   z={z6:.3f}, p={p6:.6f} {sig6}, h={h6:.3f} ({es6})")
results.append(("A6", "Positive rate", "English vs Non-English", en_pos/len(en_reviews), ne_pos/len(non_en), z6, p6, h6, es6))

# ─── Test 7: Playtime at review ───
log("\n[Test 7] Playtime at review: positive vs negative")
par_pos = np.array([r.get("author", {}).get("playtime_at_review", 0) for r in pos_reviews], dtype=float)
par_neg = np.array([r.get("author", {}).get("playtime_at_review", 0) for r in neg_reviews], dtype=float)
t7, p7, _ = ttest_ind(par_pos, par_neg)
d7 = cohens_d(par_pos, par_neg)
sig7 = interpret_p(p7)
es7 = interpret_d(d7)
log(f"   Positive: mean={np.mean(par_pos)/60:.1f}h, median={np.median(par_pos)/60:.1f}h")
log(f"   Negative: mean={np.mean(par_neg)/60:.1f}h, median={np.median(par_neg)/60:.1f}h")
log(f"   t={t7:.3f}, p={p7:.6f} {sig7}, d={d7:.3f} ({es7})")
results.append(("A7", "Playtime at review (min)", "Positive vs Negative", np.mean(par_pos), np.mean(par_neg), t7, p7, d7, es7))

# ─── Test 8: Language & sentiment (chi-square) ───
log("\n[Test 8] Sentiment by language (chi-square)")
lang_groups = ["english", "russian", "brazilian", "turkish", "spanish", "french", "german", "polish"]
lang_table = []
lang_labels = []
for lang in lang_groups:
    lang_r = [r for r in reviews if r.get("language") == lang]
    if len(lang_r) < 100:
        continue
    pos_l = sum(1 for r in lang_r if r.get("voted_up"))
    neg_l = len(lang_r) - pos_l
    lang_table.append([pos_l, neg_l])
    lang_labels.append(lang)
    log(f"   {lang:15s}: {pos_l:>5d} pos / {neg_l:>5d} neg ({pos_l/len(lang_r)*100:.1f}%)")
chi2, p8 = chi2_contingency(lang_table)
sig8 = interpret_p(p8)
log(f"   chi2={chi2:.3f}, p={p8:.6f} {sig8}")
# Cramer's V
n_total = sum(sum(row) for row in lang_table)
k = len(lang_table)
v = math.sqrt(chi2 / (n_total * (k - 1))) if n_total * (k - 1) > 0 else 0
log(f"   Cramer's V={v:.4f} ({'weak' if v<0.1 else 'moderate' if v<0.3 else 'strong'} association)")
results.append(("A8", "Language vs Sentiment", "Chi-square", chi2, 0, 0, p8, v, "Cramer's V"))

# ================================================================
# SECTION 2: CHARTS
# ================================================================
log("\n" + "=" * 60)
log("SECTION 2: CHARTS")
log("=" * 60)

plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['figure.dpi'] = 120

# ─── Chart 1: Playtime distribution ───
log("[Chart 1] Playtime distribution histogram...")
fig, ax = plt.subplots()
playtimes = np.array([r.get("author", {}).get("playtime_forever", 0) for r in reviews], dtype=float)
playtimes_hours = playtimes / 60
playtimes_hours = playtimes_hours[playtimes_hours < 500]  # clip outliers
ax.hist(playtimes_hours, bins=60, color="#4a90d9", edgecolor="white", alpha=0.85)
ax.set_xlabel("Playtime (hours)", fontsize=12)
ax.set_ylabel("Number of reviewers", fontsize=12)
ax.set_title("REMATCH - Playtime Distribution of Reviewers", fontsize=14, fontweight="bold")
ax.axvline(np.median(playtimes_hours), color="red", linestyle="--", label=f"Median: {np.median(playtimes_hours):.0f}h")
ax.axvline(np.mean(playtimes_hours), color="orange", linestyle=":", label=f"Mean: {np.mean(playtimes_hours):.0f}h")
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "01_playtime_distribution.png"), dpi=150)
plt.close(fig)
log("   saved")

# ─── Chart 2: Sentiment by language ───
log("[Chart 2] Sentiment by language bar chart...")
fig, ax = plt.subplots()
langs_sorted = sorted(lang_groups, key=lambda l: sum(1 for r in reviews if r.get("language")==l), reverse=True)
lang_data = []
for lang in langs_sorted:
    lang_r = [r for r in reviews if r.get("language") == lang]
    if len(lang_r) < 50:
        continue
    pos_l = sum(1 for r in lang_r if r.get("voted_up"))
    lang_data.append((lang, pos_l / len(lang_r) * 100, len(lang_r)))
labels = [f"{l} (n={n})" for l, p, n in lang_data]
values = [p for l, p, n in lang_data]
colors = ["#27ae60" if v >= 70 else "#e67e22" if v >= 50 else "#e74c3c" for v in values]
bars = ax.barh(range(len(labels)), values, color=colors, edgecolor="white")
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("Positive reviews (%)", fontsize=12)
ax.set_title("REMATCH - Review Sentiment by Language", fontsize=14, fontweight="bold")
ax.axvline(50, color="gray", linestyle="--", alpha=0.5)
for i, (v, bar) in enumerate(zip(values, bars)):
    ax.text(v + 0.5, bar.get_y() + bar.get_height()/2, f"{v:.1f}%", va="center", fontsize=9)
ax.set_xlim(0, 100)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "02_sentiment_by_language.png"), dpi=150)
plt.close(fig)

# ─── Chart 3: Reviews over time ───
log("[Chart 3] Reviews over time...")
weekly_counts = Counter()
for r in reviews:
    ts = r.get("timestamp_created")
    if not ts:
        continue
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    week = dt.strftime("%Y-%m-%d")
    weekly_counts[week] = weekly_counts.get(week, 0) + 1
sorted_weeks = sorted(weekly_counts.keys())
weekly_vals = [weekly_counts[w] for w in sorted_weeks]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
ax1.bar(range(len(sorted_weeks)), weekly_vals, color="#3498db", width=0.8)
ax1.set_xticks(range(0, len(sorted_weeks), max(1, len(sorted_weeks)//15)))
ax1.set_xticklabels([sorted_weeks[i] for i in range(0, len(sorted_weeks), max(1, len(sorted_weeks)//15))], rotation=45, fontsize=8)
ax1.set_ylabel("Reviews per day", fontsize=12)
ax1.set_title("REMATCH - Reviews Over Time (Daily)", fontsize=14, fontweight="bold")

# cumulative
cumulative = np.cumsum(weekly_vals)
ax2.fill_between(range(len(sorted_weeks)), cumulative, alpha=0.3, color="#2ecc71")
ax2.plot(range(len(sorted_weeks)), cumulative, color="#27ae60", linewidth=2)
ax2.set_xticks(range(0, len(sorted_weeks), max(1, len(sorted_weeks)//15)))
ax2.set_xticklabels([sorted_weeks[i] for i in range(0, len(sorted_weeks), max(1, len(sorted_weeks)//15))], rotation=45, fontsize=8)
ax2.set_ylabel("Cumulative reviews", fontsize=12)
ax2.set_xlabel("Date", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "03_reviews_over_time.png"), dpi=150)
plt.close(fig)

# ─── Chart 4: GPU distribution ───
log("[Chart 4] GPU top 10 pie chart...")
gpu_counter = Counter()
for r in reviews:
    hw = r.get("hardware")
    if hw:
        gpu = hw.get("dx_video_card", "").strip()
        if gpu:
            gpu_counter[gpu] += 1
total_gpu = sum(gpu_counter.values())
top_gpus = gpu_counter.most_common(10)
gpu_labels = [g.split("NVIDIA GeForce ")[-1].split("AMD Radeon ")[-1] for g, _ in top_gpus]
gpu_vals = [c for _, c in top_gpus]
gpu_labels = [f"{l} ({c/total_gpu*100:.1f}%)" for l, c in zip(gpu_labels, gpu_vals)]
fig, ax = plt.subplots()
wedges, texts, autotexts = ax.pie(gpu_vals, labels=None, autopct="", startangle=90,
    colors=plt.cm.Set3(np.linspace(0, 1, len(gpu_vals))))
ax.legend(wedges, gpu_labels, title="GPU (top 10)", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=8)
ax.set_title("REMATCH - GPU Distribution Among Reviewers", fontsize=14, fontweight="bold")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "04_gpu_distribution.png"), dpi=150, bbox_inches="tight")
plt.close(fig)

# ─── Chart 5: Playtime box plot: pos vs neg ───
log("[Chart 5] Playtime box plot: positive vs negative...")
fig, ax = plt.subplots()
pt_pos_clip = pt_pos[pt_pos < 30000] / 60
pt_neg_clip = pt_neg[pt_neg < 30000] / 60
bp = ax.boxplot([pt_pos_clip, pt_neg_clip], labels=["Positive", "Negative"],
                patch_artist=True, widths=0.5)
bp["boxes"][0].set_facecolor("#27ae60")
bp["boxes"][1].set_facecolor("#e74c3c")
ax.set_ylabel("Playtime (hours)", fontsize=12)
ax.set_title("REMATCH - Playtime: Positive vs Negative Reviews", fontsize=14, fontweight="bold")
# add sample sizes
ax.text(1, ax.get_ylim()[1]*0.95, f"n={len(pt_pos_clip):,}", ha="center", fontsize=10)
ax.text(2, ax.get_ylim()[1]*0.95, f"n={len(pt_neg_clip):,}", ha="center", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "05_playtime_pos_vs_neg.png"), dpi=150)
plt.close(fig)

# ─── Chart 6: Achievement unlock rates ───
log("[Chart 6] Achievement unlock rates...")
fig, ax = plt.subplots()
ach_sorted = sorted(achievements, key=lambda x: float(x["percent"]))
ach_names = [a["name"] for a in ach_sorted]
ach_pcts = [float(a["percent"]) for a in ach_sorted]
colors_ach = ["#3498db" if p > 50 else "#e67e22" if p > 20 else "#e74c3c" for p in ach_pcts]
bars = ax.barh(range(len(ach_names)), ach_pcts, color=colors_ach, edgecolor="white")
ax.set_yticks(range(len(ach_names)))
ax.set_yticklabels(ach_names, fontsize=7)
ax.set_xlabel("Players unlocked (%)", fontsize=12)
ax.set_title("REMATCH - Achievement Unlock Rates (n=37)", fontsize=14, fontweight="bold")
ax.set_xlim(0, 100)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "06_achievements.png"), dpi=150)
plt.close(fig)

# ─── Chart 7: RAM distribution ───
log("[Chart 7] RAM distribution...")
ram_vals = []
for r in reviews:
    hw = r.get("hardware")
    if hw:
        try:
            ram = int(hw.get("system_ram", 0))
            if 0 < ram < 262144:
                ram_vals.append(ram)
            ram_vals.append(ram)
        except:
            pass
ram_arr = np.array(ram_vals)
if len(ram_arr) > 0:
    fig, ax = plt.subplots()
    ax.hist(ram_arr / 1024, bins=20, color="#9b59b6", edgecolor="white", alpha=0.85)
    ax.set_xlabel("RAM (GB)", fontsize=12)
    ax.set_ylabel("Number of reviewers", fontsize=12)
    ax.set_title("REMATCH - System RAM Distribution", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "07_ram_distribution.png"), dpi=150)
    plt.close(fig)

# ─── Chart 8: OS distribution ───
log("[Chart 8] OS distribution pie...")
os_counter = Counter()
for r in reviews:
    hw = r.get("hardware")
    if hw:
        os_name = hw.get("os", "").strip()
        if os_name:
            os_counter[os_name] += 1
total_os = sum(os_counter.values())
top_os = os_counter.most_common(5)
os_labels = [f"{o} ({c/total_os*100:.1f}%)" for o, c in top_os]
os_vals = [c for _, c in top_os]
fig, ax = plt.subplots()
ax.pie(os_vals, labels=os_labels, autopct="", startangle=90,
       colors=["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6"])
ax.set_title("REMATCH - Operating System Distribution", fontsize=14, fontweight="bold")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "08_os_distribution.png"), dpi=150)
plt.close(fig)

# ─── Chart 9: Votes distribution ───
log("[Chart 9] Helpful votes distribution...")
votes_up = np.array([r.get("votes_up", 0) for r in reviews], dtype=float)
votes_up = votes_up[votes_up < 50]  # clip outliers
fig, ax = plt.subplots()
ax.hist(votes_up, bins=50, color="#1abc9c", edgecolor="white", alpha=0.85)
ax.set_xlabel("Helpful votes received", fontsize=12)
ax.set_ylabel("Number of reviews", fontsize=12)
ax.set_title("REMATCH - Distribution of Helpful Votes", fontsize=14, fontweight="bold")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "09_helpful_votes.png"), dpi=150)
plt.close(fig)

# ─── Chart 10: Weekend vs weekday ───
log("[Chart 10] Reviews by day of week...")
dow_counter = Counter()
for r in reviews:
    ts = r.get("timestamp_created")
    if not ts:
        continue
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    dow_counter[dt.weekday()] += 1
dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
dow_vals = [dow_counter.get(i, 0) for i in range(7)]
fig, ax = plt.subplots()
colors_dow = ["#e74c3c" if i >= 5 else "#3498db" for i in range(7)]
bars = ax.bar(dow_names, dow_vals, color=colors_dow, edgecolor="white")
ax.set_ylabel("Number of reviews", fontsize=12)
ax.set_title("REMATCH - Reviews by Day of Week", fontsize=14, fontweight="bold")
for bar, val in zip(bars, dow_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(dow_vals)*0.01, f"{val:,}", ha="center", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "10_reviews_by_dayofweek.png"), dpi=150)
plt.close(fig)

# ================================================================
# SECTION 3: CORRELATIONS
# ================================================================
log("\n" + "=" * 60)
log("SECTION 3: CORRELATIONS")
log("=" * 60)

def pearson_r(x, y):
    mask = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[mask], y[mask]
    if len(x) < 3:
        return 0, 1
    r = np.corrcoef(x, y)[0, 1]
    # t-test for correlation
    t = r * math.sqrt((len(x)-2) / (1 - r*r)) if abs(r) < 1 else float('inf')
    p = 2 * (1 - normal_cdf(abs(t)))
    return r, p

# Playtime vs weighted_vote_score
log("[Corr 1] Playtime vs weighted_vote_score...")
pts = np.array([r.get("author", {}).get("playtime_forever", 0) for r in reviews], dtype=float)
wvs = np.array([r.get("weighted_vote_score", 0) for r in reviews], dtype=float)
r1, p1 = pearson_r(pts, wvs)
log(f"   r={r1:.4f}, p={p1:.6f} {interpret_p(p1)}")
results.append(("C1", "Playtime vs Vote Score", "Pearson r", r1, 0, 0, p1, r1, ""))

# Playtime vs votes_up
log("[Corr 2] Playtime vs votes_up...")
vu = np.array([r.get("votes_up", 0) for r in reviews], dtype=float)
r2, p2 = pearson_r(pts, vu)
log(f"   r={r2:.4f}, p={p2:.6f} {interpret_p(p2)}")
results.append(("C2", "Playtime vs Votes Up", "Pearson r", r2, 0, 0, p2, r2, ""))

# votes_up vs weighted_vote_score
log("[Corr 3] votes_up vs weighted_vote_score...")
r3, p3 = pearson_r(vu, wvs)
log(f"   r={r3:.4f}, p={p3:.6f} {interpret_p(p3)}")
results.append(("C3", "Votes Up vs Vote Score", "Pearson r", r3, 0, 0, p3, r3, ""))

# Playtime at review vs playtime forever
log("[Corr 4] Playtime at review vs playtime forever...")
par_all = np.array([r.get("author", {}).get("playtime_at_review", 0) for r in reviews], dtype=float)
r4, p4 = pearson_r(pts, par_all)
log(f"   r={r4:.4f}, p={p4:.6f} {interpret_p(p4)}")
results.append(("C4", "Playtime@Review vs Playtime", "Pearson r", r4, 0, 0, p4, r4, ""))

# ================================================================
# SECTION 4: WRITE REPORT
# ================================================================
log("\n" + "=" * 60)
log("SECTION 4: WRITING REPORT")
log("=" * 60)

report = f"""
==========================================================
  REMATCH (AppID: 2138720) — DEEP ANALYTICS REPORT
  Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
==========================================================

1. OVERVIEW
-----------
  Total reviews analyzed:  {len(reviews):,}
  Positive:                {len(pos_reviews):,} ({len(pos_reviews)/len(reviews)*100:.1f}%)
  Negative:                {len(neg_reviews):,} ({len(neg_reviews)/len(reviews)*100:.1f}%)
  Steam Purchases:         {len(steam_purch):,}
  Free Copies:             {len(free_reviews):,}
  Refunded:                {len(refunded):,}
  Steam Deck:              {len(deck_reviews):,}
  Avg playtime:            {np.mean(pt_pos)/60:.1f}h (pos) / {np.mean(pt_neg)/60:.1f}h (neg)
  Median playtime:         {np.median(pt_pos)/60:.1f}h (pos) / {np.median(pt_neg)/60:.1f}h (neg)

2. A/B TEST RESULTS
-------------------
"""

# Format results table
header = f"  {'ID':<5s} {'Metric':<35s} {'Comparison':<35s} {'Group A':>12s} {'Group B':>12s} {'Stat':>8s} {'p-value':>10s} {'Effect':>10s} {'Interpretation':>15s}"
report += header + "\n" + "  " + "-"*140 + "\n"
for tid, metric, comp, val_a, val_b, stat, p_val, effect, interp in results:
    stat_s = f"{stat:.3f}" if isinstance(stat, float) else str(stat)
    p_s = f"{p_val:.6f}" if isinstance(p_val, float) else str(p_val)
    eff_s = f"{effect:.4f}" if isinstance(effect, float) else str(effect)
    if isinstance(val_a, float) and metric in ("Positive rate", "Language vs Sentiment"):
        val_a_s = f"{val_a*100:.1f}%"
    elif isinstance(val_a, float):
        val_a_s = f"{val_a:.1f}"
    else:
        val_a_s = str(val_a)
    if isinstance(val_b, float):
        val_b_s = f"{val_b*100:.1f}%" if "rate" in metric.lower() or "sentiment" in metric.lower() else f"{val_b:.1f}"
    else:
        val_b_s = str(val_b)
    report += f"  {tid:<5s} {metric:<35s} {comp:<35s} {val_a_s:>12s} {val_b_s:>12s} {stat_s:>8s} {p_s:>10s} {eff_s:>10s} {interp:>15s}\n"

report += """
3. KEY INSIGHTS
---------------
"""

# Generate insights
insights = []

# Insight 1: Playtime difference
if abs(np.mean(pt_pos) - np.mean(pt_neg)) > 60:
    if np.mean(pt_pos) > np.mean(pt_neg):
        insights.append(f"  * Positive reviewers have SIGNIFICANTLY higher playtime ({np.mean(pt_pos)/60:.1f}h vs {np.mean(pt_neg)/60:.1f}h).\n    Players who spend more time tend to leave positive reviews — the game gets better with playtime.")
    else:
        insights.append(f"  * Negative reviewers have higher playtime ({np.mean(pt_neg)/60:.1f}h vs {np.mean(pt_pos)/60:.1f}h).\n    This suggests experienced players are dissatisfied, possibly with endgame balance or lack of content.")

# Insight 2: Purchase type
if p_val2 < 0.05:
    sp_rate = sp_pos/len(steam_purch)*100
    fr_rate = fr_pos/len(free_reviews)*100
    if sp_rate > fr_rate:
        insights.append(f"  * Steam purchasers rate the game HIGHER ({sp_rate:.1f}%) than free-copy users ({fr_rate:.1f}%).\n    Paying users have higher investment and find more value.")
    else:
        insights.append(f"  * Free-copy users rate the game HIGHER ({fr_rate:.1f}%) than paying users ({sp_rate:.1f}%).\n    This may indicate price sensitivity or unmet expectations for paid features.")

# Insight 3: Language
if p6 < 0.05:
    en_rate = en_pos/len(en_reviews)*100
    ne_rate = ne_pos/len(non_en)*100
    if en_rate > ne_rate:
        insights.append(f"  * English reviews are more positive ({en_rate:.1f}%) than non-English ({ne_rate:.1f}%).\n    Potential localization or cultural gaps affect satisfaction.")
    else:
        insights.append(f"  * Non-English reviews are more positive ({ne_rate:.1f}%) than English ({en_rate:.1f}%).\n    English-speaking audience has higher expectations.")


# Insight 4: Deck
if p4 < 0.05:
    deck_rate = deck_pos/len(deck_reviews)*100
    nd_rate = nd_pos/len(non_deck)*100
    if deck_rate > nd_rate:
        insights.append(f"  * Steam Deck players are more satisfied ({deck_rate:.1f}% vs {nd_rate:.1f}%).\n    Steam Deck optimization is good and enhances the experience.")
    else:
        insights.append(f"  * Non-Deck players are more satisfied ({nd_rate:.1f}% vs {deck_rate:.1f}%).\n    Possible performance or control issues on Steam Deck.")

# Insight 5: Recent vs older
if p5 < 0.05:
    rec_rate = rec_pos/len(recent)*100
    old_rate = old_pos/len(older)*100
    if rec_rate > old_rate:
        insights.append(f"  * Recent reviews are more positive ({rec_rate:.1f}% vs {old_rate:.1f}%).\n    The game is improving over time with updates.")
    else:
        insights.append(f"  * Recent reviews are more negative ({rec_rate:.1f}% vs {old_rate:.1f}%).\n    Recent changes or lack of content may be hurting sentiment.")

# Insight 6: Weekend vs weekday
weekend_reviews = dow_counter.get(5, 0) + dow_counter.get(6, 0)
weekday_reviews = sum(dow_counter.get(i, 0) for i in range(5))
if weekend_reviews > 0 and weekday_reviews > 0:
    insights.append(f"  * {weekend_reviews:,} reviews written on weekends vs {weekday_reviews:,} on weekdays.\n    Weekend accounts for {weekend_reviews/(weekend_reviews+weekday_reviews)*100:.1f}% of all reviews.")

# Insight 7: Achievement rarity
ach_by_pct = sorted(achievements, key=lambda x: float(x["percent"]))
easy_ach = [a for a in ach_by_pct if float(a["percent"]) > 80]
hard_ach = [a for a in ach_by_pct if float(a["percent"]) < 10]
if easy_ach:
    insights.append(f"  * {len(easy_ach)} achievements unlocked by >80% of players ({', '.join(a['name'] for a in easy_ach[:3])}...).")
if hard_ach:
    insights.append(f"  * {len(hard_ach)} achievements unlocked by <10% of players ({', '.join(a['name'] for a in hard_ach[:3])}...).")
insights.append(f"  * Only {ach_by_pct[0]['percent']}% of players have all achievements — low completion rate typical for live-service games.")

# Insight 8: GPU distribution
if gpu_counter:
    top_gpu_name = gpu_counter.most_common(1)[0][0]
    top_gpu_pct = gpu_counter.most_common(1)[0][1] / total_gpu * 100
    insights.append(f"  * Most common GPU: {top_gpu_name} ({top_gpu_pct:.1f}% of reviewers).")

for ins in insights:
    report += ins + "\n"

report += """
4. CHARTS GENERATED
-------------------
"""
chart_files = sorted(os.listdir(CHARTS_DIR))
for cf in chart_files:
    fpath = os.path.join(CHARTS_DIR, cf)
    size = os.path.getsize(fpath)
    report += f"  - {cf} ({size//1024} KB)\n"

report += """
5. RECOMMENDATIONS
------------------
"""
recs = []
if abs(np.mean(pt_pos) - np.mean(pt_neg)) > 60 and np.mean(pt_pos) > np.mean(pt_neg):
    recs.append("  * Improve early-game experience to retain players who quit before discovering the fun")
if p_val2 < 0.05 and sp_pos/len(steam_purch) < fr_pos/len(free_reviews):
    recs.append("  * Review pricing strategy — free users are more satisfied than paying ones")
if p6 < 0.05 and en_pos/len(en_reviews) < ne_pos/len(non_en):
    recs.append("  * Investigate English-speaking community expectations and pain points")
if p4 < 0.05 and deck_pos/len(deck_reviews) < nd_pos/len(non_deck):
    recs.append("  * Improve Steam Deck experience (performance, controls, UI)")
if p5 < 0.05 and rec_pos/len(recent) < old_pos/len(older):
    recs.append("  * Recent decline in sentiment needs investigation — check recent patches/changes")
recs.append("  * Continue monitoring weekly review volume for community health trends")

if not recs:
    recs.append("  * No strong statistical effects found — maintain current course")

for rec in recs:
    report += rec + "\n"

report += f"""
==========================================================
  End of report — {len(reviews):,} reviews analyzed
==========================================================
"""

report_path = os.path.join(OUTPUT, "00_DEEP_REPORT.txt")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report)
log(f"Report saved: {report_path}")

# Also save A/B results as CSV
csv_path = os.path.join(OUTPUT, "ab_test_results.csv")
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    import csv as csvmod
    w = csvmod.writer(f)
    w.writerow(["TestID", "Metric", "Comparison", "GroupA_Value", "GroupB_Value", "Statistic", "p_value", "Effect_Size", "Interpretation"])
    for tid, metric, comp, val_a, val_b, stat, p_val, effect, interp in results:
        w.writerow([tid, metric, comp, val_a, val_b, stat, p_val, effect, interp])
log(f"A/B results: {csv_path}")

log("\nDone! Check 'rematch_deep_analysis/' for full report and charts")
