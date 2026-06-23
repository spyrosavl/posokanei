#!/usr/bin/env python3
"""Compute 'wow' price stats from the latest snapshot and write STATS.md.

Single-snapshot, cross-sectional stats (no history needed):
  1. Same product, biggest price gap across Greek supermarkets
  2. Cheapest-supermarket leaderboard (+ average premium over the cheapest)
  3. Categories where shopping around saves the most
  4. Own-brand vs branded savings, per unit
  5. Products much cheaper / pricier in Greece vs the rest of Europe

Reads data/latest.json -> path; writes STATS.md. Stdlib only.
"""

import json
import statistics as st
from collections import defaultdict

LATEST = "data/latest.json"
OUT = "STATS.md"

# Robustness floors: kill single-unit prices mis-tagged onto multipack SKUs.
MIN_PRICE = 1.0          # ignore sub-€1 "cheapest" outliers in spread stats
MIN_UNIT = 0.5           # €/unit floor for normalized comparisons


def load():
    ptr = json.load(open(LATEST, encoding="utf-8"))
    snap = json.load(open(ptr["path"], encoding="utf-8"))
    rmeta = {r["id"]: r for r in snap["retailers"]["retailers"]}
    gr = {i for i, r in rmeta.items() if r["country"] == "GR"}
    eu = {i for i, r in rmeta.items() if r["country"] != "GR"}
    names = {i: r["name"] for i, r in rmeta.items()}
    return snap, gr, eu, names


def gr_prices(p, gr):
    """Cheapest price per Greek retailer for a product."""
    out = {}
    for rp in p["retailer_prices"]:
        r = rp["retailer"]
        if r in gr and rp.get("price") and rp["price"] > 0:
            out[r] = min(rp["price"], out.get(r, 1e9))
    return out


def med_unit(p, ids):
    vs = [rp["price_normalized"] for rp in p["retailer_prices"]
          if rp["retailer"] in ids and rp.get("price_normalized")]
    return st.median(vs) if vs else None


def robust_spread(pr):
    """(pct, abs, lo, hi) for a price dict, or None if it looks like bad data.

    Requires the 2nd-cheapest within 2x of the cheapest, so a lone mis-tagged
    single-unit price can't manufacture a fake 'gap'.
    """
    vals = sorted(pr.values())
    lo, lo2, hi = vals[0], vals[1], vals[-1]
    if lo >= MIN_PRICE and lo2 <= 2 * lo:
        return (hi - lo) / lo * 100, hi - lo, lo, hi
    return None


def stat_spread(prods, gr, names):
    rows = []
    for p in prods:
        pr = gr_prices(p, gr)
        if len(pr) >= 4:
            s = robust_spread(pr)
            if s:
                rows.append((*s, len(pr), p["name"],
                             names[min(pr, key=pr.get)], names[max(pr, key=pr.get)]))
    rows.sort(reverse=True)
    out = ["## 🥇 Same product, biggest gap between supermarkets",
           "",
           "The identical product, priced wildly differently depending where you shop "
           "(≥4 Greek chains):",
           "",
           "| Product | Cheapest | Priciest | Gap |",
           "|---|---|---|---|"]
    for pct, _a, lo, hi, _n, name, cheap, exp in rows[:10]:
        out.append(f"| {name} | €{lo:.2f} {cheap} | €{hi:.2f} {exp} | **+{pct:.0f}%** |")
    return "\n".join(out), rows


def stat_leaderboard(prods, gr, names):
    wins = defaultdict(int)
    appears = defaultdict(int)
    prem = defaultdict(list)
    contested = 0
    for p in prods:
        pr = gr_prices(p, gr)
        if len(pr) >= 2:
            contested += 1
            lo = min(pr.values())
            for r, v in pr.items():
                appears[r] += 1
                if abs(v - lo) < 1e-9:
                    wins[r] += 1
                if len(pr) >= 3:
                    prem[r].append((v - lo) / lo * 100)
    order = sorted((r for r in gr if appears[r] >= 50),
                   key=lambda r: -wins[r] / appears[r])
    out = ["## 🏆 Cheapest-supermarket leaderboard",
           "",
           f"Across **{contested:,}** products sold at ≥2 Greek chains — who wins on "
           "price, and how much more you pay elsewhere (average premium over the "
           "per-product cheapest):",
           "",
           "| Supermarket | Cheapest | Avg premium over cheapest |",
           "|---|---|---|"]
    for r in order:
        pct = wins[r] / appears[r] * 100
        ap = st.mean(prem[r]) if prem[r] else 0
        out.append(f"| {names[r]} | {pct:.1f}% | +{ap:.1f}% |")
    return "\n".join(out)


def stat_categories(prods, gr):
    cat = defaultdict(list)
    for p in prods:
        pr = gr_prices(p, gr)
        if len(pr) >= 3:
            s = robust_spread(pr)
            if s:
                cat[p.get("category") or "—"].append(s[0])
    rank = sorted((c for c in cat if len(cat[c]) >= 30),
                  key=lambda c: -st.mean(cat[c]))
    out = ["## 🛒 Where shopping around pays off most",
           "",
           "Average price spread across chains, by category — the aisles that reward "
           "comparison:",
           "",
           "| Category | Avg cross-shop spread | Products |",
           "|---|---|---|"]
    for c in rank[:10]:
        out.append(f"| {c} | {st.mean(cat[c]):.0f}% | {len(cat[c])} |")
    return "\n".join(out)


def stat_private_label(prods, gr):
    pl = defaultdict(lambda: [[], []])  # category -> [private[], branded[]]
    for p in prods:
        n = med_unit(p, gr)
        if n:
            pl[p.get("category") or "—"][0 if p.get("private_label") else 1].append(n)
    gaps = []
    for c, (pv, br) in pl.items():
        if len(pv) >= 5 and len(br) >= 15:
            mp, mb = st.median(pv), st.median(br)
            gaps.append(((mb - mp) / mb * 100, c, mp, mb))
    gaps.sort(reverse=True)
    out = ["## 🏷️ Own-brand vs branded savings",
           "",
           "How much private label undercuts branded products, per unit (median €/unit):",
           "",
           "| Category | Own-brand | Branded | You save |",
           "|---|---|---|---|"]
    for pct, c, mp, mb in gaps[:10]:
        out.append(f"| {c} | €{mp:.2f}/u | €{mb:.2f}/u | **{pct:.0f}%** |")
    return "\n".join(out)


def stat_greece_vs_europe(prods, gr, eu):
    rows = []
    for p in prods:
        g = [rp["price_normalized"] for rp in p["retailer_prices"]
             if rp["retailer"] in gr and rp.get("price_normalized")]
        e = [rp["price_normalized"] for rp in p["retailer_prices"]
             if rp["retailer"] in eu and rp.get("price_normalized")]
        if len(g) >= 2 and len(e) >= 1:
            gm, em = st.median(g), st.median(e)
            if gm >= MIN_UNIT and em >= MIN_UNIT:
                rows.append(((gm - em) / em * 100, gm, em, p["name"], p.get("unit")))
    rows.sort()
    median = st.median([r[0] for r in rows]) if rows else 0
    out = ["## 🇬🇷🇪🇺 Greece vs the rest of Europe",
           "",
           f"Per-unit prices for **{len(rows):,}** products carried by both Greek and "
           f"non-Greek retailers. Median Greek price is **{median:+.1f}%** vs Europe.",
           "",
           "**Much cheaper in Greece:**",
           "",
           "| Product | Greece | Europe | Difference |",
           "|---|---|---|---|"]
    for pct, gm, em, name, u in rows[:6]:
        out.append(f"| {name} | €{gm:.2f}/{u} | €{em:.2f}/{u} | **{pct:.0f}%** |")
    out += ["", "**Much pricier in Greece:**", "",
            "| Product | Greece | Europe | Difference |",
            "|---|---|---|---|"]
    for pct, gm, em, name, u in rows[-6:][::-1]:
        out.append(f"| {name} | €{gm:.2f}/{u} | €{em:.2f}/{u} | **+{pct:.0f}%** |")
    return "\n".join(out)


def main():
    snap, gr, eu, names = load()
    prods = snap["products"]
    spread_md, _ = stat_spread(prods, gr, names)
    parts = [
        f"# 📊 Price stats — {snap['date']}",
        "",
        f"Auto-generated from the latest snapshot ({snap['total']:,} products, "
        f"{len(gr)} Greek supermarkets). Regenerated daily by `stats.py`.",
        "",
        "Cross-supermarket comparisons are restricted to Greek chains and filtered "
        "to remove pack-size mis-tags (single-unit prices mistakenly attached to "
        "multipack listings in the source data).",
        "",
        spread_md,
        "",
        stat_leaderboard(prods, gr, names),
        "",
        stat_categories(prods, gr),
        "",
        stat_private_label(prods, gr),
        "",
        stat_greece_vs_europe(prods, gr, eu),
        "",
    ]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(f"wrote {OUT} for {snap['date']}")


if __name__ == "__main__":
    main()
