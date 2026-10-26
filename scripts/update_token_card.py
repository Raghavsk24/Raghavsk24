"""Rebuilds the profile card's token usage graph and facts."""

import argparse
import datetime as dt
import json
import os
import subprocess
from itertools import accumulate
from pathlib import Path

from top_model import display_name, top_model

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "token-usage.json"
AGENT = REPO / "data" / "coding-agent.json"
ASSETS = REPO / "assets"
LOGS = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"

FACTS = [
    ("Name", "Raghav Senthil Kumar"),
    ("Age", "18"),
    ("School", "UIUC"),
    ("Coding Agent", None),
    ("Current", "AgentPhone (YC S26)"),
    ("Previous", "Clusion, Jetson"),
    ("Interests", "Alignment, Agents, Robotics, Chess"),
]
THEMES = {
    "light": dict(text="#1f3a68", muted="#57709a", line="#2f6fd6", grid="#d0d7de"),
    "dark": dict(text="#dce8ff", muted="#8fa8d6", line="#7fb2ff", grid="#30363d"),
}

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


# Returns the Monday that starts the given day's week.
def week_start(day):
    return day - dt.timedelta(days=day.weekday())


# Totals tokens per day and per model per week from logs.
def scan_logs():
    seen, days, models = set(), {}, {}
    for path in LOGS.glob("**/*.jsonl"):
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if '"usage"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                msg = entry.get("message")
                usage = msg.get("usage") if isinstance(msg, dict) else None
                ts = entry.get("timestamp")
                if not usage or not ts:
                    continue
                key = (msg.get("id"), entry.get("requestId"))
                if key in seen:
                    continue
                seen.add(key)
                day = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date()
                tokens = sum(usage.get(k, 0) for k in USAGE_KEYS)
                days[day.isoformat()] = days.get(day.isoformat(), 0) + tokens
                week = models.setdefault(week_start(day).isoformat(), {})
                week[msg.get("model", "")] = week.get(msg.get("model", ""), 0) + tokens
    return days, models


# Saves finished days and last week's top model, returning both.
def update_history():
    history = json.loads(DATA.read_text()) if DATA.exists() else {}
    agent = json.loads(AGENT.read_text()) if AGENT.exists() else {"model": "claude-opus-5-5"}
    this_week = week_start(dt.date.today())
    days, models = scan_logs()
    for day, total in days.items():
        if day < this_week.isoformat():
            history[day] = max(history.get(day, 0), total)
    last_week = (this_week - dt.timedelta(weeks=1)).isoformat()
    model = top_model(models.get(last_week, {}))
    if model:
        agent = {"week": last_week, "model": model}
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(dict(sorted(history.items())), indent=2) + "\n")
    AGENT.write_text(json.dumps(agent, indent=2) + "\n")
    return history, display_name(agent["model"])


# Formats millions of tokens as a short label like 1.23B.
def fmt(millions):
    return f"{millions / 1000:.2f}B" if millions >= 1000 else f"{millions:.0f}M"


# Picks a round gridline step so three lines cover the data.
def grid_step(top):
    mag = 1
    while True:
        for m in (1, 2, 2.5, 4, 5):
            if m * mag * 3.2 >= top:
                return m * mag
        mag *= 10


# Draws the graph and facts as one SVG card.
def render(history, facts, c):
    first = dt.date.fromisoformat(min(history))
    last = week_start(dt.date.today()) - dt.timedelta(days=1)
    days = [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]
    totals = list(accumulate(history.get(d.isoformat(), 0) / 1e6 for d in days))

    x0, x1, top, base = 90, 410, 50, 172
    step = grid_step(totals[-1])
    gridlines = [step * i for i in range(4)]
    vmax = max(gridlines[-1], totals[-1]) * 1.12
    n = len(days)
    xs = [round(x0 + i * (x1 - x0) / max(n - 1, 1), 1) for i in range(n)]

    def y(v):
        return round(base - v / vmax * (base - top), 1)

    every = max(1, -(-n // 5))
    labeled = {i for i in range(0, n, every) if n - 1 - i >= every / 2} | {n - 1}

    out = ['  <text x="36" y="26">Token usage</text>']
    for g in gridlines:
        out.append(f'  <line x1="{x0 - 10}" y1="{y(g)}" x2="{x1 + 10}" y2="{y(g)}" class="grid"/>')
        out.append(f'  <text x="{x0 - 18}" y="{y(g) + 4}" class="muted sm" text-anchor="end">{fmt(g) if g else "0"}</text>')
    pts = " ".join(f"{x},{y(v)}" for x, v in zip(xs, totals))
    out.append(f'  <polygon points="{xs[0]},{base} {pts} {xs[-1]},{base}" fill="{c["line"]}" fill-opacity="0.1"/>')
    out.append(f'  <polyline points="{pts}" fill="none" stroke="{c["line"]}" stroke-width="2" stroke-linejoin="round"/>')
    for i, (x, d) in enumerate(zip(xs, days)):
        out.append(f'  <line x1="{x}" y1="{base}" x2="{x}" y2="{base + (5 if i in labeled else 3)}" class="tick"/>')
        if i in labeled:
            out.append(f'  <text x="{x}" y="{base + 18}" class="muted sm" text-anchor="middle">{d.month}/{d.day}</text>')
    out.append(f'  <circle cx="{xs[-1]}" cy="{y(totals[-1])}" r="3.5" class="dot"/>')
    out.append(f'  <text x="{xs[-1]}" y="{y(totals[-1]) - 10}" class="sm" text-anchor="middle">{fmt(totals[-1])}</text>')
    out.append(f'  <line x1="450" y1="20" x2="450" y2="200" stroke="{c["grid"]}"/>')
    for i, (k, v) in enumerate(facts):
        out.append(f'  <text x="480" y="{44 + 25 * i}" class="muted">{k}</text>')
        out.append(f'  <text x="595" y="{44 + 25 * i}">{v}</text>')

    body = "\n".join(out)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 220" width="900" height="220">
  <style>
    text {{ font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace; font-size: 13px; fill: {c["text"]}; }}
    .muted {{ fill: {c["muted"]}; }}
    .sm {{ font-size: 11px; }}
    .grid {{ stroke: {c["grid"]}; stroke-dasharray: 2 4; }}
    .tick {{ stroke: {c["muted"]}; stroke-opacity: 0.6; }}
    .dot {{ fill: {c["line"]}; }}  </style>
{body}
</svg>
'''


# Runs a git command inside this repo.
def git(*args):
    subprocess.run(["git", "-C", str(REPO), *args], check=True)


# Updates data and cards, then optionally commits and pushes.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="commit and push the updated card")
    args = parser.parse_args()

    history, agent = update_history()
    facts = [(k, agent if k == "Coding Agent" else v) for k, v in FACTS]
    for name, colors in THEMES.items():
        (ASSETS / f"profile-card-{name}.svg").write_text(render(history, facts, colors), encoding="utf-8")
    if args.push:
        paths = ["data", "assets/profile-card-light.svg", "assets/profile-card-dark.svg"]
        changed = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", *paths],
                                 capture_output=True, text=True, check=True).stdout.strip()
        if changed:
            git("add", *paths)
            git("commit", "-m", "Update token usage graph", "--", *paths)
            git("pull", "--rebase", "--autostash")
            git("push")


if __name__ == "__main__":
    main()
