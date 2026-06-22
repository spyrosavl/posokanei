#!/usr/bin/env python3
"""Render data/history.csv as assets/products.png (daily products fetched).

Kept separate from fetch.py so the crawler stays dependency-free; only this
step needs matplotlib (see requirements.txt).
"""

import csv
import datetime as dt
import os

import matplotlib

matplotlib.use("Agg")  # headless backend for CI
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

HISTORY_PATH = os.path.join("data", "history.csv")
CHART_PATH = os.path.join("assets", "products.png")


def load_history():
    with open(HISTORY_PATH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    dates = [dt.date.fromisoformat(r["date"]) for r in rows]
    totals = [int(r["total"]) for r in rows]
    return dates, totals


def main():
    dates, totals = load_history()

    fig, ax = plt.subplots(figsize=(9, 3.2), dpi=140)
    ax.plot(dates, totals, color="#2563eb", linewidth=2,
            marker="o", markersize=4 if len(dates) <= 60 else 0)
    ax.fill_between(dates, totals, min(totals), color="#2563eb", alpha=0.08)

    ax.set_title(f"posokanei.gov.gr — products fetched per day "
                 f"(latest: {totals[-1]:,})", fontsize=11, loc="left")
    ax.set_ylabel("products")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate(rotation=30, ha="right")

    # Avoid a flat-looking single-value axis when few points exist.
    lo, hi = min(totals), max(totals)
    pad = max((hi - lo) * 0.15, 5)
    ax.set_ylim(lo - pad, hi + pad)

    os.makedirs(os.path.dirname(CHART_PATH), exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    print(f"wrote {CHART_PATH} ({len(dates)} points)")


if __name__ == "__main__":
    main()
