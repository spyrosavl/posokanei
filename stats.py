#!/usr/bin/env python3
"""Υπολογίζει «ιστορίες» από τις τιμές της τελευταίας λήψης και γράφει STATS.md.

Στατιστικά μίας ημέρας (δεν χρειάζεται ιστορικό), γραμμένα σαν αφήγηση για μη
ειδικούς:
  1. Το ίδιο προϊόν, εντελώς διαφορετική τιμή ανά σούπερ μάρκετ
  2. Ποιο σούπερ μάρκετ είναι το φθηνότερο
  3. Πού αξίζει να ψάξεις πριν αγοράσεις (ανά κατηγορία)
  4. Επώνυμο ή προϊόν ιδιωτικής ετικέτας;
  5. Η Ελλάδα φθηνότερη ή ακριβότερη από την υπόλοιπη Ευρώπη;

Διαβάζει το data/latest.json -> path· γράφει STATS.md. Μόνο stdlib.
"""

import json
import statistics as st
from collections import defaultdict

LATEST = "data/latest.json"
OUT = "STATS.md"

# Όρια αξιοπιστίας: κόβουν τιμές μονάδας λανθασμένα κολλημένες σε πολυσυσκευασίες.
MIN_PRICE = 1.0          # αγνόησε «φθηνότερες» τιμές κάτω από €1 στις διαφορές
MIN_UNIT = 0.5           # κατώφλι €/μονάδα για συγκρίσεις ανά μονάδα


def load():
    ptr = json.load(open(LATEST, encoding="utf-8"))
    snap = json.load(open(ptr["path"], encoding="utf-8"))
    rmeta = {r["id"]: r for r in snap["retailers"]["retailers"]}
    gr = {i for i, r in rmeta.items() if r["country"] == "GR"}
    eu = {i for i, r in rmeta.items() if r["country"] != "GR"}
    names = {i: r["name"] for i, r in rmeta.items()}
    return snap, gr, eu, names


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


def robust_spread(pr):
    """(pct, abs, lo, hi) για ένα dict τιμών, ή None αν μοιάζει με κακά δεδομένα.

    Απαιτεί η 2η φθηνότερη να είναι έως 2x της φθηνότερης, ώστε μια μεμονωμένη
    λάθος τιμή μονάδας να μην κατασκευάζει ψεύτικη «διαφορά».
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
    top = rows[0]
    story = (
        "## 🥇 Το ίδιο προϊόν, εντελώς διαφορετική τιμή\n\n"
        f"Το ίδιο ακριβώς προϊόν μπορεί να κοστίζει **{top[0]/100+1:.1f} φορές** "
        "περισσότερο — ανάλογα με το πού θα ψωνίσεις. Πρωταθλητής σήμερα: "
        f"**{top[5]}**, που πουλιέται **€{top[2]:.2f}** στο {top[6]} αλλά "
        f"**€{top[3]:.2f}** στο {top[7]} — διαφορά **+{top[0]:.0f}%** για το πανομοιότυπο "
        "προϊόν. Πριν το βάλεις στο καλάθι, αξίζει μια ματιά στην ετικέτα:\n")
    tbl = ["| Προϊόν | Φθηνότερα | Ακριβότερα | Διαφορά |",
           "|---|---|---|---|"]
    for pct, _a, lo, hi, _n, name, cheap, exp in rows[:10]:
        tbl.append(f"| {name} | €{lo:.2f} {cheap} | €{hi:.2f} {exp} | **+{pct:.0f}%** |")
    return story + "\n" + "\n".join(tbl), rows


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
    best, worst = order[0], order[-1]
    story = (
        "## 🏆 Ποιο σούπερ μάρκετ είναι το φθηνότερο;\n\n"
        f"Συγκρίναμε **{contested:,}** προϊόντα που πωλούνται σε τουλάχιστον δύο ελληνικές "
        f"αλυσίδες. Πιο συχνά φθηνότερο βγαίνει το **{names[best]}** "
        f"(έχει την καλύτερη τιμή στο {wins[best]/appears[best]*100:.0f}% των περιπτώσεων), "
        f"ενώ στο **{names[worst]}** πληρώνεις κατά μέσο όρο **+{st.mean(prem[worst]):.0f}%** "
        "παραπάνω σε σχέση με το να αγόραζες κάθε προϊόν εκεί που έχει την πιο χαμηλή τιμή. "
        "Ολόκληρη η κατάταξη:\n")
    tbl = ["| Σούπερ μάρκετ | Φορές φθηνότερο | Μέση επιβάρυνση vs φθηνότερου |",
           "|---|---|---|"]
    for r in order:
        pct = wins[r] / appears[r] * 100
        ap = st.mean(prem[r]) if prem[r] else 0
        tbl.append(f"| {names[r]} | {pct:.0f}% | +{ap:.0f}% |")
    return story + "\n" + "\n".join(tbl)


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
    top = rank[0]
    story = (
        "## 🛒 Πού αξίζει να ψάξεις πριν αγοράσεις\n\n"
        "Σε κάποιες κατηγορίες η τιμή για το ίδιο πράγμα αλλάζει δραματικά από μαγαζί σε "
        f"μαγαζί — εκεί η σύγκριση σε ανταμείβει περισσότερο. Πρωταθλητές τα **{top}**, "
        f"όπου η μέση διαφορά τιμής αγγίζει το **{st.mean(cat[top]):.0f}%**. "
        "Οι κατηγορίες όπου το ψάξιμο πληρώνει:\n")
    tbl = ["| Κατηγορία | Μέση διαφορά μεταξύ μαγαζιών | Προϊόντα |",
           "|---|---|---|"]
    for c in rank[:10]:
        tbl.append(f"| {c} | {st.mean(cat[c]):.0f}% | {len(cat[c])} |")
    return story + "\n" + "\n".join(tbl)


def stat_private_label(prods, gr):
    pl = defaultdict(lambda: [[], []])  # κατηγορία -> [ιδιωτική[], επώνυμα[]]
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
    top = gaps[0]
    story = (
        "## 🏷️ Επώνυμο ή προϊόν ιδιωτικής ετικέτας;\n\n"
        "Τα προϊόντα ιδιωτικής ετικέτας (της ίδιας της αλυσίδας) κοστίζουν σταθερά πολύ "
        f"λιγότερο από τα επώνυμα. Η μεγαλύτερη διαφορά είναι στην κατηγορία **{top[1]}**, "
        f"όπου γλιτώνεις έως και **{top[0]:.0f}%** ανά μονάδα. Πού συμφέρει περισσότερο το "
        "προϊόν του σούπερ μάρκετ:\n")
    tbl = ["| Κατηγορία | Ιδιωτική ετικέτα | Επώνυμο | Γλιτώνεις |",
           "|---|---|---|---|"]
    for pct, c, mp, mb in gaps[:10]:
        tbl.append(f"| {c} | €{mp:.2f}/μον. | €{mb:.2f}/μον. | **{pct:.0f}%** |")
    return story + "\n" + "\n".join(tbl)


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
    deltas = [r[0] for r in rows]
    n = len(deltas)
    cheaper = sum(1 for x in deltas if x < -2)
    pricier = sum(1 for x in deltas if x > 2)
    similar = n - cheaper - pricier
    much_ch = sum(1 for x in deltas if x < -20)
    much_pr = sum(1 for x in deltas if x > 20)
    median = st.median(deltas)
    story = (
        "## 🇬🇷🇪🇺 Η Ελλάδα φθηνότερη ή ακριβότερη από την Ευρώπη;\n\n"
        f"Βρήκαμε **{n:,}** προϊόντα που πωλούνται και στην Ελλάδα και σε άλλες ευρωπαϊκές "
        "αλυσίδες, και συγκρίναμε την τιμή τους **ανά μονάδα** (ανά κιλό ή λίτρο, ώστε οι "
        "διαφορετικές συσκευασίες να είναι συγκρίσιμες).\n\n"
        f"Από αυτά, τα **{cheaper:,} ({cheaper/n*100:.0f}%) είναι φθηνότερα** στην Ελλάδα και "
        f"τα **{pricier:,} ({pricier/n*100:.0f}%) ακριβότερα**· το υπόλοιπο "
        f"{similar/n*100:.0f}% έχει ουσιαστικά ίδια τιμή. Συνολικά η Ελλάδα βγαίνει ελαφρώς "
        f"φθηνότερη — η διάμεση διαφορά είναι **{median:+.0f}%** σε σχέση με την Ευρώπη. "
        "Οι ακρότητες όμως είναι έντονες: "
        f"**{much_ch:,} προϊόντα ({much_ch/n*100:.0f}%)** είναι πάνω από 20% φθηνότερα εδώ, "
        f"ενώ **{much_pr:,} ({much_pr/n*100:.0f}%)** πάνω από 20% ακριβότερα.\n\n"
        "**Πολύ φθηνότερα στην Ελλάδα:**\n")
    t1 = ["| Προϊόν | Ελλάδα | Ευρώπη | Διαφορά |", "|---|---|---|---|"]
    for pct, gm, em, name, u in rows[:6]:
        t1.append(f"| {name} | €{gm:.2f}/{u} | €{em:.2f}/{u} | **{pct:.0f}%** |")
    t2 = ["", "**Πολύ ακριβότερα στην Ελλάδα:**", "",
          "| Προϊόν | Ελλάδα | Ευρώπη | Διαφορά |", "|---|---|---|---|"]
    for pct, gm, em, name, u in rows[-6:][::-1]:
        t2.append(f"| {name} | €{gm:.2f}/{u} | €{em:.2f}/{u} | **+{pct:.0f}%** |")
    return story + "\n" + "\n".join(t1) + "\n" + "\n".join(t2)


def main():
    snap, gr, eu, names = load()
    prods = snap["products"]
    spread_md, _ = stat_spread(prods, gr, names)
    parts = [
        f"# 📊 Τι κρύβουν οι τιμές των σούπερ μάρκετ — {snap['date']}",
        "",
        f"Κάθε μέρα κατεβάζουμε ολόκληρο τον κατάλογο του Παρατηρητηρίου Τιμών "
        f"(**{snap['total']:,} προϊόντα** από **{len(gr)} ελληνικά σούπερ μάρκετ**) και "
        "ψάχνουμε τις πιο ενδιαφέρουσες ιστορίες που κρύβονται στους αριθμούς. Να τι "
        "βρήκαμε σήμερα.",
        "",
        "_Οι συγκρίσεις μεταξύ σούπερ μάρκετ αφορούν μόνο ελληνικές αλυσίδες και έχουν "
        "καθαριστεί από λάθη του Παρατηρητηρίου (τιμές μονάδας λανθασμένα συνδεδεμένες με "
        "πολυσυσκευασίες)._",
        "",
        spread_md, "",
        stat_leaderboard(prods, gr, names), "",
        stat_categories(prods, gr), "",
        stat_private_label(prods, gr), "",
        stat_greece_vs_europe(prods, gr, eu), "",
    ]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(f"wrote {OUT} for {snap['date']}")


if __name__ == "__main__":
    main()
