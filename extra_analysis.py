# -*- coding: utf-8 -*-
"""REMATCH: финальный раунд анализа — текстовые фичи, n-граммы, кластеризация, выживаемость, онлайны."""

import csv, json, math, os, re, urllib.request, urllib.error
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.size": 10, "axes.facecolor": "#1a2330",
                      "figure.facecolor": "#0f1419", "text.color": "#e1e8ed",
                      "axes.labelcolor": "#e1e8ed", "axes.edgecolor": "#2a3340",
                      "xtick.color": "#8899aa", "ytick.color": "#8899aa",
                      "legend.facecolor": "#1a2330", "legend.edgecolor": "#2a3340",
                      "axes.titlecolor": "#8ab4f8"})

OUT = Path("rematch_extra_analysis")
OUT.mkdir(exist_ok=True)
CHARTS = OUT / "charts"
CHARTS.mkdir(exist_ok=True)

def log(msg):
    text = f"  {msg}"
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("cp1251", errors="replace").decode("cp1251"))

def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

reviews = read_csv("rematch_analysis/01_reviews_full.csv")
log(f"Загружено {len(reviews)} отзывов")

# ────────────────────────────────────────────────────────────
# 1. ИЗВЛЕЧЕНИЕ ФИЧ ИЗ ТЕКСТА
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("1. ИЗВЛЕЧЕНИЕ ФИЧ ИЗ ТЕКСТА ОТЗЫВОВ")
log("="*60)

# Словарь фич: ключевые слова → категория
FEATURES = {
    "сервер": "servers",
    "server": "servers",
    "servidor": "servers",
    "lag": "servers",
    "ping": "servers",
    "latency": "servers",
    "disconnect": "servers",
    "connection": "servers",
    "подключ": "servers",
    "matchmaking": "matchmaking",
    "матчмейк": "matchmaking",
    "поиск": "matchmaking",
    "queue": "matchmaking",
    "очеред": "matchmaking",
    "баланс": "balance",
    "balance": "balance",
    "оптимизац": "optimization",
    "optimization": "optimization",
    "fps": "optimization",
    "лаги": "optimization",
    "тормоз": "optimization",
    "график": "graphics",
    "graphics": "graphics",
    "графон": "graphics",
    "графоний": "graphics",
    "качество": "graphics",
    "цена": "price",
    "price": "price",
    "дорог": "price",
    "money": "price",
    "денег": "price",
    "стоит": "price",
    "battle pass": "monetization",
    "battlepass": "monetization",
    "косметик": "monetization",
    "cosmetics": "monetization",
    "skins": "monetization",
    "скин": "monetization",
    "shop": "monetization",
    "магазин": "monetization",
    "adidas": "monetization",
    "туториал": "tutorial",
    "tutorial": "tutorial",
    "обучен": "tutorial",
    "читер": "cheaters",
    "cheat": "cheaters",
    "hack": "cheaters",
    "хак": "cheaters",
    "b0t": "cheaters",
    "бот": "cheaters",
    "aimbot": "cheaters",
    "контент": "content",
    "content": "content",
    "update": "content",
    "обновл": "content",
    "patch": "content",
    "season": "content",
    "сезон": "content",
    "maps": "content",
    "карт": "content",
    "mode": "content",
    "режим": "content",
    "skimpy": "content",
    "dead game": "playerbase",
    "dead": "playerbase",
    "мертв": "playerbase",
    "игроков нет": "playerbase",
    "низк": "playerbase",
    "сообще": "playerbase",
    "community": "playerbase",
    "ранг": "ranked",
    "ranked": "ranked",
    "рейтинг": "ranked",
    "лиг": "ranked",
    "league": "ranked",
    "соревнова": "ranked",
    "competitive": "ranked",
    "solo": "ranked",
    "team": "ranked",
    "команд": "ranked",
    "друз": "social",
    "friend": "social",
    "соц": "social",
    "вместе": "social",
}

def extract_features(text):
    text_lower = text.lower()
    found = set()
    for kw, cat in FEATURES.items():
        if kw in text_lower:
            found.add(cat)
    return found

# Собираем фичи для негативных и позитивных отзывов
feature_neg = Counter()
feature_pos = Counter()
feature_total_neg = Counter()
feature_total_pos = Counter()

for r in reviews:
    text = r['review_text']
    feats = extract_features(text)
    is_neg = r['voted_up'] == '0'
    for f in feats:
        if is_neg:
            feature_neg[f] += 1
        else:
            feature_pos[f] += 1
        if is_neg:
            feature_total_neg[f] += 1
        else:
            feature_total_pos[f] += 1

# Доля негатива по каждой фиче
feature_names_ru = {
    "servers": "Сервера",
    "matchmaking": "Матчмейкинг",
    "balance": "Баланс",
    "optimization": "Оптимизация",
    "graphics": "Графика",
    "price": "Цена",
    "monetization": "Монетизация",
    "tutorial": "Туториал",
    "cheaters": "Читеры",
    "content": "Контент",
    "playerbase": "База игроков",
    "ranked": "Ранговый режим",
    "social": "Социальное",
}

log("  Фичи, упоминаемые в отзывах (с % негатива):")
log(f"  {'Фича':<20} {'Всего':>8} {'Негатив':>10} {'% негат.':>10}")
log("  " + "-"*50)
feature_stats = []
for feat in sorted(feature_names_ru.keys()):
    n_neg = feature_neg.get(feat, 0)
    n_pos = feature_pos.get(feat, 0)
    total = n_neg + n_pos
    pct_neg = n_neg / total * 100 if total > 5 else 0
    feature_stats.append((feat, total, n_neg, pct_neg))
    if total >= 10:
        log(f"  {feature_names_ru.get(feat, feat):<20} {total:>8} {n_neg:>10} {pct_neg:>8.1f}%")

# График
fig, ax = plt.subplots(figsize=(12, 6))
feats_plot = [(feature_names_ru.get(f, f), t, n, p) for f, t, n, p in feature_stats if t >= 20]
feats_plot.sort(key=lambda x: x[3], reverse=True)
labels = [f[0] for f in feats_plot]
vals = [f[3] for f in feats_plot]
totals = [f[1] for f in feats_plot]
colors = ['#ea4335' if v > 35 else '#34a853' for v in vals]
bars = ax.barh(range(len(labels)), vals, color=colors)
for i, (bar, v, t) in enumerate(zip(bars, vals, totals)):
    ax.text(v + 1, bar.get_y() + bar.get_height()/2, f'{v:.0f}% (n={t})',
            va='center', fontsize=9, color='#8899aa')
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("% негативных отзывов")
ax.set_title("Какие фичи чаще всего упоминаются в негативных отзывах")
ax.axvline(x=31.5, color="#888", linestyle="--", alpha=0.5)
ax.set_xlim(0, max(vals) + 25)
plt.tight_layout()
fig.savefig(CHARTS / "01_features_negativity.png", dpi=120)
plt.close()

# ────────────────────────────────────────────────────────────
# 2. N-GRAM АНАЛИЗ НЕГАТИВНЫХ ОТЗЫВОВ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("2. N-GRAM АНАЛИЗ НЕГАТИВНЫХ ОТЗЫВОВ")
log("="*60)

def tokenize(text):
    text = text.lower()
    return re.findall(r'[a-zа-яё]+', text)

def get_ngrams(tokens, n):
    return [' '.join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

stopwords = set(['the','a','an','is','it','not','to','in','for','of','and','on','at','by',
                 'with','or','as','be','this','that','was','are','but','from','have','has',
                 'had','its','all','can','will','just','very','too','so','no','if','do',
                 'does','did','done','get','got','been','being','i','my','me','we','our',
                 'you','your','he','she','it','they','them','their','what','which','who',
                 'would','could','should','may','might','shall','need','like','also','now',
                 'и','в','на','с','о','по','за','у','из','от','к','для','до','во',
                 'не','это','что','как','но','так','же','а','то','все','они','он','она',
                 'мы','вы','ты','меня','его','ее','их','нас','вас','мне','ему','ей',
                 'них','этот','эта','эти','того','это','тем','том','был','была','было',
                 'быть','будет','будут','есть','бы','даже','уже','еще','только','если',
                 'потому','чтобы','при','каждый','другой','такой','можно','надо','без',
                 'вот','когда','после','теперь','тут','там','здесь','это','ну','да',
                 'нет','более','менее','раз','них','него','нее','них','всех','всё',
                 'сам','сама','сами','самое','самые','другие','другой','других'])

stopwords_bigrams = {
    'i have', 'i am', 'i was', 'i can', 'i dont', 'i cant', 'i will',
    'it is', 'it was', 'it has', 'it will', 'it can', 'it does',
    'this is', 'there is', 'there are', 'that is', 'the game',
    'the game is', 'this game', 'the game has', 'i think',
    'i feel', 'i just', 'its just', 'its not', 'it’s just',
    'of the', 'in the', 'on the', 'at the', 'for the', 'with the',
    'to the', 'from the', 'and the', 'the the',
}

neg_texts = [r['review_text'] for r in reviews if r['voted_up'] == '0' and len(r['review_text']) > 30]
pos_texts = [r['review_text'] for r in reviews if r['voted_up'] == '1' and len(r['review_text']) > 30]

neg_bigrams = Counter()
neg_trigrams = Counter()
pos_bigrams = Counter()
pos_trigrams = Counter()

for text in neg_texts[:2000]:
    tokens = tokenize(text)
    for ng in get_ngrams(tokens, 2):
        if ng not in stopwords_bigrams and len(ng.split()[0]) > 2 and len(ng.split()[1]) > 2:
            neg_bigrams[ng] += 1
    for ng in get_ngrams(tokens, 3):
        words = ng.split()
        if all(len(w) > 2 for w in words):
            neg_trigrams[ng] += 1

for text in pos_texts[:2000]:
    tokens = tokenize(text)
    for ng in get_ngrams(tokens, 2):
        if ng not in stopwords_bigrams and len(ng.split()[0]) > 2 and len(ng.split()[1]) > 2:
            pos_bigrams[ng] += 1
    for ng in get_ngrams(tokens, 3):
        words = ng.split()
        if all(len(w) > 2 for w in words):
            pos_trigrams[ng] += 1

# ratio нег/поз для биграм
bigram_ratios = []
for ng, nc in neg_bigrams.most_common(200):
    pc = pos_bigrams.get(ng, 1)
    ratio = nc / max(pc, 1)
    if nc >= 10 and ratio > 2.0:
        bigram_ratios.append((ng, nc, pc, ratio))
bigram_ratios.sort(key=lambda x: x[3], reverse=True)

log("  Топ-20 биграм, характерных для негатива:")
log(f"  {'Биграмма':<30} {'Негатив':>8} {'Позитив':>8} {'Ratio':>8}")
log("  " + "-"*56)
for ng, nc, pc, ratio in bigram_ratios[:20]:
    log(f"  {ng:<30} {nc:>8} {pc:>8} {ratio:>7.1f}×")

# trigram ratios
trigram_ratios = []
for ng, nc in neg_trigrams.most_common(200):
    pc = pos_trigrams.get(ng, 1)
    ratio = nc / max(pc, 1)
    if nc >= 5 and ratio > 3.0:
        trigram_ratios.append((ng, nc, pc, ratio))
trigram_ratios.sort(key=lambda x: x[3], reverse=True)

log("  Топ-15 триграм, характерных для негатива:")
for ng, nc, pc, ratio in trigram_ratios[:15]:
    log(f"    '{ng}' — {nc}× в негативе vs {pc}× в позитиве (ratio={ratio:.1f})")

# ────────────────────────────────────────────────────────────
# 3. АНАЛИЗ ВРЕМЕНИ НАПИСАНИЯ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("3. АНАЛИЗ ВРЕМЕНИ НАПИСАНИЯ ОТЗЫВОВ")
log("="*60)

hour_sent = defaultdict(lambda: {"pos": 0, "neg": 0, "total": 0})
for r in reviews:
    try:
        dt = datetime.strptime(r['timestamp_created'][:16], "%Y-%m-%d %H:%M")
        h = dt.hour
        hour_sent[h]["total"] += 1
        if r['voted_up'] == '1':
            hour_sent[h]["pos"] += 1
        else:
            hour_sent[h]["neg"] += 1
    except:
        pass

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
hours = list(range(24))
hour_counts = [hour_sent[h]["total"] for h in hours]
hour_pcts = [hour_sent[h]["pos"]/hour_sent[h]["total"]*100 if hour_sent[h]["total"] else 0 for h in hours]

ax1.bar(hours, hour_counts, color="#4285f4", alpha=0.6)
ax1.set_ylabel("Количество отзывов")
ax1.set_title("Отзывы по часам")
ax1.set_xticks(hours)

ax2.bar(hours, hour_pcts, color="#34a853", alpha=0.7)
ax2.axhline(y=68.5, color="#ea4335", linestyle="--", alpha=0.5, label="Среднее 68.5%")
ax2.set_xlabel("Час (UTC)")
ax2.set_ylabel("% положительных")
ax2.set_xticks(hours)
ax2.legend()
plt.tight_layout()
fig.savefig(CHARTS / "02_reviews_by_hour.png", dpi=120)
plt.close()

log("  Пиковые часы написания отзывов:")
for h in sorted(hours, key=lambda h: hour_sent[h]["total"], reverse=True)[:5]:
    log(f"    {h:02d}:00 UTC — {hour_sent[h]['total']} отзывов ({hour_sent[h]['pos']/hour_sent[h]['total']*100:.1f}% пол.)")

# ────────────────────────────────────────────────────────────
# 4. SURVIVAL ANALYSIS — ПЛЕЙТАЙМ ДО УХОДА
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("4. SURVIVAL ANALYSIS — НА КАКОЙ МИНУТЕ БРОСАЮТ")
log("="*60)

# Используем playtime_at_review_minutes как прокси для времени,
# когда игрок решил написать отзыв (и вероятно, бросил или сделал паузу)
survival_bins = [0, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 3000, 6000, 10000, 20000, 50000, 100000]
survival_labels = ["<5м", "5-10м", "10-20м", "20-30м", "30-60м", "1-2ч", "2-5ч", "5-10ч", "10-20ч", "20-50ч", "50-100ч", "100-330ч", "330-830ч", "830-3.4кч", ">3.4кч"]

# Playtime at review — когда игрок написал отзыв
pat_review = [float(r['playtime_at_review_minutes']) for r in reviews]

fig, ax = plt.subplots(figsize=(12, 5))
counts_bins = []
for i in range(len(survival_bins)-1):
    c = sum(1 for p in pat_review if survival_bins[i] <= p < survival_bins[i+1])
    counts_bins.append(c)
total_pat = len(pat_review)
survival_pct = [(total_pat - sum(counts_bins[:i+1])) / total_pat * 100 for i in range(len(counts_bins))]

ax.bar(range(len(survival_labels)), [total_pat - sum(counts_bins[:i+1]) for i in range(len(counts_bins))],
       color="#fbbc04", alpha=0.6, label="Еще играют (кумулята)")
ax2_twin = ax.twinx()
ax2_twin.plot(range(len(survival_labels)), survival_pct, color="#ea4335", linewidth=2, marker='o', label="% выживших")
ax2_twin.axhline(y=50, color="#888", linestyle="--", alpha=0.5)
ax.set_xticks(range(len(survival_labels)))
ax.set_xticklabels(survival_labels, rotation=45, fontsize=8)
ax.set_title("Выживаемость: на каком плейтайме игроки пишут отзыв (и вероятно, уходят)")
ax.set_xlabel("Плейтайм до отзыва")
ax.set_ylabel("Количество игроков")
ax2_twin.set_ylabel("% выживших")
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2_twin.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2)
plt.tight_layout()
fig.savefig(CHARTS / "03_survival_curve.png", dpi=120)
plt.close()

# Точка, где 50% игроков уже ушли
med_idx = next((i for i, p in enumerate(survival_pct) if p < 50), len(survival_pct)-1)
log(f"  50% игроков пишут отзыв (и уходят) до {survival_labels[med_idx]}")

log("  Падение доли игроков по времени:")
for i, (lb, cnt) in enumerate(zip(survival_labels, counts_bins)):
    pct_left = survival_pct[i]
    if i < 3 or i % 2 == 0:
        log(f"    До {lb}: {total_pat - sum(counts_bins[:i+1]):>6} игроков ({pct_left:.1f}%) еще не написали отзыв")

# ────────────────────────────────────────────────────────────
# 5. КЛАСТЕРИЗАЦИЯ ИГРОКОВ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("5. КЛАСТЕРИЗАЦИЯ ИГРОКОВ ПО ПОВЕДЕНИЮ")
log("="*60)

# Простая кластеризация на основе K-means-like подход
# Признаки: playtime, playtime_at_review, voted_up, language (eng/not), steam_purchase, refunded
# для упрощения используем ручные сегменты
segments = {
    "Энтузиасты (>100ч, положительный)": [],
    "Долгие, но недовольные (>100ч, отрицательный)": [],
    "Средние (10-100ч, положительный)": [],
    "Средние недовольные (10-100ч, отрицательный)": [],
    "Новички (<10ч, положительный)": [],
    "Новички ушедшие (<10ч, отрицательный)": [],
}

for r in reviews:
    pt = float(r['playtime_forever_minutes']) / 60
    is_pos = r['voted_up'] == '1'
    if pt >= 100:
        key = "Энтузиасты (>100ч, положительный)" if is_pos else "Долгие, но недовольные (>100ч, отрицательный)"
    elif pt >= 10:
        key = "Средние (10-100ч, положительный)" if is_pos else "Средние недовольные (10-100ч, отрицательный)"
    else:
        key = "Новички (<10ч, положительный)" if is_pos else "Новички ушедшие (<10ч, отрицательный)"
    segments[key].append(r)

log(f"  {'Сегмент':<40} {'Кол-во':>8} {'%':>8}")
log("  " + "-"*58)
for seg_name, seg_data in segments.items():
    log(f"  {seg_name:<40} {len(seg_data):>8} {len(seg_data)/len(reviews)*100:>7.1f}%")

# Average playtime per segment
seg_stats = []
for seg_name, seg_data in segments.items():
    pts = [float(r['playtime_forever_minutes'])/60 for r in seg_data]
    pats = [float(r['playtime_at_review_minutes'])/60 for r in seg_data]
    refunds = sum(1 for r in seg_data if r['refunded'] == '1')
    steam_deck = sum(1 for r in seg_data if r['primarily_steam_deck'] == '1')
    seg_stats.append((seg_name, len(seg_data), np.mean(pts), np.mean(pats), refunds, steam_deck))

fig, ax = plt.subplots(figsize=(10, 5))
names = [s[0].split("(")[0].strip().split(",")[0] for s in seg_stats]
amounts = [s[1] for s in seg_stats]
colors = ['#34a853' if 'положительный' in s[0] else '#ea4335' for s in seg_stats]
bars = ax.barh(range(len(names)), amounts, color=colors)
for i, (bar, a) in enumerate(zip(bars, amounts)):
    ax.text(bar.get_width() + 200, bar.get_y() + bar.get_height()/2, str(a),
            va='center', fontsize=9, color='#8899aa')
ax.set_yticks(range(len(names)))
ax.set_yticklabels([s[0].replace(" (>100ч,", "\n>100ч").replace(" (10-100ч,", "\n10-100ч").replace(" (<10ч,", "\n<10ч") for s in seg_stats], fontsize=8)
ax.set_xlabel("Количество игроков")
ax.set_title("Сегментация игроков по плейтайму + тональность")
plt.tight_layout()
fig.savefig(CHARTS / "04_player_segments.png", dpi=120)
plt.close()

# ────────────────────────────────────────────────────────────
# 6. ПОПЫТКА ПОЛУЧИТЬ ИСТОРИЮ ОНЛАЙНА
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("6. ИСТОРИЯ ОНЛАЙНА (SteamDB)")
log("="*60)

steamdb_url = "https://steamdb.info/api/GetChart/?appid=2138720"
log(f"  Пробуем SteamDB API: {steamdb_url}")
try:
    req = urllib.request.Request(steamdb_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html_data = resp.read().decode("utf-8")
    # сохраняем
    with open(OUT / "steamdb_chart.json", "w", encoding="utf-8") as f:
        f.write(html_data)
    log(f"  Получено {len(html_data)} байт")
    # пытаемся распарсить
    try:
        chart_data = json.loads(html_data)
        log(f"  JSON ok, ключи: {list(chart_data.keys())[:5]}")
        if 'chart' in chart_data:
            log(f"  Точки данных: {len(chart_data['chart'])}")
            # рисуем
            points = chart_data['chart']
            if points and isinstance(points, list):
                dates = [datetime.fromtimestamp(p[0]) for p in points if len(p) >= 2]
                values = [p[1] for p in points if len(p) >= 2]
                fig, ax = plt.subplots(figsize=(14, 4))
                ax.plot(dates, values, color="#4285f4", linewidth=1.5)
                ax.set_title("REMATCH — Онлайн по дням (SteamDB)")
                ax.set_ylabel("Игроков онлайн")
                plt.xticks(rotation=45)
                plt.tight_layout()
                fig.savefig(CHARTS / "05_steamdb_player_history.png", dpi=120)
                plt.close()
                log(f"  График онлайна сохранен")
    except json.JSONDecodeError:
        log("  Не JSON — сохранили как HTML")
except Exception as e:
    log(f"  SteamDB API недоступен: {e}")
    # Fallback: пробуем SteamCharts
    try:
        alt_url = "https://steamcharts.com/app/2138720"
        log(f"  Пробуем SteamCharts: {alt_url}")
        req = urllib.request.Request(alt_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_data = resp.read().decode("utf-8")
        with open(OUT / "steamcharts_page.html", "w", encoding="utf-8") as f:
            f.write(html_data)
        # simple parse - look for numbers in chart data
        log(f"  HTML сохранен, ищем данные...")
        # match patterns like [new Date("2025-06"), 1234] or monthly table rows
        matches = re.findall(r'new Date\("(\d{4}-\d{2})"\),\s*(\d+)', html_data)
        if not matches:
            matches = re.findall(
                r'month-cell left">\s*([A-Za-z]+ \d{4})\s*</td>\s*<td class="right num-f">([\d.]+)',
                html_data,
            )
            if matches:
                dates_chart = [datetime.strptime(m[0], "%B %Y") for m in reversed(matches)]
                values_chart = [float(m[1]) for m in reversed(matches)]
                fig, ax = plt.subplots(figsize=(14, 4))
                ax.plot(dates_chart, values_chart, color="#34a853", linewidth=2, marker='o')
                ax.set_title("REMATCH — Средний онлайн по месяцам (SteamCharts)")
                ax.set_ylabel("Средний онлайн")
                plt.xticks(rotation=45)
                plt.tight_layout()
                fig.savefig(CHARTS / "05_steamcharts_monthly.png", dpi=120)
                plt.close()
                log(f"  График среднего онлайна по месяцам сохранен ({len(matches)} точек)")
                matches = []  # skip duplicate chart below
        if matches:
            log(f"  Найдено {len(matches)} точек данных")
            dates_chart = [datetime.strptime(m[0], "%Y-%m") for m in matches]
            values_chart = [int(m[1]) for m in matches]
            fig, ax = plt.subplots(figsize=(14, 4))
            ax.plot(dates_chart, values_chart, color="#34a853", linewidth=2, marker='o')
            ax.set_title("REMATCH — Средний онлайн по месяцам (SteamCharts)")
            ax.set_ylabel("Средний онлайн")
            plt.xticks(rotation=45)
            plt.tight_layout()
            fig.savefig(CHARTS / "05_steamcharts_monthly.png", dpi=120)
            plt.close()
            log(f"  График среднего онлайна по месяцам сохранен")
    except Exception as e2:
        log(f"  SteamCharts тоже недоступен: {e2}")

# ────────────────────────────────────────────────────────────
# 7. КОРРЕЛЯЦИЯ ДЛИНЫ ОТЗЫВА С ТОНАЛЬНОСТЬЮ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("7. ДЛИНА ОТЗЫВА VS ТОНАЛЬНОСТЬ")
log("="*60)

review_lengths_pos = []
review_lengths_neg = []
for r in reviews:
    text = r['review_text']
    length = len(text)
    if r['voted_up'] == '1':
        review_lengths_pos.append(length)
    else:
        review_lengths_neg.append(length)

log(f"  Средняя длина положительного отзыва: {np.mean(review_lengths_pos):.0f} символов")
log(f"  Средняя длина отрицательного отзыва: {np.mean(review_lengths_neg):.0f} символов")

# buckets
len_buckets = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 5000), (5000, 20000)]
log("  Тональность по длине отзыва:")
for lo, hi in len_buckets:
    n_pos = sum(1 for r in reviews if r['voted_up'] == '1' and lo <= len(r['review_text']) < hi)
    n_neg = sum(1 for r in reviews if r['voted_up'] == '0' and lo <= len(r['review_text']) < hi)
    total = n_pos + n_neg
    if total:
        log(f"    {lo}-{hi} символов: {n_pos}/{total} = {n_pos/total*100:.1f}% положительных")

# ────────────────────────────────────────────────────────────
# 8. ПРОЦЕНТ ИГРОКОВ С НИЗКИМ ПЛЕЙТАЙМОМ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("8. ДОЛЯ ИГРОКОВ С КРИТИЧЕСКИ НИЗКИМ ПЛЕЙТАЙМОМ")
log("="*60)

log(f"  Игроков с <30 мин: {sum(1 for r in reviews if float(r['playtime_forever_minutes'])/60 < 0.5)}")
log(f"  Игроков с <1 ч: {sum(1 for r in reviews if float(r['playtime_forever_minutes'])/60 < 1)}")
log(f"  Игроков с <2 ч: {sum(1 for r in reviews if float(r['playtime_forever_minutes'])/60 < 2)}")
log(f"  Игроков с <5 ч: {sum(1 for r in reviews if float(r['playtime_forever_minutes'])/60 < 5)}")

# Кто возвращает в первые 2 часа
sub_2h = [r for r in reviews if float(r['playtime_forever_minutes'])/60 < 2]
refunded_sub_2h = sum(1 for r in sub_2h if r['refunded'] == '1')
log(f"  Из <2ч: {refunded_sub_2h} возвратов ({refunded_sub_2h/len(sub_2h)*100:.1f}%)")
neg_sub_2h = sum(1 for r in sub_2h if r['voted_up'] == '0')
log(f"  Из <2ч: {neg_sub_2h} негативных ({neg_sub_2h/len(sub_2h)*100:.1f}%)")

# ────────────────────────────────────────────────────────────
# 9. ОТЗЫВЫ ПО МЕСЯЦАМ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("9. ОТЗЫВЫ ПО МЕСЯЦАМ")
log("="*60)

month_counts = Counter()
month_sent = defaultdict(lambda: {"pos": 0, "neg": 0})
for r in reviews:
    try:
        m = r['timestamp_created'][:7]
        month_counts[m] += 1
        if r['voted_up'] == '1':
            month_sent[m]["pos"] += 1
        else:
            month_sent[m]["neg"] += 1
    except:
        pass

log(f"  {'Месяц':<10} {'Отзывов':>8} {'% пол.':>8}")
log("  " + "-"*28)
for m in sorted(month_counts.keys()):
    s = month_sent[m]
    pct = s["pos"]/(s["pos"]+s["neg"])*100
    log(f"  {m:<10} {month_counts[m]:>8} {pct:>7.1f}%")

# ────────────────────────────────────────────────────────────
# ЗАПИСЬ РЕЗУЛЬТАТОВ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("ЗАПИСЬ ФАЙЛОВ...")

# CSV: feature extraction
with open(OUT / "feature_sentiment.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["feature", "name_ru", "total", "neg_count", "neg_pct"])
    for feat, total, n_neg, pct in feature_stats:
        w.writerow([feat, feature_names_ru.get(feat, feat), total, n_neg, round(pct, 1)])

# CSV: bigrams
with open(OUT / "neg_bigrams.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["bigram", "neg_count", "pos_count", "ratio"])
    for ng, nc, pc, ratio in bigram_ratios[:30]:
        w.writerow([ng, nc, pc, round(ratio, 1)])

# CSV: segments
with open(OUT / "player_segments.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["segment", "count", "avg_playtime_h", "avg_playtime_at_review_h", "refunds", "steam_deck"])
    w.writerows(seg_stats)

# CSV: hours
with open(OUT / "reviews_by_hour.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["hour", "count", "pos_pct"])
    for h in hours:
        s = hour_sent[h]
        if s["total"]:
            w.writerow([h, s["total"], round(s["pos"]/s["total"]*100, 1)])

log("  CSV-файлы сохранены")
log(f"\nГотово! Все файлы в {OUT}/")
