"""Dashboard generator for Weather Edge ensemble system."""
import os
from datetime import datetime, timezone

OUTPUT_DIR     = "output"
DASHBOARD_PATH = os.path.join(OUTPUT_DIR, "dashboard.html")

# ── CSS ────────────────────────────────────────────────────────────────────────
_CSS = """
:root {
  --bg: #080d1a; --surface: #0f1729; --surface2: #162035; --surface3: #1a2840;
  --border: #1d2d45; --text: #dde4f0; --muted: #5c7399; --muted2: #3d5070;
  --bet: #22c55e; --bet-dim: #052e16; --bet-border: #15803d;
  --fade: #ef4444; --fade-dim: #1e0707; --fade-border: #b91c1c;
  --skip: #475569; --skip-dim: #0f172a; --skip-border: #1e293b;
  --accent: #3b82f6; --accent-dim: #1e3a5f; --accent2: #6366f1;
  --gold: #f59e0b; --gold-dim: #2d1b00;
  --poly: #6366f1; --kal: #0ea5e9;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
  line-height: 1.5; font-size: 15px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.header {
  background: linear-gradient(135deg, #0b1120 0%, #13103a 100%);
  border-bottom: 1px solid var(--border);
  padding: 20px 36px;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
}
.logo { font-size: 1.4rem; font-weight: 800; letter-spacing: -0.03em; }
.logo em { color: var(--accent); font-style: normal; }
.logo-sub { font-size: 0.72rem; color: var(--muted); margin-top: 3px; letter-spacing: 0.04em; }
.header-right { color: var(--muted); font-size: 0.78rem; text-align: right; line-height: 1.9; }

.container { max-width: 1480px; margin: 0 auto; padding: 24px 36px; }

/* ── Backtest stats ──────────────────────────────────────────────────────── */
.backtest-bar {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--gold);
  border-radius: 12px;
  padding: 16px 24px;
  margin-bottom: 28px;
  display: flex; align-items: center; gap: 0;
}
.bt-label {
  font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--gold); white-space: nowrap; margin-right: 24px; flex-shrink: 0;
}
.bt-stats { display: flex; flex-wrap: wrap; gap: 0; flex: 1; }
.bt-stat {
  flex: 1; min-width: 110px; padding: 0 20px;
  border-right: 1px solid var(--border);
}
.bt-stat:last-child { border-right: none; }
.bt-stat .bv { font-size: 1.5rem; font-weight: 800; line-height: 1.1; }
.bt-stat .bl { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 3px; }
.bt-stat.win  .bv { color: var(--bet); }
.bt-stat.loss .bv { color: var(--fade); }
.bt-stat.pnl-pos .bv { color: var(--bet); }
.bt-stat.pnl-neg .bv { color: var(--fade); }
.bt-stat.neutral .bv { color: var(--accent); }
.bt-stat.brier   .bv { color: var(--gold); }

/* ── Section header ─────────────────────────────────────────────────────── */
.section-hdr {
  font-size: 0.7rem; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.12em;
  margin-bottom: 14px;
  display: flex; align-items: center; gap: 12px;
}
.section-hdr::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.section-hdr span { background: var(--surface2); padding: 2px 8px; border-radius: 4px; font-size: 0.68rem; }

/* ── Signal cards ───────────────────────────────────────────────────────── */
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(480px,1fr)); gap: 16px; margin-bottom: 48px; }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid transparent;
  border-radius: 14px;
  overflow: hidden;
  display: flex; flex-direction: column;
  transition: transform 0.12s, box-shadow 0.12s;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.3); }
.card.bet  { border-left-color: var(--bet);  }
.card.fade { border-left-color: var(--fade); }

.card-head {
  background: var(--surface2);
  padding: 14px 18px;
  display: flex; align-items: flex-start; gap: 12px;
}
.badge {
  display: inline-flex; align-items: center; padding: 4px 10px;
  border-radius: 6px; font-size: 0.68rem; font-weight: 800; letter-spacing: 0.1em;
  flex-shrink: 0;
}
.badge.bet  { background: var(--bet-dim);  color: var(--bet);  border: 1px solid var(--bet-border); }
.badge.fade { background: var(--fade-dim); color: var(--fade); border: 1px solid var(--fade-border); }

.head-info { flex: 1; }
.edge-big { font-size: 1.6rem; font-weight: 800; line-height: 1; }
.bet  .edge-big { color: var(--bet); }
.fade .edge-big { color: var(--fade); }
.question-line { font-size: 0.88rem; font-weight: 500; margin-top: 6px; line-height: 1.4; }
.meta-line { font-size: 0.72rem; color: var(--muted); margin-top: 4px; }

.card-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }

/* ── Model grid ──────────────────────────────────────────────────────────── */
.model-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.model-table th {
  text-align: left; color: var(--muted); font-size: 0.65rem;
  text-transform: uppercase; letter-spacing: 0.08em;
  padding: 5px 8px; border-bottom: 1px solid var(--border);
}
.model-table td { padding: 6px 8px; vertical-align: middle; }
.model-table tr.ensemble-row td { border-top: 1px solid var(--border); font-weight: 700; }
.model-name { font-weight: 600; color: var(--text); white-space: nowrap; }
.model-members { color: var(--muted); font-size: 0.72rem; }
.model-avg { color: var(--text); font-variant-numeric: tabular-nums; }
.model-bias { color: var(--muted); font-size: 0.7rem; }

.bar-cell { width: 100px; padding: 6px 8px; }
.bar-wrap { background: var(--surface3); border-radius: 3px; height: 6px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.bar-fill.high { background: var(--bet); }
.bar-fill.mid  { background: var(--gold); }
.bar-fill.low  { background: var(--fade); }

.vote-pct { font-weight: 700; font-variant-numeric: tabular-nums; width: 40px; text-align: right; }
.bet  .vote-pct { color: var(--bet); }
.fade .vote-pct { color: var(--fade); }
.vote-count { color: var(--muted); font-size: 0.7rem; }

/* ── Platform comparison ─────────────────────────────────────────────────── */
.platform-row {
  background: var(--surface3);
  border-radius: 10px;
  padding: 12px 14px;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  align-items: center;
}
.plat { display: flex; flex-direction: column; gap: 2px; }
.plat-name { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }
.plat-name.poly { color: var(--poly); }
.plat-name.kal  { color: var(--kal); }
.plat-name.ours { color: var(--muted); }
.plat-price { font-size: 1.2rem; font-weight: 800; }
.plat-price.poly { color: var(--poly); }
.plat-price.kal  { color: var(--kal); }
.plat-price.ours { color: var(--accent); }
.plat-sub { font-size: 0.68rem; color: var(--muted); }
.plat-sub.best { color: var(--bet); font-weight: 600; }
.plat-sub.fade-note { color: var(--fade); font-weight: 600; }

/* ── Empty state ─────────────────────────────────────────────────────────── */
.empty-msg {
  background: var(--surface);
  border: 1px dashed var(--border); border-radius: 12px;
  padding: 40px; text-align: center; color: var(--muted); font-size: 0.9rem;
}

/* ── History table ───────────────────────────────────────────────────────── */
.tbl-wrap { overflow-x: auto; margin-bottom: 48px; }
table { width: 100%; border-collapse: collapse; font-size: 0.81rem; }
th {
  text-align: left; color: var(--muted);
  font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.08em;
  padding: 9px 12px; border-bottom: 1px solid var(--border); white-space: nowrap;
}
td { padding: 9px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:hover td { background: var(--surface2); }
.ts { color: var(--muted); white-space: nowrap; font-size: 0.73rem; }
.qs { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.edge-td { font-weight: 700; }
.bsm { display: inline-block; padding: 2px 7px; border-radius: 5px;
  font-size: 0.63rem; font-weight: 800; letter-spacing: 0.08em; }
.bsm.bet  { background: var(--bet-dim);  color: var(--bet); }
.bsm.fade { background: var(--fade-dim); color: var(--fade); }
.bsm.skip { background: var(--skip-dim); color: var(--skip); }
.empty-td { text-align: center; color: var(--muted); padding: 32px; }
.plat-tag { font-size: 0.68rem; padding: 2px 6px; border-radius: 4px; }
.plat-tag.poly { background: rgba(99,102,241,.15); color: var(--poly); }
.plat-tag.kal  { background: rgba(14,165,233,.15);  color: var(--kal);  }
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sc(s: str) -> str:
    return {"BET": "bet", "FADE": "fade", "SKIP": "skip"}.get(s, "skip")


def _bar_class(pct: float) -> str:
    if pct >= 0.6:  return "high"
    if pct >= 0.4:  return "mid"
    return "low"


def _fmt_price(price) -> str:
    if price is None:
        return "—"
    return f"{price * 100:.1f}%"


def _metric_label(metric: str, threshold, comparison: str) -> str:
    labels = {
        "temperature_2m": f"temp {'>' if comparison == 'above' else '<'} {threshold}°C",
        "precipitation":  f"precip {'>' if comparison == 'above' else '<'} {threshold}mm",
        "windspeed_10m":  f"wind {'>' if comparison == 'above' else '<'} {threshold}km/h",
    }
    return labels.get(metric, f"{metric} {comparison} {threshold}")


def _model_rows(by_model: dict, total_votes: int) -> str:
    if not by_model:
        return '<tr><td colspan="6" style="color:var(--muted);padding:8px">No model data</td></tr>'

    rows = []
    MODEL_ORDER = ["ECMWF", "GFS", "NAM", "UKMET"]
    for model in MODEL_ORDER:
        info = by_model.get(model)
        if not info:
            continue
        pct     = info["probability"]
        bar_cls = _bar_class(pct)
        avg     = f"{info['avg_forecast']}" if info.get("avg_forecast") is not None else "—"
        bias    = f"{info['bias_applied']:+.2f}" if info.get("bias_applied") else "0"
        rows.append(f"""
<tr>
  <td class="model-name">{model}</td>
  <td class="model-members">{info['total']}</td>
  <td class="model-avg">{avg}</td>
  <td class="model-bias">{bias}</td>
  <td class="bar-cell"><div class="bar-wrap"><div class="bar-fill {bar_cls}" style="width:{pct*100:.0f}%"></div></div></td>
  <td class="vote-pct">{pct*100:.0f}%</td>
</tr>""")

    # Ensemble total row
    if total_votes > 0:
        yes_votes = sum(m.get("votes", 0) for m in by_model.values())
        ens_pct   = yes_votes / total_votes
        bar_cls   = _bar_class(ens_pct)
        rows.append(f"""
<tr class="ensemble-row">
  <td class="model-name">ENSEMBLE</td>
  <td class="model-members">{total_votes}</td>
  <td class="model-avg">—</td>
  <td class="model-bias">—</td>
  <td class="bar-cell"><div class="bar-wrap"><div class="bar-fill {bar_cls}" style="width:{ens_pct*100:.0f}%"></div></div></td>
  <td class="vote-pct">{ens_pct*100:.0f}%</td>
</tr>""")

    return "\n".join(rows)


def _cards_html(signals: list) -> str:
    if not signals:
        return '<div class="empty-msg">No signals with ≥15% edge this run. Try again after the next market update.</div>'

    parts = []
    for sig in signals:
        signal   = sig.get("signal", "SKIP")
        sc       = _sc(signal)
        edge_pct = sig.get("edge_pct", 0)
        our_prob = sig.get("ensemble_probability", 0)
        poly_p   = sig.get("polymarket_price")
        kal_p    = sig.get("kalshi_price")
        best_pl  = sig.get("best_platform", "")
        by_model = sig.get("by_model", {})

        # Handle by_model stored as JSON string (from logger)
        if isinstance(by_model, str):
            import json
            try:
                by_model = json.loads(by_model)
            except Exception:
                by_model = {}

        total_v  = sig.get("total_votes", 0)
        q        = sig.get("question", "")

        poly_url = sig.get("polymarket_url", "")
        kal_url  = sig.get("kalshi_url",     "")
        best_url = (poly_url if best_pl == "polymarket" else kal_url) or poly_url or kal_url

        q_html   = f'<a href="{best_url}" target="_blank">{q}</a>' if best_url else q

        metric_lbl = _metric_label(
            sig.get("metric",     "temperature_2m"),
            sig.get("threshold",  "?"),
            sig.get("comparison", "above"),
        )

        # Platform action text
        action_note = ""
        if signal == "BET":
            action_note = f'<span class="plat-sub best">↑ BUY YES on {best_pl.capitalize()}</span>'
        else:
            action_note = f'<span class="plat-sub fade-note">↓ BUY NO on {best_pl.capitalize()}</span>'

        # Which platform has the better edge (highlight best price)
        poly_cls = " (best edge)" if best_pl == "polymarket" else ""
        kal_cls  = " (best edge)" if best_pl == "kalshi"     else ""

        parts.append(f"""
<div class="card {sc}">
  <div class="card-head">
    <div>
      <span class="badge {sc}">{signal}</span>
      <div class="edge-big">{edge_pct:+.1f}%</div>
    </div>
    <div class="head-info">
      <div class="question-line">{q_html}</div>
      <div class="meta-line">
        {sig.get("city", "")} &bull; {sig.get("target_date", "")} &bull; {metric_lbl}
        &bull; {total_v} ensemble votes
      </div>
    </div>
  </div>
  <div class="card-body">
    <table class="model-table">
      <thead>
        <tr>
          <th>Model</th><th>Members</th><th>Avg Fcst</th><th>Bias</th><th style="width:100px">Vote %</th><th></th>
        </tr>
      </thead>
      <tbody>
        {_model_rows(by_model, total_v)}
      </tbody>
    </table>
    <div class="platform-row">
      <div class="plat">
        {'<a href="' + poly_url + '" target="_blank" style="text-decoration:none">' if poly_url else ''}
        <div class="plat-name poly">Polymarket{'↗' if poly_url else ''}</div>
        <div class="plat-price poly">{_fmt_price(poly_p)}</div>
        <div class="plat-sub">{"YES price" + poly_cls}</div>
        {'</a>' if poly_url else ''}
      </div>
      <div class="plat">
        {'<a href="' + kal_url + '" target="_blank" style="text-decoration:none">' if kal_url else ''}
        <div class="plat-name kal">Kalshi{'↗' if kal_url else ''}</div>
        <div class="plat-price kal">{_fmt_price(kal_p)}</div>
        <div class="plat-sub">{"YES price" + kal_cls}</div>
        {'</a>' if kal_url else ''}
      </div>
      <div class="plat">
        <div class="plat-name ours">Our Model</div>
        <div class="plat-price ours">{our_prob*100:.1f}%</div>
        {action_note}
      </div>
    </div>
  </div>
</div>""")

    return "\n".join(parts)


def _backtest_bar(bt: dict) -> str:
    win_rate  = bt.get("win_rate", 0)
    avg_edge  = bt.get("avg_edge_pct", 0)
    pnl       = bt.get("total_pnl", 0.0)
    bets      = bt.get("bets_placed", 0)
    brier     = bt.get("brier_score", 0.25)
    days      = bt.get("backtest_days", 90)
    cities    = bt.get("cities_analyzed", 0)

    win_cls  = "win"  if win_rate >= 0.5 else "loss"
    pnl_cls  = "pnl-pos" if pnl >= 0 else "pnl-neg"
    pnl_str  = f"{pnl:+.2f}"
    brier_str = f"{brier:.4f}"
    # Brier score: 0.25 = random, lower = better
    brier_note = "↑ good" if brier < 0.22 else ("≈ avg" if brier < 0.26 else "↓ below avg")

    return f"""
<div class="backtest-bar">
  <div class="bt-label">Backtest<br>{days}d · {cities} cities</div>
  <div class="bt-stats">
    <div class="bt-stat {win_cls}">
      <div class="bv">{win_rate*100:.1f}%</div>
      <div class="bl">Win Rate</div>
    </div>
    <div class="bt-stat neutral">
      <div class="bv">{avg_edge:.1f}%</div>
      <div class="bl">Avg Edge</div>
    </div>
    <div class="bt-stat {pnl_cls}">
      <div class="bv">{pnl_str}</div>
      <div class="bl">P&amp;L (units)</div>
    </div>
    <div class="bt-stat neutral">
      <div class="bv">{bets}</div>
      <div class="bl">Bets Simulated</div>
    </div>
    <div class="bt-stat brier">
      <div class="bv">{brier_str}</div>
      <div class="bl">Brier Score <small style="font-size:0.55rem;color:var(--muted)">{brier_note}</small></div>
    </div>
  </div>
</div>"""


def _history_rows(history: list) -> str:
    if not history:
        return '<tr><td colspan="9" class="empty-td">No historical signals yet.</td></tr>'

    rows = []
    for e in reversed(history[-100:]):
        signal = e.get("signal", "SKIP")
        sc     = _sc(signal)
        edge   = e.get("edge_pct", 0)
        ts     = e.get("timestamp", "")[:16].replace("T", " ")
        eprob  = e.get("ensemble_probability", 0) or e.get("forecast_yes_probability", 0)
        best   = e.get("best_platform", "")

        plat_tag = ""
        if best == "polymarket":
            plat_tag = '<span class="plat-tag poly">Polymarket</span>'
        elif best == "kalshi":
            plat_tag = '<span class="plat-tag kal">Kalshi</span>'

        rows.append(f"""
<tr>
  <td class="ts">{ts}</td>
  <td>{e.get("city", "")}</td>
  <td class="qs" title="{e.get('question','')}">{e.get("question","")}</td>
  <td>{e.get("market_yes_price", 0) * 100:.1f}%</td>
  <td>{eprob * 100:.1f}%</td>
  <td class="edge-td" style="color:{'var(--bet)' if edge > 0 else 'var(--fade)'}">{edge:+.1f}%</td>
  <td><span class="bsm {sc}">{signal}</span></td>
  <td>{plat_tag}</td>
  <td style="color:var(--muted);font-size:.72rem">{e.get("total_votes","—")}</td>
</tr>""")

    return "\n".join(rows)


def generate_dashboard(signals: list, history: list = None, backtest: dict = None) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    history  = history  or []
    backtest = backtest or {}

    now     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bet_n   = sum(1 for s in signals if s.get("signal") == "BET")
    fade_n  = sum(1 for s in signals if s.get("signal") == "FADE")
    total_h = len(history)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="3600">
<title>Weather Edge — Ensemble</title>
<style>{_CSS}</style>
</head>
<body>

<div class="header">
  <div>
    <div class="logo">Weather <em>Edge</em></div>
    <div class="logo-sub">ECMWF · GFS · NAM · UKMET &nbsp;|&nbsp; Polymarket + Kalshi &nbsp;|&nbsp; 15% edge filter</div>
  </div>
  <div class="header-right">
    {now}<br>
    {bet_n} BET · {fade_n} FADE · {total_h} all-time signals<br>
    <span style="color:var(--muted2);font-size:.72rem">refreshes every hour</span>
  </div>
</div>

<div class="container">

  {_backtest_bar(backtest)}

  <div class="section-hdr">High-Confidence Signals <span>≥15% edge only</span></div>
  <div class="cards">
    {_cards_html(signals)}
  </div>

  <div class="section-hdr">Signal History <span>last {min(len(history), 100)}</span></div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>UTC</th><th>City</th><th>Question</th>
          <th>Market Yes</th><th>Ensemble</th><th>Edge</th>
          <th>Signal</th><th>Platform</th><th>Votes</th>
        </tr>
      </thead>
      <tbody>
        {_history_rows(history)}
      </tbody>
    </table>
  </div>

</div>
</body>
</html>"""

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard → {os.path.abspath(DASHBOARD_PATH)}")
