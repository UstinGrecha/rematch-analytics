"""SteamCharts player count chart."""
import urllib.request, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

plt.rcParams.update({"font.size": 10, "axes.facecolor": "#1a2330",
    "figure.facecolor": "#0f1419", "text.color": "#e1e8ed",
    "axes.labelcolor": "#e1e8ed", "axes.edgecolor": "#2a3340",
    "xtick.color": "#8899aa", "ytick.color": "#8899aa",
    "legend.facecolor": "#1a2330", "legend.edgecolor": "#2a3340",
    "axes.titlecolor": "#8ab4f8"})

url = "https://steamcharts.com/app/2138720/chart-data.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode())

dates = [datetime.fromtimestamp(p[0]/1000) for p in data]
values = [p[1] for p in data]

fig, ax = plt.subplots(figsize=(14, 5))
ax.fill_between(dates, values, alpha=0.2, color="#4285f4")
ax.plot(dates, values, color="#4285f4", linewidth=2, marker="o", markersize=4)
ax.set_title("REMATCH - Average Monthly Players (SteamCharts)")
ax.set_ylabel("Average Players")
ax.set_xlabel("Month")
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
plt.xticks(rotation=45)
plt.tight_layout()
fig.savefig("rematch_extra_analysis/charts/05_steamcharts_monthly.png", dpi=120)
plt.close()

peak = max(values)
peak_date = dates[values.index(peak)].strftime("%Y-%m")
current = values[-1]
current_date = dates[-1].strftime("%Y-%m")
drop_pct = (1 - current/peak) * 100
print(f"Saved. Points: {len(dates)}, Peak: {peak} ({peak_date}), Current: {current} ({current_date}), Drop: {drop_pct:.0f}%")
