#!/usr/bin/env python3
"""Υπολογίζει «ιστορίες» από τις τιμές της τελευταίας λήψης για το docs/index.html.

Στατιστικά μίας ημέρας (δεν χρειάζεται ιστορικό), για μη ειδικούς:
  1. Ποιο σούπερ μάρκετ είναι το φθηνότερο
  2. Πού αξίζει να ψάξεις πριν αγοράσεις (ανά κατηγορία)
  3. Η Ελλάδα φθηνότερη ή ακριβότερη από την υπόλοιπη Ευρώπη;
  4. Το ίδιο προϊόν, εντελώς διαφορετική τιμή ανά σούπερ μάρκετ
  5. Επώνυμο ή προϊόν ιδιωτικής ετικέτας;

Διαβάζει το data/latest.json -> path, υπολογίζει τα δεδομένα και τα δίνει στο
report.render() που γράφει το docs/index.html. Μόνο stdlib.
"""

import json
import os
import statistics as st
from collections import defaultdict

LATEST = "data/latest.json"

# Όρια αξιοπιστίας: κόβουν τιμές μονάδας λανθασμένα κολλημένες σε πολυσυσκευασίες.
MIN_PRICE = 1.0          # αγνόησε «φθηνότερες» τιμές κάτω από €1 στις διαφορές
MIN_UNIT = 0.5           # κατώφλι €/μονάδα για συγκρίσεις ανά μονάδα
MIN_EU_COUNTRIES = 2     # μην το πεις «Ευρώπη» αν είναι ένα μόνο ξένο μαγαζί/χώρα


def load():
    ptr = json.load(open(LATEST, encoding="utf-8"))
    snap = json.load(open(ptr["path"], encoding="utf-8"))
    rmeta = {r["id"]: r for r in snap["retailers"]["retailers"]}
    gr = {i for i, r in rmeta.items() if r["country"] == "GR"}
    eu = {i for i, r in rmeta.items() if r["country"] != "GR"}
    names = {i: r["name"] for i, r in rmeta.items()}
    return snap, gr, eu, names, ptr["path"]


def gr_prices(p, gr):
    """Φθηνότερη τιμή ανά ελληνικό σούπερ μάρκετ για ένα προϊόν."""
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


SUPPORT = 1.5  # πόσο μακριά επιτρέπεται η ακραία τιμή από τη 2η ακραία


def robust_spread(pr):
    """(pct, lo, hi, lo_r, hi_r) για ένα dict {αλυσίδα: τιμή}, ή None.

    Απορρίπτουμε το προϊόν αν η φθηνότερη ή η ακριβότερη τιμή είναι μεμονωμένο
    «ξεκάρφωτο» outlier — πάνω από 1.5x μακριά από τη 2η φθηνότερη/ακριβότερη.
    Έτσι μια λάθος καταχωρημένη τιμή (π.χ. μονάδα κολλημένη σε πολυσυσκευασία)
    δεν κατασκευάζει ψεύτικη «διαφορά»· η διαφορά πρέπει να στηρίζεται σε τιμές
    πολλών καταστημάτων, όχι σε ένα ύποπτο νούμερο.
    """
    vals = sorted(pr.values())
    lo, lo2, hi2, hi = vals[0], vals[1], vals[-2], vals[-1]
    if lo < MIN_PRICE or lo2 > SUPPORT * lo or hi > SUPPORT * hi2:
        return None
    lo_r, hi_r = min(pr, key=pr.get), max(pr, key=pr.get)
    return (hi - lo) / lo * 100, lo, hi, lo_r, hi_r


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
    if not order:
        return {"contested": contested, "best_name": "—", "best_pct": 0,
                "worst_name": "—", "worst_premium": 0, "rows": []}
    # best = πιο συχνά φθηνότερο· worst = σπανιότερα φθηνότερο (το άλλο άκρο της
    # κατάταξης). Το worst_premium είναι η δική του μέση επιβάρυνση — δεν το
    # παρουσιάζουμε ως «το ακριβότερο μαγαζί» (βλ. διατύπωση στο report.py).
    best, worst = order[0], order[-1]
    return {
        "contested": contested,
        "best_name": names[best],
        "best_pct": round(wins[best] / appears[best] * 100),
        "worst_name": names[worst],
        "worst_premium": round(st.mean(prem[worst])) if prem[worst] else 0,
        "rows": [{"name": names[r],
                  "win_pct": round(wins[r] / appears[r] * 100),
                  "premium": round(st.mean(prem[r])) if prem[r] else 0}
                 for r in order],
    }


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
    return [{"cat": c, "pct": round(st.mean(cat[c])), "count": len(cat[c])}
            for c in rank[:10]]


def stat_greece_vs_europe(prods, gr, eu):
    rows = []
    for p in prods:
        g = [rp["price_normalized"] for rp in p["retailer_prices"]
             if rp["retailer"] in gr and rp.get("price_normalized")]
        e = [rp["price_normalized"] for rp in p["retailer_prices"]
             if rp["retailer"] in eu and rp.get("price_normalized")]
        countries = {rp["country"] for rp in p["retailer_prices"]
                     if rp["retailer"] in eu and rp.get("price_normalized")}
        # Απαιτούμε >=2 διαφορετικές ευρωπαϊκές χώρες, ώστε η «Ευρώπη» να μην
        # είναι ένα μόνο ξένο κατάστημα (π.χ. μόνο μία κυπριακή αλυσίδα).
        if len(g) >= 2 and len(countries) >= MIN_EU_COUNTRIES:
            gm, em = st.median(g), st.median(e)
            if gm >= MIN_UNIT and em >= MIN_UNIT:
                rows.append(((gm - em) / em * 100, gm, em, p["name"], p.get("unit")))
    rows.sort()
    deltas = [r[0] for r in rows]
    n = len(deltas)
    if not n:
        return {"n": 0, "cheaper": 0, "similar": 0, "pricier": 0,
                "cheaper_pct": 0, "similar_pct": 0, "pricier_pct": 0, "median": 0,
                "much_ch": 0, "much_ch_pct": 0, "much_pr": 0, "much_pr_pct": 0,
                "cheap_rows": [], "pricey_rows": []}
    cheaper = sum(1 for x in deltas if x < -2)
    pricier = sum(1 for x in deltas if x > 2)
    similar = n - cheaper - pricier
    much_ch = sum(1 for x in deltas if x < -20)
    much_pr = sum(1 for x in deltas if x > 20)
    median = st.median(deltas)
    return {
        "n": n, "cheaper": cheaper, "similar": similar, "pricier": pricier,
        "cheaper_pct": round(cheaper / n * 100),
        "similar_pct": round(similar / n * 100),
        "pricier_pct": round(pricier / n * 100),
        "median": round(median),
        "much_ch": much_ch, "much_ch_pct": round(much_ch / n * 100),
        "much_pr": much_pr, "much_pr_pct": round(much_pr / n * 100),
        "cheap_rows": [{"name": name, "gm": gm, "em": em, "unit": u,
                        "pct": round(pct)} for pct, gm, em, name, u in rows[:6]],
        "pricey_rows": [{"name": name, "gm": gm, "em": em, "unit": u,
                         "pct": round(pct)}
                        for pct, gm, em, name, u in rows[-6:][::-1]],
    }


def stat_spread(prods, gr, names):
    rows = []
    for p in prods:
        pr = gr_prices(p, gr)
        if len(pr) >= 4:
            s = robust_spread(pr)
            if s:
                pct, lo, hi, lo_r, hi_r = s
                rows.append((pct, lo, hi, p["name"], names[lo_r], names[hi_r]))
    rows.sort(reverse=True)
    return [{"name": name, "pct": round(pct), "lo": lo, "lo_chain": cheap,
             "hi": hi, "hi_chain": exp}
            for pct, lo, hi, name, cheap, exp in rows[:5]]


def stat_private_label(prods, gr):
    # Ομαδοποίηση ανά (κατηγορία, μονάδα): €/τεμ, €/λίτρο και €/κιλό δεν είναι
    # συγκρίσιμα, οπότε δεν τα ανακατεύουμε ποτέ στην ίδια διάμεσο.
    pl = defaultdict(lambda: [[], []])  # (κατηγορία, μονάδα) -> [ιδιωτική[], επώνυμα[]]
    for p in prods:
        n = med_unit(p, gr)
        if n:
            key = (p.get("category") or "—", p.get("unit") or "—")
            pl[key][0 if p.get("private_label") else 1].append(n)
    gaps = []
    for (c, _u), (pv, br) in pl.items():
        if len(pv) >= 5 and len(br) >= 15:
            mp, mb = st.median(pv), st.median(br)
            if mb > 0:
                gaps.append(((mb - mp) / mb * 100, c, mp, mb))
    gaps.sort(reverse=True)
    return [{"cat": c, "save_pct": round(pct), "mp": mp, "mb": mb}
            for pct, c, mp, mb in gaps[:10]]


def main():
    snap, gr, eu, names, src_path = load()
    prods = snap["products"]
    report_data = {
        "date": snap["date"],
        "total": snap["total"],
        "n_gr": len(gr),
        "source_path": src_path,
        "leaderboard": stat_leaderboard(prods, gr, names),
        "categories": stat_categories(prods, gr),
        "private_label": stat_private_label(prods, gr),
        "gve": stat_greece_vs_europe(prods, gr, eu),
        "spread": stat_spread(prods, gr, names),
    }
    import report
    os.makedirs(report.OUT_DIR, exist_ok=True)
    out_html = os.path.join(report.OUT_DIR, "index.html")
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(report.render(report_data))
    print(f"wrote {out_html} for {snap['date']}")


if __name__ == "__main__":
    main()
