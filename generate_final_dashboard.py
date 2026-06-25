# -*- coding: utf-8 -*-
"""Финальный HTML-дашборд со всеми новыми анализами."""

import base64, csv
from datetime import datetime
from pathlib import Path

CHARTS_EXTRA = Path("rematch_extra_analysis/charts")
OUT = Path("rematch_final_dashboard.html")

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# Читаем все CSV
with open("rematch_extra_analysis/feature_sentiment.csv", encoding="utf-8") as f:
    features = list(csv.DictReader(f))

with open("rematch_extra_analysis/neg_bigrams.csv", encoding="utf-8") as f:
    bigrams = list(csv.DictReader(f))

with open("rematch_extra_analysis/player_segments.csv", encoding="utf-8") as f:
    segments = list(csv.DictReader(f))

with open("rematch_extra_analysis/reviews_by_hour.csv", encoding="utf-8") as f:
    hours_data = list(csv.DictReader(f))

charts = {}
for fname in ["01_features_negativity.png", "02_reviews_by_hour.png",
               "03_survival_curve.png", "04_player_segments.png",
               "05_steamcharts_monthly.png"]:
    p = CHARTS_EXTRA / fname
    if p.exists():
        charts[fname] = img_b64(p)

feat_rows = "".join(
    f"<tr><td>{f['name_ru']}</td><td>{f['total']}</td><td>{f['neg_count']}</td>"
    f"<td><div class=\"bar-wrap\"><div class=\"bar\" style=\"width:{f['neg_pct']}%\"></div></div></td>"
    f"<td>{f['neg_pct']}%</td></tr>"
    for f in sorted(features, key=lambda x: float(x['neg_pct']), reverse=True)
    if int(f['total']) >= 50
)

bigram_rows = "".join(
    f"<tr><td><code>{b['bigram']}</code></td><td>{b['neg_count']}</td><td>{b['pos_count']}</td><td>{b['ratio']}x</td></tr>"
    for b in bigrams[:15]
)

seg_rows = "".join(
    f"<tr><td>{s['segment']}</td><td>{s['count']}</td>"
    f"<td>{float(s['avg_playtime_h']):.1f}</td><td>{float(s['avg_playtime_at_review_h']):.1f}</td>"
    f"<td>{s['refunds']}</td><td>{s['steam_deck']}</td></tr>"
    for s in segments
)

hour_rows = "".join(
    f"<tr><td>{int(h['hour']):02d}:00</td><td>{h['count']}</td><td>{h['pos_pct']}%</td></tr>"
    for h in hours_data[:8]
)

chart_cards = ""
for fname, label in [
    ("01_features_negativity.png", "Процент негатива по упоминаемым фичам"),
    ("02_reviews_by_hour.png", "Отзывы по часам (количество и тональность)"),
    ("03_survival_curve.png", "Выживаемость: на каком плейтайме уходят"),
    ("04_player_segments.png", "Сегментация игроков"),
    ("05_steamcharts_monthly.png", "Средний онлайн по месяцам (93% падение за год)"),
]:
    if fname in charts:
        chart_cards += f"""
        <div class="chart-card">
            <h3>{label}</h3>
            <img src="data:image/png;base64,{charts[fname]}" onclick="openModal(this.src, '{label}')">
        </div>"""

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>REMATCH — Финальный дашборд</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f1419; color:#e1e8ed; padding:20px; }}
  .container {{ max-width:1350px; margin:0 auto; }}
  h1 {{ font-size:26px; margin-bottom:4px; color:#fff; }}
  .subtitle {{ color:#8899aa; font-size:13px; margin-bottom:20px; }}
  h2 {{ font-size:18px; margin:28px 0 12px; color:#8ab4f8; border-bottom:1px solid #2a3340; padding-bottom:6px; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:10px; margin-bottom:20px; }}
  .kpi {{ background:#1a2330; border-radius:10px; padding:14px; text-align:center; }}
  .kpi .value {{ font-size:24px; font-weight:700; }}
  .kpi .value.red {{ color:#ea4335; }}
  .kpi .value.green {{ color:#34a853; }}
  .kpi .value.blue {{ color:#4285f4; }}
  .kpi .value.orange {{ color:#fbbc04; }}
  .kpi .label {{ font-size:10px; color:#8899aa; text-transform:uppercase; margin-top:3px; }}
  .chart-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:14px; }}
  .chart-card {{ background:#1a2330; border-radius:10px; padding:14px; cursor:pointer; transition:transform 0.1s; }}
  .chart-card:hover {{ transform:scale(1.01); }}
  .chart-card img {{ width:100%; height:auto; border-radius:6px; }}
  .chart-card h3 {{ font-size:14px; margin-bottom:8px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; background:#1a2330; border-radius:10px; overflow:hidden; }}
  th,td {{ padding:7px 10px; text-align:left; border-bottom:1px solid #2a3340; }}
  th {{ background:#263040; color:#8ab4f8; font-weight:600; font-size:11px; text-transform:uppercase; }}
  tr:hover {{ background:#1e2a3a; }}
  .scroll {{ max-height:400px; overflow-y:auto; border-radius:10px; margin-bottom:14px; }}
  .scroll::-webkit-scrollbar {{ width:6px; }}
  .scroll::-webkit-scrollbar-thumb {{ background:#3a4a5a; border-radius:3px; }}
  .bar-wrap {{ background:#2a3340; border-radius:4px; height:14px; width:100px; }}
  .bar {{ height:14px; border-radius:4px; background:#ea4335; }}
  code {{ color:#fbbc04; }}
  .modal {{ display:none; position:fixed; z-index:1000; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); align-items:center; justify-content:center; }}
  .modal img {{ max-width:90vw; max-height:90vh; border-radius:10px; }}
  .modal .close {{ position:absolute; top:20px; right:30px; color:#fff; font-size:32px; cursor:pointer; }}
  .footer {{ text-align:center; color:#5a6a7a; font-size:11px; padding:24px 0 8px; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  @media (max-width:800px) {{ .grid-2 {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>REMATCH — Финальный анализ</h1>
  <div class="subtitle">49 735 отзывов · Steam Charts данные · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>

  <h2>Ключевые метрики</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="value green">68.5%</div><div class="label">Положительных отзывов</div></div>
    <div class="kpi"><div class="value red">76.9%</div><div class="label">Негатив в первые 30 мин</div></div>
    <div class="kpi"><div class="value blue">91 374</div><div class="label">Пик онлайна (июнь 2025)</div></div>
    <div class="kpi"><div class="value red">6 201</div><div class="label">Текущий онлайн (июнь 2026)</div></div>
    <div class="kpi"><div class="value red">-93%</div><div class="label">Падение онлайна за 12 мес</div></div>
    <div class="kpi"><div class="value orange">50%</div><div class="label">Уходят до 10-20ч плейтайма</div></div>
  </div>

  <h2>Графики</h2>
  <div class="chart-grid">{chart_cards}</div>

  <div class="grid-2">
    <div>
      <h2>Фичи в негативных отзывах</h2>
      <div class="scroll">
        <table><thead><tr><th>Фича</th><th>Всего</th><th>Негатив</th><th>% нег.</th><th></th></tr></thead>
          <tbody>{feat_rows}</tbody></table>
      </div>
    </div>
    <div>
      <h2>Биграммы из негативных отзывов</h2>
      <div class="scroll">
        <table><thead><tr><th>Фраза</th><th>Негатив</th><th>Позитив</th><th>Ratio</th></tr></thead>
          <tbody>{bigram_rows}</tbody></table>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div>
      <h2>Сегментация игроков</h2>
      <div class="scroll">
        <table><thead><tr><th>Сегмент</th><th>Кол-во</th><th>Ср. пл.</th><th>Пл. отзыва</th><th>Возвр.</th><th>Deck</th></tr></thead>
          <tbody>{seg_rows}</tbody></table>
      </div>
    </div>
    <div>
      <h2>Часовая активность (UTC)</h2>
      <div class="scroll">
        <table><thead><tr><th>Час</th><th>Отзывов</th><th>% пол.</th></tr></thead>
          <tbody>{hour_rows}</tbody></table>
      </div>
    </div>
  </div>

  <h2>Ключевые выводы</h2>
  <ul style="list-style:none;padding:0;">
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>Читеры (72.7% негатива)</b> — самая токсичная тема. Античит срочно нужен.
    </li>
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>Монетизация (70.5%)</b> и <b>Сервера (66.3%)</b> — вторые по негативу
    </li>
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>Онлайн упал на 93%</b> за 12 месяцев: с 91 374 до 6 201 среднего онлайна
    </li>
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>50% игроков уходят до 10-20 часов</b> — критическое окно удержания
    </li>
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>Новички играют меньше</b> (медиана 39.1ч vs 55.7ч у ранних) — ухудшение retention
    </li>
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>Длина отзыва коррелирует с негативом</b>: короткие — 82% позитив, длинные — 39%
    </li>
    <li style="padding:10px 14px;margin-bottom:6px;background:#1a2330;border-radius:8px;border-left:3px solid #8ab4f8;font-size:14px;">
      <b>game breaking bugs, fix the game, dont buy</b> — главные фразы в негативе
    </li>
  </ul>

  <div class="footer">REMATCH (2138720) · Sloclap · Данные Steam + SteamCharts</div>
</div>

<div id="modal" class="modal" onclick="closeModal()">
  <span class="close">&times;</span>
  <img id="modal-img">
</div>

<script>
function openModal(src,label) {{
  document.getElementById('modal-img').src=src;
  document.getElementById('modal').style.display='flex';
}}
function closeModal() {{
  document.getElementById('modal').style.display='none';
}}
document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeModal();}});
</script>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
print(f"Готово: {OUT} ({OUT.stat().st_size/1024:.0f} КБ)")
