# -*- coding: utf-8 -*-
"""Генерация единого мега-дашборда со ВСЕМИ метриками."""

import base64, csv
from datetime import datetime
from pathlib import Path

OUT = Path("rematch_final_dashboard.html")

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ── читаем все данные ─────────────────────────────────────

# 1. Основные метрики
TOTAL, POS, NEG = 49735, 34069, 15666
PCT_POS = round(POS/TOTAL*100, 1)
reviews_lang = read_csv("rematch_analysis/02_reviews_by_language.csv")
gpu = read_csv("rematch_analysis/04_gpu_top20.csv")
os_dist = read_csv("rematch_analysis/06_os_distribution.csv")
achieves = read_csv("rematch_analysis/08_achievements.csv")
weekly = read_csv("rematch_analysis/09_reviews_over_time_weekly.csv")
ab_csv = read_csv("rematch_deep_analysis/ab_test_results.csv")

# 2. Гипотезы и рекомендации (decline)
hyps = read_csv("rematch_decline_analysis/hypotheses.csv")
recs = read_csv("rematch_decline_analysis/recommendations.csv")

# 3. Extra data
features = read_csv("rematch_extra_analysis/feature_sentiment.csv")
bigrams = read_csv("rematch_extra_analysis/neg_bigrams.csv")
segments = read_csv("rematch_extra_analysis/player_segments.csv")
hours_data = read_csv("rematch_extra_analysis/reviews_by_hour.csv")

# ── собираем изображения ─────────────────────────────────
chart_images = {}
# deep analysis (10)
for fname in ["01_playtime_distribution.png", "02_sentiment_by_language.png",
               "03_reviews_over_time.png", "04_gpu_distribution.png",
               "05_playtime_pos_vs_neg.png", "06_achievements.png",
               "07_ram_distribution.png", "08_os_distribution.png",
               "09_helpful_votes.png", "10_reviews_by_dayofweek.png"]:
    p = Path("rematch_deep_analysis/charts") / fname
    if p.exists():
        chart_images[fname] = img_b64(p)
# decline (4)
for fname in ["01_weekly_trend.png", "02_sentiment_weekly.png",
               "03_playtime_cohorts.png", "04_negativity_by_playtime.png"]:
    p = Path("rematch_decline_analysis/charts") / fname
    if p.exists():
        chart_images[f"decline_{fname}"] = img_b64(p)
# extra (5)
for fname in ["01_features_negativity.png", "02_reviews_by_hour.png",
               "03_survival_curve.png", "04_player_segments.png",
               "05_steamcharts_monthly.png"]:
    p = Path("rematch_extra_analysis/charts") / fname
    if p.exists():
        chart_images[f"extra_{fname}"] = img_b64(p)

# ── рендерим таблицы ─────────────────────────────────────
lang_rows = "".join(
    f"<tr><td>{r['language']}</td><td>{r['total']}</td><td>{r['positive']}</td><td>{r['negative']}</td><td>{r['positive_pct']}%</td></tr>"
    for r in reviews_lang if int(r['total']) > 100)
gpu_rows = "".join(
    f"<tr><td>{r['gpu']}</td><td>{r['count']}</td><td>{r['pct']}%</td></tr>" for r in gpu[:10])
os_rows = "".join(
    f"<tr><td>{r['os']}</td><td>{r['count']}</td><td>{r['pct']}%</td></tr>" for r in os_dist[:5])
achieve_rows = "".join(
    f"<tr><td>{r['name']}</td><td>{r['unlock_pct']}%</td></tr>" for r in achieves)
weekly_rows = "".join(
    f"<tr><td>{r['week']}</td><td>{r['review_count']}</td></tr>" for r in weekly[-20:])

# A/B тесты
def fmt_ab(r):
    pv = float(r['p_value'])
    ef = float(r['Effect_Size'])
    interp = r['Interpretation'] if r['Interpretation'] else ""
    # человеческая значимость
    if pv < 0.001:
        verdict = "Достоверно (p<0.001)"
        vclass = "yes"
    elif pv < 0.01:
        verdict = "Достоверно (p<0.01)"
        vclass = "yes"
    elif pv < 0.05:
        verdict = "Достоверно (p<0.05)"
        vclass = "partial"
    else:
        verdict = "Не значимо (разница случайна)"
        vclass = "no"
    es_text = f"d={ef:.3f} ({interp})" if interp else f"r={ef:.3f}"
    va, vb = r['GroupA_Value'], r['GroupB_Value']
    if r['Metric'] == 'Positive rate':
        va, vb = f"{float(va)*100:.1f}%", f"{float(vb)*100:.1f}%"
    elif r['Metric'] in ('Playtime (min)', 'Playtime at review (min)'):
        va, vb = f"{float(va)/60:.1f}ч", f"{float(vb)/60:.1f}ч"
    elif r['Metric'] == 'Language vs Sentiment':
        va = f"Хи-квадрат={float(va):.1f}"; vb = ""
    elif r['Metric'] in ('Playtime vs Vote Score', 'Playtime vs Votes Up', 'Votes Up vs Vote Score', 'Playtime@Review vs Playtime'):
        va = f"r={float(va):.3f}"; vb = ""
        es_text = f"r={ef:.3f}"
    return f"<tr><td><b>{r['TestID']}</b></td><td>{r['Comparison']}</td><td>{va}</td><td>{vb}</td><td class=\"{vclass}\">{verdict}</td><td>{es_text}</td></tr>"
ab_rows = "".join(fmt_ab(r) for r in ab_csv)

# Фичи
feat_rows = "".join(
    f"<tr><td>{f['name_ru']}</td><td>{f['total']}</td><td>{f['neg_count']}</td>"
    f"<td><div class=\"bar-wrap\"><div class=\"bar\" style=\"width:{float(f['neg_pct']):.0f}%\"></div></div></td>"
    f"<td>{f['neg_pct']}%</td></tr>"
    for f in sorted(features, key=lambda x: float(x['neg_pct']), reverse=True) if int(f['total']) >= 50)

# Биграммы
bigram_rows = "".join(
    f"<tr><td><code>{b['bigram']}</code></td><td>{b['neg_count']}</td><td>{b['pos_count']}</td><td>{b['ratio']}x</td></tr>"
    for b in bigrams[:15])

# Сегменты
seg_rows = "".join(
    f"<tr><td>{s['segment']}</td><td>{s['count']}</td>"
    f"<td>{float(s['avg_playtime_h']):.1f}</td><td>{float(s['avg_playtime_at_review_h']):.1f}</td>"
    f"<td>{s['refunds']}</td><td>{s['steam_deck']}</td></tr>"
    for s in segments)

# Часы
hour_rows = "".join(
    f"<tr><td>{int(h['hour']):02d}:00</td><td>{h['count']}</td><td>{h['pos_pct']}%</td></tr>"
    for h in hours_data)

# Гипотезы
hyp_rows = "".join(
    f"<tr><td>{h['ID']}</td><td>{h['Гипотеза']}</td><td>{h['Данные']}</td>"
    f"<td class=\"{'yes' if h['Подтверждение']=='ДА' else 'partial' if h['Подтверждение']=='ЧАСТИЧНО' else 'no'}\">{h['Подтверждение']}</td>"
    f"<td><span class=\"prio-{h['Приоритет'].lower()}\">{h['Приоритет']}</span></td></tr>"
    for h in hyps)

rec_rows = "".join(
    f"<tr><td>{r['ID']}</td><td><b>{r['Действие']}</b></td><td>{r['Обоснование']}</td></tr>"
    for r in recs)

# ── графики ──────────────────────────────────────────────
chart_sections = [
    ("Общее", [
        ("decline_01_weekly_trend.png", "Отзывы по неделям (спад -98%)"),
        ("03_reviews_over_time.png", "Отзывы по времени (детально)"),
        ("decline_02_sentiment_weekly.png", "Тональность по неделям"),
        ("10_reviews_by_dayofweek.png", "Отзывы по дням недели"),
        ("extra_02_reviews_by_hour.png", "Отзывы по часам"),
        ("extra_05_steamcharts_monthly.png", "Средний онлайн по месяцам (SteamCharts)"),
    ]),
    ("Плейтайм и удержание", [
        ("01_playtime_distribution.png", "Распределение плейтайма"),
        ("05_playtime_pos_vs_neg.png", "Плейтайм: положительные vs отрицательные"),
        ("decline_03_playtime_cohorts.png", "Плейтайм по когортам"),
        ("decline_04_negativity_by_playtime.png", "% негатива по диапазонам плейтайма"),
        ("extra_03_survival_curve.png", "Выживаемость (плейтайм до ухода)"),
    ]),
    ("Железо и ОС", [
        ("04_gpu_distribution.png", "GPU (Топ-10)"),
        ("08_os_distribution.png", "ОС"),
        ("07_ram_distribution.png", "RAM"),
    ]),
    ("Тональность и фичи", [
        ("02_sentiment_by_language.png", "Тональность по языкам"),
        ("extra_01_features_negativity.png", "Негатив по фичам"),
        ("extra_04_player_segments.png", "Сегментация игроков"),
        ("09_helpful_votes.png", "Полезные голоса"),
    ]),
    ("Достижения", [
        ("06_achievements.png", "Процент получения достижений"),
    ]),
]

chart_cards_html = ""
for section_label, charts_list in chart_sections:
    sid = section_label.lower().replace(" ","_").replace("(","").replace(")","")
    chart_cards_html += f'<h2 id="{sid}">{section_label}</h2>\n<div class="chart-grid">\n'
    for fname, label in charts_list:
        if fname in chart_images:
            chart_cards_html += f"""
            <div class="chart-card">
                <h3>{label}</h3>
                <img src="data:image/png;base64,{chart_images[fname]}" onclick="openModal(this.src, '{label}')">
            </div>"""
    chart_cards_html += "\n</div>\n"

# ── сборка HTML ──────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>REMATCH — Полная аналитика</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f1419; color:#e1e8ed; padding:20px; }}
  .container {{ max-width:1400px; margin:0 auto; }}
  h1 {{ font-size:28px; margin-bottom:4px; color:#fff; }}
  .subtitle {{ color:#8899aa; font-size:14px; margin-bottom:20px; }}
  h2 {{ font-size:20px; margin:30px 0 14px; color:#8ab4f8; border-bottom:1px solid #2a3340; padding-bottom:6px; }}
  h3 {{ font-size:14px; margin-bottom:8px; }}
  .nav {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:20px; }}
  .nav a {{ color:#8ab4f8; text-decoration:none; font-size:12px; padding:4px 10px; border-radius:4px; background:#1a2330; }}
  .nav a:hover {{ background:#263040; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(155px,1fr)); gap:10px; margin-bottom:24px; }}
  .kpi {{ background:#1a2330; border-radius:10px; padding:14px; text-align:center; }}
  .kpi .v {{ font-size:24px; font-weight:700; }}
  .kpi .v.g {{ color:#34a853; }} .kpi .v.r {{ color:#ea4335; }}
  .kpi .v.b {{ color:#4285f4; }} .kpi .v.o {{ color:#fbbc04; }}
  .kpi .l {{ font-size:10px; color:#8899aa; text-transform:uppercase; margin-top:3px; }}
  .chart-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:14px; }}
  .chart-card {{ background:#1a2330; border-radius:10px; padding:14px; cursor:pointer; transition:transform 0.1s; }}
  .chart-card:hover {{ transform:scale(1.01); }}
  .chart-card img {{ width:100%; height:auto; border-radius:6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; background:#1a2330; border-radius:10px; overflow:hidden; }}
  th,td {{ padding:7px 10px; text-align:left; border-bottom:1px solid #2a3340; }}
  th {{ background:#263040; color:#8ab4f8; font-weight:600; font-size:11px; text-transform:uppercase; }}
  tr:hover {{ background:#1e2a3a; }}
  .scroll {{ max-height:380px; overflow-y:auto; border-radius:10px; margin-bottom:14px; }}
  .scroll::-webkit-scrollbar {{ width:6px; }}
  .scroll::-webkit-scrollbar-thumb {{ background:#3a4a5a; border-radius:3px; }}
  .bar-wrap {{ background:#2a3340; border-radius:4px; height:14px; width:100px; }}
  .bar {{ height:14px; border-radius:4px; background:#ea4335; }}
  code {{ color:#fbbc04; }}
  .yes {{ color:#34a853; font-weight:700; }}
  .no {{ color:#ea4335; font-weight:700; }}
  .partial {{ color:#fbbc04; font-weight:700; }}
  .prio-высокая {{ color:#ea4335; font-weight:700; }}
  .prio-средняя {{ color:#fbbc04; font-weight:700; }}
  .prio-низкая {{ color:#8899aa; }}
  ul.insights {{ list-style:none; padding:0; }}
  ul.insights li {{ padding:10px 14px; margin-bottom:6px; background:#1a2330; border-radius:8px; border-left:3px solid #8ab4f8; font-size:14px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  @media (max-width:800px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
  .modal {{ display:none; position:fixed; z-index:1000; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); align-items:center; justify-content:center; }}
  .modal img {{ max-width:90vw; max-height:90vh; border-radius:10px; }}
  .modal .close {{ position:absolute; top:20px; right:30px; color:#fff; font-size:32px; cursor:pointer; }}
  .footer {{ text-align:center; color:#5a6a7a; font-size:11px; padding:24px 0 8px; }}
</style>
</head>
<body>
<div class="container">
  <h1>REMATCH — Полная аналитика</h1>
  <div class="subtitle">49 735 отзывов · {PCT_POS}% положительных · AppID 2138720 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>

  <div class="nav">
    <a href="#kpi">Метрики</a>
    <a href="#charts">Графики</a>
    <a href="#ab">A/B тесты</a>
    <a href="#lang">Языки</a>
    <a href="#hw">Железо</a>
    <a href="#ach">Достижения</a>
    <a href="#features">Фичи</a>
    <a href="#bigrams">Фразы</a>
    <a href="#segments">Сегменты</a>
    <a href="#hyp">Гипотезы</a>
    <a href="#rec">Рекомендации</a>
    <a href="#insights">Выводы</a>
  </div>

  <h2 id="kpi">Ключевые метрики</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="v">{TOTAL:,}</div><div class="l">Всего отзывов</div></div>
    <div class="kpi"><div class="v g">{POS:,}</div><div class="l">Положительных ({PCT_POS}%)</div></div>
    <div class="kpi"><div class="v r">{NEG:,}</div><div class="l">Отрицательных ({100-PCT_POS}%)</div></div>
    <div class="kpi"><div class="v b">{36932:,}</div><div class="l">Куплено в Steam</div></div>
    <div class="kpi"><div class="v o">{2728:,}</div><div class="l">Бесплатных копий</div></div>
    <div class="kpi"><div class="v r">{410:,}</div><div class="l">Возвращено</div></div>
    <div class="kpi"><div class="v b">227</div><div class="l">Steam Deck</div></div>
    <div class="kpi"><div class="v g">111.2ч</div><div class="l">Средний пл. (пол.)</div></div>
    <div class="kpi"><div class="v r">103.5ч</div><div class="l">Средний пл. (отр.)</div></div>
    <div class="kpi"><div class="v g">54.9ч</div><div class="l">Медианный пл. (пол.)</div></div>
    <div class="kpi"><div class="v r">52.9ч</div><div class="l">Медианный пл. (отр.)</div></div>
    <div class="kpi"><div class="v b">91 374</div><div class="l">Пик онлайна (06/2025)</div></div>
    <div class="kpi"><div class="v r">6 201</div><div class="l">Текущий онлайн (06/2026)</div></div>
    <div class="kpi"><div class="v r">-93%</div><div class="l">Падение онлайна за год</div></div>
    <div class="kpi"><div class="v r">76.9%</div><div class="l">Негатив в первые 30 мин</div></div>
    <div class="kpi"><div class="v o">50%</div><div class="l">Уходят до 10-20ч</div></div>
  </div>

  <h2 id="charts">Графики</h2>
  {chart_cards_html}

  <h2 id="ab">A/B Тесты и корреляции</h2>
  <div class="scroll">
    <table><thead><tr><th>ID</th><th>Что сравнивается</th><th>Группа A</th><th>Группа B</th><th>Разница достоверна?</th><th>Размер эффекта</th></tr></thead>
      <tbody>{ab_rows}</tbody></table>
  </div>

  <div class="grid2">
    <div>
      <h2 id="lang">Тональность по языкам (>100)</h2>
      <div class="scroll"><table><thead><tr><th>Язык</th><th>Всего</th><th>+</th><th>-</th><th>%+</th></tr></thead>
        <tbody>{lang_rows}</tbody></table></div>
    </div>
    <div>
      <h2 id="hw">Топ-10 GPU</h2>
      <div class="scroll"><table><thead><tr><th>GPU</th><th>Кол-во</th><th>%</th></tr></thead>
        <tbody>{gpu_rows}</tbody></table></div>
      <h2 style="margin-top:10px;">Топ-5 ОС</h2>
      <table><thead><tr><th>ОС</th><th>Кол-во</th><th>%</th></tr></thead>
        <tbody>{os_rows}</tbody></table>
    </div>
  </div>

  <div class="grid2">
    <div>
      <h2 id="ach">Процент получения достижений</h2>
      <div class="scroll"><table><thead><tr><th>Достижение</th><th>% получения</th></tr></thead>
        <tbody>{achieve_rows}</tbody></table></div>
    </div>
    <div>
      <h2>Отзывы по неделям (последние 20)</h2>
      <div class="scroll"><table><thead><tr><th>Неделя</th><th>Отзывов</th></tr></thead>
        <tbody>{weekly_rows}</tbody></table></div>
    </div>
  </div>

  <div class="grid2">
    <div>
      <h2 id="features">Фичи в негативных отзывах</h2>
      <div class="scroll"><table><thead><tr><th>Фича</th><th>Всего</th><th>Негатив</th><th></th><th>% нег.</th></tr></thead>
        <tbody>{feat_rows}</tbody></table></div>
    </div>
    <div>
      <h2 id="bigrams">Характерные фразы негатива</h2>
      <div class="scroll"><table><thead><tr><th>Фраза</th><th>Негатив</th><th>Позитив</th><th>Ratio</th></tr></thead>
        <tbody>{bigram_rows}</tbody></table></div>
    </div>
  </div>

  <div class="grid2">
    <div>
      <h2 id="segments">Сегментация игроков</h2>
      <div class="scroll"><table><thead><tr><th>Сегмент</th><th>Кол-во</th><th>Ср.пл.</th><th>Пл.отз.</th><th>Возвр.</th><th>Deck</th></tr></thead>
        <tbody>{seg_rows}</tbody></table></div>
    </div>
    <div>
      <h2>Часовая активность (UTC)</h2>
      <div class="scroll"><table><thead><tr><th>Час</th><th>Отзывов</th><th>% пол.</th></tr></thead>
        <tbody>{hour_rows}</tbody></table></div>
    </div>
  </div>

  <h2 id="hyp">Гипотезы спада (по приоритету)</h2>
  <div class="scroll">
    <table><thead><tr><th>ID</th><th>Гипотеза</th><th>Данные</th><th>Подтв.</th><th>Приор.</th></tr></thead>
      <tbody>{hyp_rows}</tbody></table>
  </div>

  <h2 id="rec">Рекомендации (по приоритету)</h2>
  <div class="scroll">
    <table><thead><tr><th>ID</th><th>Действие</th><th>Обоснование</th></tr></thead>
      <tbody>{rec_rows}</tbody></table>
  </div>

  <h2 id="insights">Ключевые выводы</h2>
  <ul class="insights">
    <li><b>Онлайн упал на 93%</b> за 12 месяцев: с 91 374 до 6 201 среднего онлайна — критическая ситуация</li>
    <li><b>76.9% негатива в первые 30 минут</b> — игра проваливает онбординг, игроки не доходят до интересного контента</li>
    <li><b>50% игроков уходят до 10-20 часов</b> — критическое окно удержания не используется</li>
    <li><b>Читеры (72.7% негатива)</b> — главная токсичная тема. Без античита игра теряет аудиторию</li>
    <li><b>Монетизация (70.5%)</b> и <b>Сервера (66.3%)</b> — вторые по негативу. Adidas-коллабы раздражают</li>
    <li><b>Новички играют меньше</b> (медиана 39.1ч vs 55.7ч у ранних) — retention ухудшается</li>
    <li><b>Контентные паузы убивают интерес</b> — 20 новостей за 55 недель, сезонные всплески быстро затухают</li>
    <li><b>"game breaking bugs", "fix the game", "dead game"</b> — главные фразы негатива. Баги после патчей бесят</li>
    <li><b>Свежие отзывы позитивнее</b> (71.6% vs 68.4%) — игра объективно улучшается, но новые игроки не приходят</li>
    <li><b>Только 4.5% получили все достижения</b> — нет стимулов играть долго</li>
    <li><b>Английские игроки чуть довольнее</b> (69.1% vs 68.1%) — проблемы локализации</li>
    <li><b>Длина отзыва коррелирует с негативом</b>: короткие 82% позитив, длинные — 39%</li>
  </ul>

  <div class="footer">REMATCH (2138720) · Sloclap · Данные Steam API + SteamCharts · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>
</div>

<div id="modal" class="modal" onclick="closeModal()">
  <span class="close">&times;</span>
  <img id="modal-img">
</div>

<script>
function openModal(s,l){{
  document.getElementById('modal-img').src=s;
  document.getElementById('modal').style.display='flex';
  document.title=l+' — REMATCH';
}}
function closeModal(){{
  document.getElementById('modal').style.display='none';
  document.title='REMATCH — Полная аналитика';
}}
document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeModal();}});
</script>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
size = OUT.stat().st_size / 1024
print(f"Готово: {OUT} ({size:.0f} КБ)")
