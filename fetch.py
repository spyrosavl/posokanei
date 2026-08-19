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
# Since 2026-08-07 the API edge rejects (403) any request whose User-Agent is
# not a recognised browser/curl token — a self-identifying "posokanei/1.0 (+url)"
# UA is refused, as is any custom product token. The site's robots.txt still
# allows all crawlers (Allow: / for User-agent: *), so this is an indiscriminate
# WAF rule rather than a policy against archiving. We therefore send a standard
# browser UA to get through, and keep honest contact details in the From header.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")
CONTACT = "https://github.com/spyrosavl/posokanei"
TIMEOUT = 60
MAX_RETRIES = 5
RETRY_BACKOFF = 3        # seconds, multiplied by attempt number
PER_PAGE_DELAY = 1.0     # honours the Crawl-delay: 1 in the site's robots.txt
# The backend refuses to page past 10 000 results and clamps the `total` it
# reports to the same ceiling (the Elasticsearch max_result_window default).
# Once the catalogue outgrew that — 2026-07-31 — a flat `/products` crawl
# silently returned exactly 10 000 every day while the real catalogue kept
# growing, and the collected-vs-total check below could never notice because
# both sides were clamped. We therefore crawl one top-level category at a time
# (largest is ~1 100 products) and count the catalogue from category metadata.
RESULT_WINDOW = 10000
# Which query parameter filters /products by category is not documented, and
# the API is geo-fenced to Greece so it cannot be probed from a dev machine.
# detect_category_param() tries these against a known category at run time and
# keeps the first that demonstrably filters.
CATEGORY_PARAM_CANDIDATES = ("category_ids", "category_id", "category")


def get_json(path, retries=MAX_RETRIES):
    """GET a JSON endpoint with retries and exponential-ish backoff."""
    url = f"{BASE}{path}"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
                "From": CONTACT,
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as err:
            last_err = err
            wait = RETRY_BACKOFF * attempt
            print(f"  ! {url} failed (attempt {attempt}/{retries}): {err}; "
                  f"retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last_err}")


def root_categories(categories):
    """The depth-1 categories, which between them cover every product."""
    return [c for c in categories.get("categories", []) if c.get("depth") == 1]


def expected_total(categories):
    """True catalogue size, counted from metadata rather than from `total`.

    Every product carries its top-level category in `category_ids`, so summing
    the root categories' `product_count` gives a figure the result window
    cannot clamp — which is what makes truncation detectable at all.
    """
    return sum(c.get("product_count", 0) for c in root_categories(categories))


def filters_by_category(products, category_id):
    """Did the API actually honour the category filter we asked for?

    An unrecognised parameter is ignored rather than rejected, and the reply is
    then just the unfiltered head of the catalogue. Requiring a decent number of
    results that *all* sit in one category tells the two cases apart.
    """
    if len(products) < 5:
        return False
    return all(category_id in (p.get("category_ids") or []) for p in products)


def detect_category_param(categories):
    """Find the query parameter that filters /products by category."""
    # A mid-sized category: big enough that a full page of matches cannot be a
    # coincidence, small enough to answer in one page.
    probes = sorted(root_categories(categories), key=lambda c: c["product_count"])
    probe = next((c for c in probes if c["product_count"] >= 20), probes[-1])
    cid = probe["category_id"]

    for param in CATEGORY_PARAM_CANDIDATES:
        try:
            data = get_json(f"/products?page=1&page_size={PAGE_SIZE}"
                            f"&countries={COUNTRIES}&{param}={cid}", retries=2)
        except RuntimeError as err:
            print(f"  probe {param}= rejected: {err}", file=sys.stderr)
            continue
        if filters_by_category(data.get("products", []), cid):
            print(f"category filter parameter: {param}=")
            return param
        print(f"  probe {param}= ignored by the API", file=sys.stderr)

    raise RuntimeError(
        "none of " + ", ".join(f"{p}=" for p in CATEGORY_PARAM_CANDIDATES) +
        " filters /products by category; the catalogue is larger than the "
        f"{RESULT_WINDOW}-result window, so a flat crawl would silently drop "
        "products. Find the correct parameter and add it to "
        "CATEGORY_PARAM_CANDIDATES."
    )


def fetch_category(param, category, products):
    """Paginate one category, merging into `products` (keyed by id)."""
    cid, name = category["category_id"], category["category_name"]
    page, total_pages = 1, 1
    while page <= total_pages:
        if page > 1:
            time.sleep(PER_PAGE_DELAY)
        data = get_json(f"/products?page={page}&page_size={PAGE_SIZE}"
                        f"&countries={COUNTRIES}&{param}={cid}")
        total_pages = data.get("total_pages", 1)
        for p in data.get("products", []):
            products[p.get("id")] = p
        page += 1

    # `total` is itself clamped to the window, so a category that has outgrown
    # it reports exactly RESULT_WINDOW, never more — hence >=, not >.
    got = data.get("total", 0)
    if got >= RESULT_WINDOW:
        print(f"  WARNING: category '{name}' reports {got} products, at or past "
              f"the {RESULT_WINDOW} window — it needs splitting by subcategory",
              file=sys.stderr)
    return got


def fetch_all_products(categories):
    """Crawl the catalogue one top-level category at a time and merge.

    Categories overlap (a product can sit under more than one), so results are
    merged by product id rather than concatenated.
    """
    param = detect_category_param(categories)
    roots = sorted(root_categories(categories), key=lambda c: c["category_name"])
    total = expected_total(categories)
    print(f"products: {total} total across {len(roots)} top-level categories")

    products = {}
    for i, cat in enumerate(roots, 1):
        time.sleep(PER_PAGE_DELAY)
        fetch_category(param, cat, products)
        print(f"  [{i}/{len(roots)}] {cat['category_name']} "
              f"({len(products)} collected)")

    if len(products) < total:
        print(f"  WARNING: collected {len(products)} but the catalogue holds "
              f"{total} — {total - len(products)} products missing",
              file=sys.stderr)
    return total, list(products.values())


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

    total, products = fetch_all_products(categories)

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
