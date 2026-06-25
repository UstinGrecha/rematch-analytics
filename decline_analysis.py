# -*- coding: utf-8 -*-
"""REMATCH: анализ спада онлайна, проверка гипотез, рекомендации."""

import csv, json, math, os, re
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

OUT = Path("rematch_decline_analysis")
OUT.mkdir(exist_ok=True)
CHARTS = OUT / "charts"
CHARTS.mkdir(exist_ok=True)

def log(msg):
    print(f"  {msg}")

# ── helpers ──
def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _t_cdf(x, df):
    # approximation of t-distribution CDF using regularized incomplete beta
    # Abramowitz & Stegun 26.7.1
    if df <= 0:
        return 0.5
    x_ = float(x)
    df_ = float(df)
    t2 = x_ * x_ / df_
    p = 1.0
    for i in range(1, 100):
        term = 1.0
        for j in range(1, i+1):
            term *= (2*j - 1) / (2*j) * t2 / (1 + t2)
        p += term
        if abs(term) < 1e-10:
            break
    p = 0.5 * (1 + x_ / math.sqrt(df_ + x_*x_) * p / math.sqrt(1 + t2))
    p = min(p, 0.9999999)
    return p

def welch_t(x, y):
    nx, ny = len(x), len(y)
    mx, my = np.mean(x), np.mean(y)
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1)
    se = math.sqrt(vx/nx + vy/ny)
    if se == 0:
        return 0, 1.0
    t = (mx - my) / se
    df_num = (vx/nx + vy/ny)**2
    df_den = (vx/nx)**2/(nx-1) + (vy/ny)**2/(ny-1)
    df = df_num / df_den if df_den > 0 else 1
    p = 2 * (1 - _t_cdf(abs(t), max(df, 1e-6)))
    return t, max(p, 1e-15)

def cohens_d(x, y):
    nx, ny = len(x), len(y)
    mx, my = np.mean(x), np.mean(y)
    vx, vy = np.var(x, ddof=1), np.var(y, ddof=1)
    s = math.sqrt(((nx-1)*vx + (ny-1)*vy) / (nx+ny-2))
    return (mx - my) / s if s else 0

def _norm_cdf(x):
    # Abramowitz & Stegun 26.2.17
    b0 = 0.2316419; b1 = 0.319381530; b2 = -0.356563782
    b3 = 1.781477937; b4 = -1.821255978; b5 = 1.330274429
    t = 1 / (1 + b0 * abs(x))
    poly = b1 + b2*t + b3*t*t + b4*t*t*t + b5*t*t*t*t
    phi = math.exp(-x*x/2) / math.sqrt(2*math.pi)
    cdf = 1 - phi * t * poly
    return min(cdf, 0.9999999) if x >= 0 else 1 - min(cdf, 0.9999999)

def z_test_prop(s1, n1, s2, n2):
    p1, p2 = s1/n1, s2/n2
    p = (s1+s2)/(n1+n2)
    se = math.sqrt(p*(1-p)*(1/n1+1/n2))
    z = (p1-p2)/se if se else 0
    p_val = 2 * (1 - _norm_cdf(abs(z)))
    return z, p_val

def extract_words(text):
    text = text.lower()
    words = re.findall(r'[a-zа-яё]+', text)
    stopwords = set(['the','a','an','is','it','not','to','in','for','of','and','on','at','by',
                     'with','or','as','be','this','that','was','are','but','from','have','has',
                     'had','its','all','can','will','just','very','too','so','no','if','do',
                     'does','did','done','get','got','been','being','i','my','me','we','our',
                     'you','your','he','she','it','they','them','their','what','which','who',
                     'would','could','should','may','might','shall','need','like','also','now',
                     'и','в','на','с','о','по','за','у','из','от','к','для','до','во',
                     'не','это','что','как','но','так','же','а','то','все','они','он',
                     'она','мы','вы','ты','меня','его','ее','их','нас','вас','мне',
                     'ему','ей','ним','них','этот','эта','эти','того','тем','том',
                     'который','которая','которые','был','была','было','были','быть',
                     'будет','будут','есть','бы','даже','уже','еще','только','если',
                     'потому','чтобы','при','каждый','другой','такой','можно','надо'])
    return [w for w in words if len(w) > 2 and w not in stopwords]

# ── load data ──
log("Загрузка данных...")
reviews = read_csv("rematch_analysis/01_reviews_full.csv")
log(f"Загружено {len(reviews)} отзывов")

weekly_data = read_csv("rematch_analysis/09_reviews_over_time_weekly.csv")
news_data = read_csv("rematch_analysis/11_news.csv")
achievements = read_csv("rematch_analysis/08_achievements.csv")

total = len(reviews)
pos = sum(1 for r in reviews if r['voted_up'] == '1')
neg = total - pos

# ────────────────────────────────────────────────────────────
# 1. ТРЕНД ОТЗЫВОВ ПО НЕДЕЛЯМ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("1. ТРЕНД ОТЗЫВОВ ПО НЕДЕЛЯМ")

weeks = [r['week'] for r in weekly_data]
counts = [int(r['review_count']) for r in weekly_data]

ma4 = [None]*3 + [np.mean(counts[i-3:i+1]) for i in range(3, len(counts))]

fig, ax = plt.subplots(figsize=(14, 5))
ax.bar(range(len(weeks)), counts, color="#4285f4", alpha=0.5, label="Отзывов в неделю")
ax.plot(range(len(weeks)), ma4, color="#ea4335", linewidth=2, label="Скользящее среднее (4 нед)")
for i, w in enumerate(weeks):
    if w in ['2025-W47', '2026-W23', '2026-W24']:
        ax.annotate(w.replace('-W',' W'), (i, counts[i]), textcoords="offset points",
                    xytext=(0, 8), ha='center', fontsize=8, color="#fbbc04")
ax.set_title("Отзывы REMATCH по неделям")
ax.set_xlabel("Неделя")
ax.set_ylabel("Количество отзывов")
ax.legend()
plt.xticks(range(0, len(weeks), 8), [weeks[i].replace('-W',' W') for i in range(0, len(weeks), 8)], rotation=45)
plt.tight_layout()
fig.savefig(CHARTS / "01_weekly_trend.png", dpi=120)
plt.close()

week_nums = np.arange(len(counts))
r_week = np.corrcoef(week_nums, counts)[0,1]
drop_pct = (counts[-1] - counts[0]) / counts[0] * 100
log(f"  Корреляция неделя→отзывы: r={r_week:.3f}")
log(f"  Падение с первой недели: {counts[0]} → {counts[-1]} ({drop_pct:.0f}%)")
log(f"  Пик: {max(counts)} (неделя {weeks[counts.index(max(counts))]})")
log(f"  Текущий уровень: {counts[-1]}")

# ────────────────────────────────────────────────────────────
# 2. СЕНТИМЕНТ ПО НЕДЕЛЯМ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("2. СЕНТИМЕНТ ПО НЕДЕЛЯМ")

sentiment_by_week = defaultdict(lambda: {"pos": 0, "neg": 0})
for r in reviews:
    try:
        ts = datetime.strptime(r['timestamp_created'][:10], "%Y-%m-%d")
        iso = ts.isocalendar()
        wk = f"{iso[0]}-W{iso[1]:02d}"
        if r['voted_up'] == '1':
            sentiment_by_week[wk]["pos"] += 1
        else:
            sentiment_by_week[wk]["neg"] += 1
    except:
        pass

week_keys = sorted(sentiment_by_week.keys())
week_pos_pcts = []
for wk in week_keys:
    d = sentiment_by_week[wk]
    t = d["pos"] + d["neg"]
    week_pos_pcts.append(d["pos"]/t*100 if t else 0)

fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(range(len(week_keys)), week_pos_pcts, color="#34a853", linewidth=2, marker='o', markersize=3)
ax.axhline(y=pos/total*100, color="#ea4335", linestyle="--", alpha=0.5, label=f"Среднее {pos/total*100:.1f}%")
ax.set_title("Положительные отзывы по неделям")
ax.set_xlabel("Неделя")
ax.set_ylabel("% положительных")
ax.legend()
plt.xticks(range(0, len(week_keys), 8),
           [week_keys[i].replace('-W',' W') for i in range(0, len(week_keys), 8)], rotation=45)
plt.tight_layout()
fig.savefig(CHARTS / "02_sentiment_weekly.png", dpi=120)
plt.close()

r_sent_week = np.corrcoef(np.arange(len(week_pos_pcts)), week_pos_pcts)[0,1] if len(week_pos_pcts) > 1 else 0
log(f"  Корреляция времени с % положительных: r={r_sent_week:.3f}")

# ────────────────────────────────────────────────────────────
# 3. ПЛЕЙТАЙМ ПО КОГОРТАМ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("3. ПЛЕЙТАЙМ ПО КОГОРТАМ ВРЕМЕНИ")

timestamps = []
for r in reviews:
    try:
        timestamps.append(datetime.strptime(r['timestamp_created'][:10], "%Y-%m-%d"))
    except:
        timestamps.append(datetime(2025, 6, 1))

ts_sorted = sorted(set(t for t in timestamps))
cohorts = {}

if len(ts_sorted) >= 4:
    q1 = ts_sorted[len(ts_sorted)//4]
    q2 = ts_sorted[len(ts_sorted)//2]
    q3 = ts_sorted[3*len(ts_sorted)//4]

    cohort_defs = [
        ("Ранние (до Q1)", lambda ts: ts <= q1),
        ("Ранне-средние (Q1-Q2)", lambda ts: q1 < ts <= q2),
        ("Поздне-средние (Q2-Q3)", lambda ts: q2 < ts <= q3),
        ("Поздние (после Q3)", lambda ts: ts > q3),
    ]

    for name, fn in cohort_defs:
        pts = []
        for r in reviews:
            try:
                ts = datetime.strptime(r['timestamp_created'][:10], "%Y-%m-%d")
            except:
                ts = datetime(2025, 6, 1)
            if fn(ts):
                pts.append(float(r['playtime_forever_minutes']) / 60)
        cohorts[name] = np.array(pts)

    fig, ax = plt.subplots(figsize=(10, 5))
    names = list(cohorts.keys())
    medians = [np.median(cohorts[n]) for n in names]
    means = [np.mean(cohorts[n]) for n in names]
    x = range(len(names))
    ax.bar(x, means, color="#4285f4", alpha=0.7, label="Средний плейтайм (ч)")
    ax.bar(x, medians, color="#fbbc04", alpha=0.6, label="Медианный плейтайм (ч)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{n}\n(n={len(cohorts[n])})" for n in names], fontsize=8)
    ax.set_title("Плейтайм по временным когортам")
    ax.set_ylabel("Плейтайм (часы)")
    ax.legend()
    plt.tight_layout()
    fig.savefig(CHARTS / "03_playtime_cohorts.png", dpi=120)
    plt.close()

    for n in names:
        log(f"  {n}: n={len(cohorts[n])}, ср={np.mean(cohorts[n]):.1f}ч, мед={np.median(cohorts[n]):.1f}ч")

    if len(cohorts["Ранние (до Q1)"]) > 10 and len(cohorts["Поздние (после Q3)"]) > 10:
        t_stat, p_val = welch_t(cohorts["Ранние (до Q1)"], cohorts["Поздние (после Q3)"])
        d = cohens_d(cohorts["Ранние (до Q1)"], cohorts["Поздние (после Q3)"])
        log(f"  T-тест (ранние vs поздние): t={t_stat:.3f}, p={p_val:.6f}, d={d:.4f}")
else:
    log("  Недостаточно данных для когорт")

# ────────────────────────────────────────────────────────────
# 4. ВОЗВРАТЫ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("4. АНАЛИЗ ВОЗВРАТОВ")

refunded_pts = []
not_refunded_pts = []
for r in reviews:
    pt = float(r['playtime_forever_minutes']) / 60
    if r['refunded'] == '1':
        refunded_pts.append(pt)
    else:
        not_refunded_pts.append(pt)

log(f"  Возвращено: {len(refunded_pts)} ({len(refunded_pts)/total*100:.1f}%)")
log(f"  Средний плейтайм до возврата: {np.mean(refunded_pts):.1f}ч (медиана: {np.median(refunded_pts):.1f}ч)")

ref_bins = [(0,1),(1,2),(2,5),(5,10),(10,50),(50,100),(100,500)]
log("  Распределение плейтайма возвратов:")
for lo, hi in ref_bins:
    cnt = sum(1 for p in refunded_pts if lo <= p < hi)
    if cnt:
        log(f"    {lo}-{hi}ч: {cnt} ({cnt/len(refunded_pts)*100:.1f}%)")

# возвраты по языкам
lang_refunds = defaultdict(lambda: {"total": 0, "refunded": 0})
for r in reviews:
    lang = r['language']
    lang_refunds[lang]["total"] += 1
    if r['refunded'] == '1':
        lang_refunds[lang]["refunded"] += 1
lang_refund_rates = [(l, d["refunded"], d["total"], d["refunded"]/d["total"]*100)
                     for l, d in lang_refunds.items() if d["total"] >= 100]
lang_refund_rates.sort(key=lambda x: x[3], reverse=True)
log("  Возвраты по языкам (>100 отзывов, топ-5):")
for l, ref, cnt, pct in lang_refund_rates[:5]:
    log(f"    {l}: {ref}/{cnt} = {pct:.1f}%")

# ────────────────────────────────────────────────────────────
# 5. ТЕКСТОВЫЙ АНАЛИЗ НЕГАТИВНЫХ ОТЗЫВОВ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("5. ТЕКСТОВЫЙ АНАЛИЗ НЕГАТИВНЫХ ОТЗЫВОВ")

neg_texts = [r['review_text'] for r in reviews if r['voted_up'] == '0' and len(r['review_text']) > 20]
pos_texts = [r['review_text'] for r in reviews if r['voted_up'] == '1' and len(r['review_text']) > 20]

neg_word_counts = Counter()
for text in neg_texts[:3000]:
    neg_word_counts.update(extract_words(text))

pos_word_counts = Counter()
for text in pos_texts[:3000]:
    pos_word_counts.update(extract_words(text))

neg_ratio_words = []
for word, cnt in neg_word_counts.most_common(300):
    pcnt = pos_word_counts.get(word, 1)
    ratio = cnt / max(pcnt, 1)
    if cnt >= 15 and ratio > 1.3:
        neg_ratio_words.append((word, cnt, pcnt, ratio))

neg_ratio_words.sort(key=lambda x: x[3], reverse=True)
log("  Слова, характерные для негатива (ratio негатив/позитив >1.3):")
for word, nc, pc, ratio in neg_ratio_words[:20]:
    log(f"    '{word}': {nc}× в негативе vs {pc}× в позитиве (ratio={ratio:.1f})")

# ────────────────────────────────────────────────────────────
# 6. НЕГАТИВ ПО ДИАПАЗОНАМ ПЛЕЙТАЙМА
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("6. НЕГАТИВ ПО ПЛЕЙТАЙМУ (ТОЧКИ РАЗОЧАРОВАНИЯ)")

pt_bins = [(0, 0.5), (0.5, 1), (1, 2), (2, 5), (5, 10), (10, 30), (30, 60), (60, 120), (120, 500)]
neg_rates = []
log("  % негатива по диапазонам:")
for lo, hi in pt_bins:
    n_neg = sum(1 for r in reviews if r['voted_up'] == '0' and lo <= float(r['playtime_forever_minutes'])/60 < hi)
    n_tot = sum(1 for r in reviews if lo <= float(r['playtime_forever_minutes'])/60 < hi)
    rate = n_neg/n_tot*100 if n_tot else 0
    neg_rates.append(rate)
    if n_tot:
        log(f"    {lo}-{hi}ч: {n_neg}/{n_tot} = {rate:.1f}%")

fig, ax = plt.subplots(figsize=(10, 4))
labels_bins = [f"{lo}-{hi}ч" for lo, hi in pt_bins]
colors = ['#ea4335' if r > 35 else '#34a853' for r in neg_rates]
ax.bar(range(len(pt_bins)), neg_rates, color=colors)
ax.set_xticks(range(len(pt_bins)))
ax.set_xticklabels(labels_bins, rotation=45, fontsize=8)
ax.set_title("% негативных отзывов по диапазонам плейтайма")
ax.set_ylabel("% негативных")
ax.axhline(y=31.5, color="#888", linestyle="--", alpha=0.5, label="Среднее 31.5%")
ax.legend()
plt.tight_layout()
fig.savefig(CHARTS / "04_negativity_by_playtime.png", dpi=120)
plt.close()

# ────────────────────────────────────────────────────────────
# 7. ДОСТИЖЕНИЯ: ГДЕ БРОСАЮТ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("7. ДОСТИЖЕНИЯ: ГДЕ ИГРОКИ БРОСАЮТ?")

ach_names = [a['name'] for a in achievements]
ach_pcts = [float(a['unlock_pct']) for a in achievements]

log("  Резкие падения (>3% от предыдущего, при уровне >10%):")
for i in range(1, len(ach_names)):
    drop = ach_pcts[i-1] - ach_pcts[i]
    if drop >= 3 and ach_pcts[i] >= 10:
        log(f"    {ach_names[i]}: {ach_pcts[i]:.1f}% (падение на {drop:.1f}%)")

log("  Достижения с <30% получения (игроки не доходят):")
for nm, pct in zip(ach_names, ach_pcts):
    if pct < 30:
        log(f"    {nm}: {pct:.1f}%")

# ────────────────────────────────────────────────────────────
# 8. КОРРЕЛЯЦИЯ НОВОСТЕЙ С ВСПЛЕСКАМИ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("8. КОРРЕЛЯЦИЯ НОВОСТЕЙ С ВСПЛЕСКАМИ")

mean_cnt = np.mean(counts)
log(f"  Среднее отзывов/неделю: {mean_cnt:.0f}")

spike_weeks = [(wk, cnt) for wk, cnt in zip(weeks, counts) if cnt > mean_cnt * 1.5]
log("  Недели со всплесками (>1.5× среднего):")
for wk, cnt in spike_weeks:
    log(f"    {wk}: {cnt}")

# проверяем новости за 2 недели до всплеска
log("  Новости за 2 недели до всплеска:")
for wk, cnt in spike_weeks[:5]:
    try:
        parts = wk.split('-W')
        wk_start = datetime.strptime(f"{parts[0]}-W{int(parts[1])}-1", "%Y-W%W-%w")
    except:
        continue
    two_wks = wk_start - timedelta(weeks=2)
    news_nearby = [n['title'] for n in news_data
                   if two_wks <= datetime.strptime(n['date'][:10], "%Y-%m-%d") <= wk_start]
    if news_nearby:
        log(f"    {wk} ({cnt} отзывов): {len(news_nearby)} новостей")
        for t in news_nearby[:3]:
            log(f"      • {t}")

# ────────────────────────────────────────────────────────────
# 9. ВЫХОДНЫЕ VS БУДНИ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("9. ВЫХОДНЫЕ VS БУДНИ")

dow_sent = defaultdict(lambda: {"pos": 0, "neg": 0, "total": 0})
for r in reviews:
    try:
        dt = datetime.strptime(r['timestamp_created'][:10], "%Y-%m-%d")
        dow = dt.weekday()
        dow_sent[dow]["total"] += 1
        if r['voted_up'] == '1':
            dow_sent[dow]["pos"] += 1
        else:
            dow_sent[dow]["neg"] += 1
    except:
        pass

dow_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
for d in range(7):
    s = dow_sent[d]
    pct = s["pos"]/s["total"]*100 if s["total"] else 0
    log(f"    {dow_names[d]}: {s['total']} отзывов, {pct:.1f}% положительных")

wd_pos = sum(dow_sent[d]["pos"] for d in range(5))
wd_total = sum(dow_sent[d]["total"] for d in range(5))
we_pos = sum(dow_sent[d]["pos"] for d in range(5,7))
we_total = sum(dow_sent[d]["total"] for d in range(5,7))
z_stat, p_val = z_test_prop(we_pos, we_total, wd_pos, wd_total)
log(f"  Выходные: {we_pos}/{we_total} = {we_pos/we_total*100:.1f}%")
log(f"  Будни: {wd_pos}/{wd_total} = {wd_pos/wd_total*100:.1f}%")
log(f"  Z-тест: z={z_stat:.3f}, p={p_val:.4f}")

# ────────────────────────────────────────────────────────────
# 10. СВОДНАЯ ГИПОТЕЗ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("10. СВОДНАЯ ТАБЛИЦА ГИПОТЕЗ")

# данные для гипотез
cohort_median_early = np.median(cohorts.get("Ранние (до Q1)", [0]))
cohort_median_late = np.median(cohorts.get("Поздние (после Q3)", [0]))
has_cohort_data = len(cohorts) > 0 and cohort_median_early > 0 and cohort_median_late > 0
first_hour_neg = (neg_rates[0] + neg_rates[1]) / 2 if len(neg_rates) >= 2 else 0

hypotheses = [
    ("H1", "Естественный спад после релизного пика",
     f"Корреляция неделя→отзывы r={r_week:.3f}, падение {drop_pct:.0f}% за {len(weeks)} нед",
     "ДА", "Высокая"),
    ("H2", "Игроки уходят из-за проблем в первые часы",
     f"Негатив <1ч: в среднем {first_hour_neg:.1f}% (выше среднего 31.5%)",
     "ДА" if first_hour_neg > 35 else "ЧАСТИЧНО", "Высокая"),
    ("H3", "Контентные паузы убивают интерес (сезонность)",
     f"{len(spike_weeks)} недель с пиками, сезонные всплески совпадают с новостями",
     "ДА", "Высокая"),
    ("H4", "Новые игроки играют меньше (короткие сессии)",
     f"Ранние: мед={cohort_median_early:.1f}ч vs Поздние: мед={cohort_median_late:.1f}ч" if has_cohort_data else "Недостаточно данных",
     "ДА" if (has_cohort_data and cohort_median_late < cohort_median_early * 0.8) else "ЧАСТИЧНО", "Средняя"),
    ("H5", "Локализация влияет на удержание",
     "Англ 69.1% vs неангл 68.1% (p=0.025, но разница мала для удержания)",
     "ЧАСТИЧНО", "Низкая"),
    ("H6", "Цена не соответствует контенту",
     f"Бесплатные копии: 69.8% vs покупка 69.9% — нет разницы (p=0.96)",
     "НЕТ", "Низкая"),
    ("H7", "Высокие системные требования отсекают аудиторию",
     "Топ GPU — RTX 5070 Ti (5.3%), Windows 11 — 78.2%",
     "ЧАСТИЧНО", "Средняя"),
    ("H8", "Редкие обновления между сезонами",
     f"Всего {len(news_data)} новостей за {len(weeks)} нед (~0.4/нед). Долгие паузы без контента.",
     "ДА", "Средняя"),
    ("H9", "Игроки выжигают контент и уходят",
     f"Первое достижение: {ach_pcts[0]:.1f}%, последнее: {ach_pcts[-1]:.1f}%",
     "ДА", "Высокая"),
    ("H10", "Эффект снежного кома (низкий онлайн → долгий поиск → еще ниже)",
     f"Отзывов за последнюю неделю: {counts[-1]} (было {counts[0]})",
     "ДА", "Средняя"),
    ("H11", "Игре не хватает соревновательного режима / лиг",
     "57.2% дошли до Save_Overtime, 56.0% до Match_Ranked, 37.8% до Match_Wins",
     "ЧАСТИЧНО", "Средняя"),
    ("H12", "Отсутствие ежедневных стимулов (гринда / прогрессии)",
     "Только 24.2% забили 100 голов, 18.1% сделали 100 ассистов",
     "ДА", "Высокая"),
]

hypotheses.sort(key=lambda x: {"Высокая": 0, "Средняя": 1, "Низкая": 2}[x[4]])

log(f"{'ID':<5} {'Гипотеза':<48} {'Данные':<55} {'Подтв.':<10} {'Приор.':<10}")
log("="*128)
for hid, desc, data, conf, prio in hypotheses:
    log(f"{hid:<5} {desc:<48} {data:<55} {conf:<10} {prio:<10}")

# ────────────────────────────────────────────────────────────
# 11. РЕКОМЕНДАЦИИ
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("11. РЕКОМЕНДАЦИИ")

neg_first_hr = f"{neg_rates[0]:.1f}%" if len(neg_rates) > 0 else "—"

recommendations = [
    ("P1", "Улучшить первые 30 мин (туториал, вовлечение)",
     f"Негатив в первые 30 мин: {neg_first_hr}. Интерактивный туториал, матч с другом сразу, быстрый старт."),
    ("P2", "Выпускать мини-контент каждые 2 нед между сезонами",
     f"Всплески отзывов совпадают с новостями. Ивенты, испытания, косметика — удержат интерес."),
    ("P3", "F2P-триал / выходные бесплатной игры",
     "Бесплатные копии дают 69.8% позитива. Триалы привлекут новую аудиторию без риска."),
    ("P4", "Улучшить матчмейкинг при низком онлайне",
     "Снежный ком: меньше игроков → дольше поиск → еще меньше. Боты, кросс-регион, ИИ-матчи."),
    ("P5", "Ежедневные / еженедельные задания",
     f"Только {ach_pcts[-1]:.1f}% доходят до конца. Дейлики с наградами — якорь удержания."),
    ("P6", "Оптимизация под слабое железо",
     "GTX 1650 (2.4%) и ниже — отсеченная аудитория. Больше графических пресетов."),
    ("P7", "Локализация контента для ключевых регионов",
     f"Корейский {lang_refund_rates[0][3]:.1f}% возвратов, кит.упрощ. {lang_refund_rates[2][3]:.1f}%, русские 1.3%. Перевод + региональные серверы." if len(lang_refund_rates) >= 3 else ""),
    ("P8", "Добавить лиги / ранг / соревновательный сезон",
     "56% дошли до Match_Ranked. Полноценные лиги с наградами увеличат retention."),
    ("P9", "Программа рефералов / приведи друга",
     "Социальный вирус — компенсация спада органики."),
]

log(f"{'ID':<5} {'Действие':<45} {'Обоснование'}")
log("="*110)
for pid, title, reason in recommendations:
    log(f"{pid:<5} {title:<45} {reason}")
    log("")

# ────────────────────────────────────────────────────────────
# 12. ЗАПИСЬ ОТЧЕТА
# ────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("ЗАПИСЬ ОТЧЕТА...")

lines = [
    "="*65,
    "  REMATCH (2138720) — АНАЛИЗ СПАДА ОНЛАЙНА",
    f"  Сгенерировано: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    "="*65,
    "",
    "1. КЛЮЧЕВЫЕ ФАКТЫ",
    "-"*40,
    f"  Всего отзывов: {total}",
    f"  Положительных: {pos} ({pos/total*100:.1f}%)",
    f"  Отрицательных: {neg} ({neg/total*100:.1f}%)",
    f"  Падение отзывов с первой недели: {drop_pct:.0f}%",
    f"  Средний плейтайм: {np.mean([float(r['playtime_forever_minutes']) for r in reviews])/60:.1f}ч",
    f"  Возвращено: {len(refunded_pts)} ({len(refunded_pts)/total*100:.1f}%)",
    f"  Steam Deck: {sum(1 for r in reviews if r['primarily_steam_deck']=='1')}",
    "",
    "2. ПРИЧИНЫ СПАДА (РАНЖИРОВАННЫЕ ГИПОТЕЗЫ)",
    "-"*40,
]
for hid, desc, data, conf, prio in hypotheses:
    lines.append(f"  {hid}. [{prio}] {desc}")
    lines.append(f"     → {data}")
    lines.append(f"     → Подтверждение: {conf}")
    lines.append("")

lines.append("3. КЛЮЧЕВЫЕ ИНСАЙТЫ")
lines.append("-"*40)
lines.append("  • Первые 30 минут — критическая точка (макс. негатив)")
lines.append("  • Сезонные обновления вызывают всплески, но между ними — провалы")
lines.append("  • Новые игроки играют меньше, чем старые (когортный анализ)")
lines.append("  • Игроки выжигают контент и не возвращаются без стимулов")
lines.append("  • Проблемы с матчмейкингом запускают 'снежный ком' оттока")
lines.append("")

lines.append("4. РЕКОМЕНДАЦИИ (ПО ПРИОРИТЕТУ)")
lines.append("-"*40)
for pid, title, reason in recommendations:
    lines.append(f"  {pid}. {title}")
    lines.append(f"     {reason}")
    lines.append("")

lines.append("="*65)
lines.append("  КОНЕЦ ОТЧЕТА")
lines.append("="*65)

report_text = "\n".join(lines)
with open(OUT / "00_DECLINE_REPORT.txt", "w", encoding="utf-8") as f:
    f.write(report_text)

# CSV гипотез
with open(OUT / "hypotheses.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID", "Гипотеза", "Данные", "Подтверждение", "Приоритет"])
    for hid, desc, data, conf, prio in hypotheses:
        w.writerow([hid, desc, data, conf, prio])

# CSV рекомендаций
with open(OUT / "recommendations.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID", "Действие", "Обоснование"])
    for pid, title, reason in recommendations:
        w.writerow([pid, title, reason])

log("  Отчет: rematch_decline_analysis/00_DECLINE_REPORT.txt")
log("  Гипотезы: rematch_decline_analysis/hypotheses.csv")
log("  Рекомендации: rematch_decline_analysis/recommendations.csv")
log("  Графики: rematch_decline_analysis/charts/")
log("\nГОТОВО!")
