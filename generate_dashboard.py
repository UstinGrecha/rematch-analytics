import base64, csv, json, os, textwrap
from pathlib import Path

CHART_DIR = Path("rematch_deep_analysis/charts")
OUTPUT = Path("rematch_dashboard.html")

CHARTS = [
    ("01_playtime_distribution.png", "Распределение плейтайма"),
    ("02_sentiment_by_language.png", "Тональность по языкам"),
    ("03_reviews_over_time.png", "Отзывы по времени"),
    ("04_gpu_distribution.png", "GPU (Топ-10)"),
    ("05_playtime_pos_vs_neg.png", "Плейтайм: положительные vs отрицательные"),
    ("06_achievements.png", "Процент получения достижений"),
    ("07_ram_distribution.png", "Распределение RAM"),
    ("08_os_distribution.png", "Распределение ОС"),
    ("09_helpful_votes.png", "Распределение полезных голосов"),
    ("10_reviews_by_dayofweek.png", "Отзывы по дням недели"),
]

def img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


images = {}
for fname, _ in CHARTS:
    p = CHART_DIR / fname
    if p.exists():
        images[fname] = img_b64(p)

reviews_lang = read_csv("rematch_analysis/02_reviews_by_language.csv")
gpu = read_csv("rematch_analysis/04_gpu_top20.csv")
os_dist = read_csv("rematch_analysis/06_os_distribution.csv")
achieves = read_csv("rematch_analysis/08_achievements.csv")
weekly = read_csv("rematch_analysis/09_reviews_over_time_weekly.csv")
ab_csv = read_csv("rematch_deep_analysis/ab_test_results.csv")

POS = 34069
NEG = 15666
TOTAL = 49735
PCT_POS = round(POS / TOTAL * 100, 1)
AVG_POS = 111.2
AVG_NEG = 103.5
MED_POS = 54.9
MED_NEG = 52.9
STEAM_PURCH = 36932
FREE = 2728
REFUNDED = 410
STEAM_DECK = 227

lang_rows = "".join(
    f"<tr><td>{r['language']}</td><td>{r['total']}</td><td>{r['positive']}</td><td>{r['negative']}</td><td>{r['positive_pct']}%</td></tr>"
    for r in reviews_lang if int(r['total']) > 100
)
gpu_rows = "".join(
    f"<tr><td>{r['gpu']}</td><td>{r['count']}</td><td>{r['pct']}%</td></tr>"
    for r in gpu[:10]
)
os_rows = "".join(
    f"<tr><td>{r['os']}</td><td>{r['count']}</td><td>{r['pct']}%</td></tr>"
    for r in os_dist[:5]
)
achieve_rows = "".join(
    f"<tr><td>{r['name']}</td><td>{r['unlock_pct']}%</td></tr>"
    for r in achieves
)
weekly_rows = "".join(
    f"<tr><td>{r['week']}</td><td>{r['review_count']}</td></tr>"
    for r in weekly[-20:]
)

def fmt_ab_row(r):
    pv = r['p_value']
    if pv == "0.0":
        star = "*** p<0.001"
    elif pv.startswith("0."):
        pvf = float(pv)
        if pvf < 0.001:
            star = "*** p<0.001"
        elif pvf < 0.01:
            star = "** p<0.01"
        elif pvf < 0.05:
            star = "* p<0.05"
        else:
            star = "не значимо"
    else:
        star = "не значимо"
    val_a = r['GroupA_Value']
    val_b = r['GroupB_Value']
    if r['Metric'] == 'Positive rate':
        val_a = f"{float(val_a)*100:.1f}%"
        val_b = f"{float(val_b)*100:.1f}%"
    elif r['Metric'] in ('Playtime (min)', 'Playtime at review (min)'):
        val_a = f"{float(val_a)/60:.1f}h"
        val_b = f"{float(val_b)/60:.1f}h"
    elif r['Metric'] == 'Language vs Sentiment':
        val_a = f"χ²={float(val_a):.1f}"
        val_b = ""
    elif r['Metric'] in ('Playtime vs Vote Score', 'Playtime vs Votes Up', 'Votes Up vs Vote Score', 'Playtime@Review vs Playtime'):
        val_a = f"r={float(val_a):.3f}"
        val_b = ""
    return f"<tr><td><b>{r['TestID']}</b></td><td>{r['Comparison']}</td><td>{val_a}</td><td>{val_b}</td><td>{star}</td></tr>"

ab_rows = "".join(fmt_ab_row(r) for r in ab_csv)

insights_html = """
<li>Положительные отзывы имеют <b>значительно выше плейтайм</b> (111.2ч vs 103.5ч) — игра становится лучше со временем</li>
<li>Англоязычные отзывы чуть позитивнее (69.1% vs 68.1%) — возможны проблемы локализации</li>
<li>Игроки на <b>Steam Deck</b> довольны больше (69.6% vs 68.5%) — оптимизация хорошая</li>
<li><b>Свежие отзывы</b> позитивнее (71.6% vs 68.4%) — игра улучшается с обновлениями</li>
<li>27.6% отзывов написаны в выходные — 13 726 из 49 735</li>
<li>5 достижений открыты у >80% игроков, 1 — у <10%</li>
<li>Только <b>4.5%</b> игроков получили все достижения — типично для live-service игр</li>
<li>Самый популярный GPU: <b>NVIDIA GeForce RTX 5070 Ti</b> (5.3%)</li>
"""

chart_cards = ""
for fname, label in CHARTS:
    if fname in images:
        chart_cards += f"""
        <div class="chart-card">
            <h3>{label}</h3>
            <img src="data:image/png;base64,{images[fname]}" alt="{label}" onclick="openModal(this.src, '{label}')">
        </div>"""

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>REMATCH — Steam Аналитика</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1419; color: #e1e8ed; padding: 20px; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; color: #fff; }}
  h2 {{ font-size: 20px; margin: 30px 0 16px; color: #8ab4f8; border-bottom: 1px solid #2a3340; padding-bottom: 8px; }}
  h3 {{ font-size: 15px; margin-bottom: 10px; color: #e1e8ed; }}
  .subtitle {{ color: #8899aa; font-size: 14px; margin-bottom: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 30px; }}
  .kpi {{ background: #1a2330; border-radius: 10px; padding: 16px; text-align: center; }}
  .kpi .value {{ font-size: 26px; font-weight: 700; color: #fff; }}
  .kpi .value.green {{ color: #34a853; }}
  .kpi .value.red {{ color: #ea4335; }}
  .kpi .value.blue {{ color: #4285f4; }}
  .kpi .value.orange {{ color: #fbbc04; }}
  .kpi .label {{ font-size: 11px; color: #8899aa; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }}
  .chart-card {{ background: #1a2330; border-radius: 10px; padding: 16px; cursor: pointer; transition: transform 0.15s; }}
  .chart-card:hover {{ transform: scale(1.01); }}
  .chart-card img {{ width: 100%; height: auto; border-radius: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #1a2330; border-radius: 10px; overflow: hidden; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #2a3340; }}
  th {{ background: #263040; color: #8ab4f8; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px; }}
  tr:hover {{ background: #1e2a3a; }}
  .scroll {{ max-height: 400px; overflow-y: auto; border-radius: 10px; }}
  .scroll::-webkit-scrollbar {{ width: 6px; }}
  .scroll::-webkit-scrollbar-thumb {{ background: #3a4a5a; border-radius: 3px; }}
  ul.insights {{ list-style: none; padding: 0; }}
  ul.insights li {{ padding: 10px 14px; margin-bottom: 6px; background: #1a2330; border-radius: 8px; border-left: 3px solid #8ab4f8; font-size: 14px; }}
  .modal {{ display: none; position: fixed; z-index: 1000; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; }}
  .modal img {{ max-width: 90vw; max-height: 90vh; border-radius: 10px; }}
  .modal .close {{ position: absolute; top: 20px; right: 30px; color: #fff; font-size: 32px; cursor: pointer; }}
  .ab-table td:first-child {{ font-weight: 700; color: #8ab4f8; }}
  .footer {{ text-align: center; color: #5a6a7a; font-size: 12px; padding: 30px 0 10px; }}
}}</style>
</head>
<body>
<div class="container">
  <h1>⚽ REMATCH — Аналитика Steam</h1>
  <div class="subtitle">49 735 отзывов · AppID 2138720 · Сгенерировано 2026-06-24</div>

  <h2>Ключевые метрики</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="value">{TOTAL:,}</div><div class="label">Всего отзывов</div></div>
    <div class="kpi"><div class="value green">{POS:,}</div><div class="label">Положительных ({PCT_POS}%)</div></div>
    <div class="kpi"><div class="value red">{NEG:,}</div><div class="label">Отрицательных ({100-PCT_POS}%)</div></div>
    <div class="kpi"><div class="value blue">{STEAM_PURCH:,}</div><div class="label">Куплено в Steam</div></div>
    <div class="kpi"><div class="value orange">{FREE:,}</div><div class="label">Бесплатных копий</div></div>
    <div class="kpi"><div class="value red">{REFUNDED:,}</div><div class="label">Возвращено</div></div>
    <div class="kpi"><div class="value blue">{STEAM_DECK:,}</div><div class="label">Steam Deck</div></div>
    <div class="kpi"><div class="value green">{AVG_POS}ч</div><div class="label">Средний плейтайм (пол.)</div></div>
    <div class="kpi"><div class="value red">{AVG_NEG}ч</div><div class="label">Средний плейтайм (отр.)</div></div>
    <div class="kpi"><div class="value green">{MED_POS}ч</div><div class="label">Медианный плейтайм (пол.)</div></div>
    <div class="kpi"><div class="value red">{MED_NEG}ч</div><div class="label">Медианный плейтайм (отр.)</div></div>
  </div>

  <h2>Графики</h2>
  <div class="chart-grid">{chart_cards}</div>

  <h2>Ключевые выводы</h2>
  <ul class="insights">{insights_html}</ul>

  <h2>A/B Тесты</h2>
  <div class="scroll">
    <table class="ab-table">
      <thead><tr>            <th>ID</th><th>Сравнение</th><th>Группа A</th><th>Группа B</th><th>Стат. значимость</th></tr></thead>
      <tbody>{ab_rows}</tbody>
    </table>
  </div>

  <h2>Тональность по языкам (>100 отзывов)</h2>
  <div class="scroll">
    <table><thead><tr><th>Язык</th><th>Всего</th><th>Положительных</th><th>Отрицательных</th><th>% пол.</th></tr></thead>
      <tbody>{lang_rows}</tbody></table>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px;">
    <div>
      <h2>Топ-10 GPU</h2>
      <div class="scroll"><table><thead><tr><th>GPU</th><th>Кол-во</th><th>%</th></tr></thead>
        <tbody>{gpu_rows}</tbody></table></div>
    </div>
    <div>
      <h2>Топ-5 OS</h2>
      <div class="scroll"><table><thead><tr><th>ОС</th><th>Кол-во</th><th>%</th></tr></thead>
        <tbody>{os_rows}</tbody></table></div>
    </div>
  </div>

  <h2>Процент получения достижений</h2>
  <div class="scroll">
    <table><thead><tr><th>Достижение</th><th>% получения</th></tr></thead>
      <tbody>{achieve_rows}</tbody></table>
  </div>

  <h2>Отзывы по неделям (последние 20)</h2>
  <div class="scroll">
    <table><thead><tr><th>Неделя</th><th>Отзывов</th></tr></thead>
      <tbody>{weekly_rows}</tbody></table>
  </div>

  <div class="footer">REMATCH (AppID 2138720) · Sloclap · Данные Steam API</div>
</div>

<div id="modal" class="modal" onclick="closeModal()">
  <span class="close">&times;</span>
  <img id="modal-img" src="">
</div>

<script>
function openModal(src, label) {{
  document.getElementById('modal-img').src = src;
  document.getElementById('modal').style.display = 'flex';
  document.title = label + ' — REMATCH Dashboard';
}}
function closeModal() {{
  document.getElementById('modal').style.display = 'none';
  document.title = 'REMATCH — Steam Analytics Dashboard';
}}
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') closeModal();
}});
</script>
</body>
</html>"""

OUTPUT.write_text(html, encoding="utf-8")
print(f"Dashboard written: {OUTPUT} ({os.path.getsize(OUTPUT)/1024/1024:.1f} MB)")
