# -*- coding: utf-8 -*-
"""Генерация HTML-дашборда по анализу спада (на русском)."""

import base64, csv
from datetime import datetime
from pathlib import Path

CHARTS = Path("rematch_decline_analysis/charts")
OUT = Path("rematch_decline_dashboard.html")

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

images = {}
for fname in ["01_weekly_trend.png", "02_sentiment_weekly.png", "03_playtime_cohorts.png", "04_negativity_by_playtime.png"]:
    p = CHARTS / fname
    if p.exists():
        images[fname] = img_b64(p)

with open("rematch_decline_analysis/hypotheses.csv", encoding="utf-8") as f:
    hyps = list(csv.DictReader(f))

with open("rematch_decline_analysis/recommendations.csv", encoding="utf-8") as f:
    recs = list(csv.DictReader(f))

early_neg = list(csv.DictReader(open("rematch_analysis/12_early_negativity.csv", encoding="utf-8")))
def early_metric(key):
    row = next((r for r in early_neg if key in r["metric"]), None)
    if not row:
        return "—", 0
    return f"{float(row['negative_pct']):.1f}%", int(row["review_count"])
NEG_FOREVER_30, N_FOREVER_30 = early_metric("playtime_forever <30")
NEG_AT_REVIEW_30, N_AT_REVIEW_30 = early_metric("playtime_at_review <30")

with open("rematch_decline_analysis/00_DECLINE_REPORT.txt", encoding="utf-8") as f:
    report_text = f.read()

hyp_rows = "".join(
    f"<tr><td>{h['ID']}</td><td>{h['Гипотеза']}</td><td>{h['Данные']}</td>"
    f"<td class=\"{'yes' if h['Подтверждение']=='ДА' else 'partial' if h['Подтверждение']=='ЧАСТИЧНО' else 'no'}\">{h['Подтверждение']}</td>"
    f"<td><span class=\"prio-{h['Приоритет'].lower()}\">{h['Приоритет']}</span></td></tr>"
    for h in hyps
)

rec_rows = "".join(
    f"<tr><td>{r['ID']}</td><td><b>{r['Действие']}</b></td><td>{r['Обоснование']}</td></tr>"
    for r in recs
)

chart_cards = ""
for fname, label in [
    ("01_weekly_trend.png", "Отзывы по неделям (спад онлайн)"),
    ("02_sentiment_weekly.png", "Тональность отзывов по неделям"),
    ("03_playtime_cohorts.png", "Плейтайм по временным когортам"),
    ("04_negativity_by_playtime.png", "% негатива по диапазонам плейтайма"),
]:
    if fname in images:
        chart_cards += f"""
        <div class="chart-card">
            <h3>{label}</h3>
            <img src="data:image/png;base64,{images[fname]}" onclick="openModal(this.src, '{label}')">
        </div>"""

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>REMATCH — Анализ спада онлайна</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f1419; color:#e1e8ed; padding:20px; }}
  .container {{ max-width:1300px; margin:0 auto; }}
  h1 {{ font-size:26px; margin-bottom:4px; color:#fff; }}
  .subtitle {{ color:#8899aa; font-size:14px; margin-bottom:20px; }}
  h2 {{ font-size:18px; margin:28px 0 12px; color:#8ab4f8; border-bottom:1px solid #2a3340; padding-bottom:6px; }}
  .chart-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(400px,1fr)); gap:14px; }}
  .chart-card {{ background:#1a2330; border-radius:10px; padding:14px; cursor:pointer; }}
  .chart-card img {{ width:100%; height:auto; border-radius:6px; }}
  .chart-card h3 {{ font-size:14px; margin-bottom:8px; color:#e1e8ed; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; background:#1a2330; border-radius:10px; overflow:hidden; }}
  th,td {{ padding:8px 12px; text-align:left; border-bottom:1px solid #2a3340; }}
  th {{ background:#263040; color:#8ab4f8; font-weight:600; font-size:11px; text-transform:uppercase; }}
  tr:hover {{ background:#1e2a3a; }}
  .scroll {{ max-height:450px; overflow-y:auto; border-radius:10px; }}
  .scroll::-webkit-scrollbar {{ width:6px; }}
  .scroll::-webkit-scrollbar-thumb {{ background:#3a4a5a; border-radius:3px; }}
  .yes {{ color:#34a853; font-weight:700; }}
  .no {{ color:#ea4335; font-weight:700; }}
  .partial {{ color:#fbbc04; font-weight:700; }}
  .prio-высокая {{ color:#ea4335; font-weight:700; }}
  .prio-средняя {{ color:#fbbc04; font-weight:700; }}
  .prio-низкая {{ color:#8899aa; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; margin:14px 0; }}
  .kpi {{ background:#1a2330; border-radius:8px; padding:12px; text-align:center; }}
  .kpi .value {{ font-size:22px; font-weight:700; }}
  .kpi .value.red {{ color:#ea4335; }}
  .kpi .value.blue {{ color:#4285f4; }}
  .kpi .value.orange {{ color:#fbbc04; }}
  .kpi .label {{ font-size:10px; color:#8899aa; text-transform:uppercase; margin-top:2px; }}
  .rec-table td:first-child {{ color:#8ab4f8; font-weight:700; }}
  .modal {{ display:none; position:fixed; z-index:1000; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); align-items:center; justify-content:center; }}
  .modal img {{ max-width:90vw; max-height:90vh; border-radius:10px; }}
  .modal .close {{ position:absolute; top:20px; right:30px; color:#fff; font-size:32px; cursor:pointer; }}
  .footer {{ text-align:center; color:#5a6a7a; font-size:11px; padding:24px 0 8px; }}
</style>
</head>
<body>
<div class="container">
  <h1>📉 REMATCH — Анализ спада онлайна</h1>
  <div class="subtitle">49 735 отзывов · AppID 2138720 · Сгенерировано {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>

  <h2>Ключевые показатели спада</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="value red">-98%</div><div class="label">Падение отзывов с релиза</div></div>
    <div class="kpi"><div class="value">12 754 → 205</div><div class="label">Отзывов/нед: пик → сейчас</div></div>
    <div class="kpi"><div class="value blue">r=-0.486</div><div class="label">Корреляция времени с отзывами</div></div>
    <div class="kpi"><div class="value blue">r=+0.415</div><div class="label">Корреляция времени с тональностью</div></div>
    <div class="kpi"><div class="value orange">55.7→39.1ч</div><div class="label">Медианный плейтайм (ранние vs поздние)</div></div>
    <div class="kpi"><div class="value red">{NEG_FOREVER_30}</div><div class="label">Негатив при пл. &lt;30 мин (n={N_FOREVER_30})</div></div>
    <div class="kpi"><div class="value orange">{NEG_AT_REVIEW_30}</div><div class="label">Негатив при отзыве &lt;30 мин (n={N_AT_REVIEW_30})</div></div>
  </div>

  <h2>Графики</h2>
  <div class="chart-grid">{chart_cards}</div>

  <h2>Гипотезы спада (ранжированные по приоритету)</h2>
  <div class="scroll">
    <table><thead><tr><th>ID</th><th>Гипотеза</th><th>Данные</th><th>Подтв.</th><th>Приор.</th></tr></thead>
      <tbody>{hyp_rows}</tbody></table>
  </div>

  <h2>Рекомендации (по приоритету)</h2>
  <div class="scroll rec-table">
    <table><thead><tr><th>ID</th><th>Действие</th><th>Обоснование</th></tr></thead>
      <tbody>{rec_rows}</tbody></table>
  </div>

  <div class="footer">REMATCH (AppID 2138720) · Sloclap · Анализ спада онлайна</div>
</div>

<div id="modal" class="modal" onclick="closeModal()">
  <span class="close">&times;</span>
  <img id="modal-img">
</div>

<script>
function openModal(src, label) {{
  document.getElementById('modal-img').src = src;
  document.getElementById('modal').style.display = 'flex';
}}
function closeModal() {{
  document.getElementById('modal').style.display = 'none';
}}
document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeModal(); }});
</script>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
print(f"Готово: {OUT} ({OUT.stat().st_size/1024:.0f} КБ)")
