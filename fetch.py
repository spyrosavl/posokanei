#!/usr/bin/env python3
"""Download a full daily snapshot of products and prices from posokanei.gov.gr.

The product listing endpoint already embeds per-retailer prices and price
stats, so a single paginated crawl captures the whole price picture. Each daily
snapshot is therefore self-contained; the sequence of snapshots is the history.

Output: data/<YYYY>/posokanei-<YYYY-MM-DD>.json  (plain JSON), containing:
    {
      "date": "...", "fetched_at": "...", "source": "...",
      "total": <int>,
      "retailers": {...},      # /meta/retailers?countries=all
      "categories": {...},     # /meta/categories
      "products": [ ... ]      # every product, all pages merged
    }

Stored uncompressed and pretty-printed with products sorted by id and stable
key order, so day-to-day snapshots are nearly identical line-by-line. Git's
delta compression then stores each new day as a tiny delta against the previous,
keeping repository growth small despite the ~20 MB working-tree file.

Stdlib only (no pip install needed in CI).
"""

import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.posokanei.gov.gr"
PAGE_SIZE = 100          # API maximum
COUNTRIES = "all"        # full catalogue (GR + international)
USER_AGENT = "posokanei-archive/1.0 (+https://github.com/spyrosavl/posokanei-archive)"
TIMEOUT = 60
MAX_RETRIES = 5
RETRY_BACKOFF = 3        # seconds, multiplied by attempt number
PER_PAGE_DELAY = 0.3     # politeness pause between pages


def get_json(path):
    """GET a JSON endpoint with retries and exponential-ish backoff."""
    url = f"{BASE}{path}"
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as err:
            last_err = err
            wait = RETRY_BACKOFF * attempt
            print(f"  ! {url} failed (attempt {attempt}/{MAX_RETRIES}): {err}; "
                  f"retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last_err}")


def fetch_all_products():
    """Paginate the full product listing and return every product."""
    first = get_json(f"/products?page=1&page_size={PAGE_SIZE}&countries={COUNTRIES}")
    total = first.get("total", 0)
    total_pages = first.get("total_pages", 1)
    products = list(first.get("products", []))
    print(f"products: {total} total across {total_pages} pages")

    for page in range(2, total_pages + 1):
        time.sleep(PER_PAGE_DELAY)
        data = get_json(
            f"/products?page={page}&page_size={PAGE_SIZE}&countries={COUNTRIES}"
        )
        batch = data.get("products", [])
        products.extend(batch)
        if page % 10 == 0 or page == total_pages:
            print(f"  page {page}/{total_pages} ({len(products)} collected)")

    if total and len(products) != total:
        print(f"  WARNING: collected {len(products)} but total reported {total}",
              file=sys.stderr)
    return total, products


HISTORY_PATH = os.path.join("data", "history.csv")


def update_history(date, total, collected):
    """Append (or replace) today's row in the append-only history CSV.

    Returns the full, date-sorted list of (date, total, collected) rows.
    """
    rows = {}
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows[r["date"]] = (int(r["total"]), int(r["collected"]))
    rows[date] = (total, collected)  # idempotent re-runs overwrite the day

    ordered = sorted(rows.items())
    with open(HISTORY_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["date", "total", "collected"])
        for d, (t, c) in ordered:
            w.writerow([d, t, c])
    return [(d, t, c) for d, (t, c) in ordered]


def main():
    today = dt.date.today().isoformat()
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()

    print("fetching meta ...")
    retailers = get_json("/meta/retailers?countries=all")
    categories = get_json("/meta/categories")

    total, products = fetch_all_products()

    # Stable ordering so the same product keeps the same position every day,
    # which keeps git deltas between consecutive snapshots minimal.
    products.sort(key=lambda p: p.get("id", ""))

    snapshot = {
        "date": today,
        "fetched_at": fetched_at,
        "source": BASE,
        "countries": COUNTRIES,
        "total": total,
        "collected": len(products),
        "retailers": retailers,
        "categories": categories,
        "products": products,
    }

    out_dir = os.path.join("data", today[:4])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"posokanei-{today}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, sort_keys=True, indent=1)

    size_mb = os.path.getsize(out_path) / 1e6
    print(f"wrote {out_path} ({size_mb:.2f} MB, {len(products)} products)")

    # Pointer to the newest snapshot for convenient access.
    with open(os.path.join("data", "latest.json"), "w", encoding="utf-8") as fh:
        json.dump({"date": today, "path": out_path,
                   "total": total, "collected": len(products)}, fh, indent=2)

    update_history(today, total, len(products))


if __name__ == "__main__":
    main()
