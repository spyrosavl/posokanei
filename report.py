#!/usr/bin/env python3
"""Render the daily Greek price briefing; standard library only."""

import html
from xml.etree import ElementTree

import report_charts

OUT_DIR = "docs"
SOURCE_URL = "https://posokanei.gov.gr"
REPO_URL = "https://github.com/spyrosavl/posokanei"
_MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου",
           "Ιουνίου", "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου",
           "Νοεμβρίου", "Δεκεμβρίου"]


def _esc(value):
    return html.escape(str(value))


def _date_long(iso):
    y, m, d = (int(x) for x in iso.split('-'))
    return f'{d} {_MONTHS[m - 1]} {y}'


def _int(n):
    return f'{n:,}'.replace(',', '.')


def _eur(value):
    return f'€{value:.2f}'.replace('.', ',')


def _pct(value):
    return f'{value:+d}%'.replace('-', '−') if value else '0%'


def _figure(name, alt, charts):
    root = ElementTree.fromstring(charts[name + ".svg"])
    height = root.get("height")
    chart_text = " · ".join(root.find("{http://www.w3.org/2000/svg}g").itertext())
    alt = f"{alt} {chart_text}"
    return (f'<figure><img class="chart" src="assets/{name}.svg" alt="{_esc(alt)}" '
            f'width="600" height="{height}" loading="lazy">'
            f'<figcaption><a href="assets/{name}.svg" download>Λήψη γραφήματος SVG ↗</a>'
            '</figcaption></figure>')


def _spread_rows(rows):
    out = []
    ceiling = max((r['hi'] for r in rows), default=1)
    for r in rows:
        lo, hi = r['lo'] / ceiling * 100, r['hi'] / ceiling * 100
        out.append(f'''<article class="spread-row">
          <div class="spread-title"><h3>{_esc(r['name'])}</h3>
          <strong>{_eur(r['hi'] - r['lo'])}<small>διαφορά · +{r['pct']}%</small></strong></div>
          <div class="price-line" aria-hidden="true"><span style="left:{lo:.2f}%;width:{hi-lo:.2f}%"></span>
          <i style="left:{lo:.2f}%"></i><i class="high" style="left:{hi:.2f}%"></i></div>
          <div class="price-labels"><span><b>{_eur(r['lo'])}</b> {_esc(r['lo_chain'])}</span>
          <span><b>{_eur(r['hi'])}</b> {_esc(r['hi_chain'])}</span></div></article>''')
    return ''.join(out) or '<p>Δεν υπάρχουν αρκετά συγκρίσιμα προϊόντα.</p>'


def _europe_examples(rows):
    return ''.join(f'''<li><span>{_esc(r['name'])}<small>Ελλάδα {_eur(r['gm'])}/{_esc(r['unit'] or 'μον.')} ·
        αλλού {_eur(r['em'])}/{_esc(r['unit'] or 'μον.')}</small></span><b>{_pct(r['pct'])}</b></li>'''
        for r in rows[:3]) or '<li>Δεν υπάρχουν διαθέσιμα παραδείγματα.</li>'


def _private_rows(rows):
    return ''.join(f'''<tr><th scope="row">{_esc(r['cat'])}<small>ανά {_esc(r['unit'] or 'μονάδα')}</small></th>
        <td><span class="mobile-label" aria-hidden="true">Ιδιωτική ετικέτα</span>{_eur(r['mp'])}</td>
        <td><span class="mobile-label" aria-hidden="true">Επώνυμα</span>{_eur(r['mb'])}</td>
        <td class="accent"><span class="mobile-label" aria-hidden="true">Διαφορά</span>{_pct(-r['save_pct'])}</td></tr>'''
        for r in rows)


def render(d):
    date = _date_long(d['date'])
    charts = report_charts.render(d)
    lb, cats, gve = d['leaderboard'], d['categories'], d['gve']
    spread = d['spread']
    snapshot = f'{REPO_URL}/blob/main/{d["source_path"]}' if d.get('source_path') else REPO_URL
    if spread:
        r = spread[0]
        featured = f'''<div class="receipt"><div class="eyebrow">Η ΣΥΓΚΡΙΣΗ ΤΗΣ ΗΜΕΡΑΣ <span>ΣΗΜΕΡΑ</span></div>
          <h2>Το ίδιο προϊόν.<br>Δύο διαφορετικές τιμές.</h2>
          <p class="product">{_esc(r['name'])}</p>
          <div class="receipt-prices"><div><strong>{_eur(r['lo'])}</strong><span>{_esc(r['lo_chain'])}</span></div>
          <span class="arrow" aria-hidden="true">→</span><div><strong>{_eur(r['hi'])}</strong><span>{_esc(r['hi_chain'])}</span></div></div>
          <div class="receipt-bottom"><span>Διαφορά <b>{_eur(r['hi'] - r['lo'])}</b></span>
          <a href="#price-gaps">Δες τις συγκρίσεις ↗</a></div></div>'''
    else:
        featured = '<div class="receipt"><h2>Οι τιμές με μια ματιά.</h2><p>Δεν υπάρχουν αρκετά δεδομένα για σύγκριση μεμονωμένων προϊόντων.</p><a href="#retailers">Δες την ανάλυση ↗</a></div>'
    retailer_summary = (f'{_esc(lb["best_name"])} · {lb["best_pct"]}%' if lb['rows'] else 'Δεν υπάρχουν αρκετά δεδομένα')
    category_summary = (f'{_esc(cats[0]["cat"])} · {cats[0]["pct"]}%' if cats else 'Δεν υπάρχουν αρκετά δεδομένα')
    europe_summary = f'{_pct(gve["median"])} διάμεση διαφορά' if gve['n'] else 'Δεν υπάρχουν αρκετά δεδομένα'
    retailer_table = ''.join(f'<tr><th scope="row">{_esc(r["name"])}</th><td>{_int(r["count"])}</td><td>{r["win_pct"]}%</td><td>+{r["premium"]}%</td></tr>' for r in lb['rows'])
    return f'''<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Πόσο κάνει τελικά; · {date}</title>
<meta name="description" content="Οι τιμές των σούπερ μάρκετ, με μια ματιά. Καθημερινές συγκρίσεις τιμών, αλυσίδων και προϊόντων από τα δεδομένα του posokanei.gov.gr.">
<link rel="stylesheet" href="report.css">
</head>
<body>
<a class="skip-link" href="#main">Μετάβαση στην ανάλυση</a>
<div class="wrap">
<header class="topbar">
  <a class="brand" href="#"><span class="brand-mark" aria-hidden="true">≈</span> posokanei<span class="brand-dot">.</span></a>
  <nav aria-label="Εργαλεία"><a href="{REPO_URL}">GitHub ↗</a><a href="{_esc(snapshot)}">Δεδομένα ↗</a><button onclick="window.print()">Εκτύπωση / PDF</button></nav>
</header>
<main id="main">
  <section class="hero" aria-labelledby="hero-title">
    <div class="hero-copy"><p class="eyebrow"><span class="live-dot" aria-hidden="true"></span> ΚΑΘΗΜΕΡΙΝΗ ΑΝΑΛΥΣΗ · <time datetime="{d['date']}">{date}</time></p>
      <h1 id="hero-title">Πόσο κάνει<br><em>τελικά;</em></h1>
      <p class="dek">Οι τιμές των σούπερ μάρκετ,<br>με μια ματιά.</p>
      <p class="intro">Το ίδιο ράφι, άλλη τιμή. Συγκρίνουμε τα δεδομένα του Παρατηρητηρίου Τιμών για να δεις πού αξίζει να ψάξεις.</p>
      <a class="text-link" href="#retailers">Εξερεύνησε τη σημερινή εικόνα ↓</a>
    </div>{featured}
  </section>
  <div class="coverage"><span><b>{_int(d['total'])}</b> προϊόντα στον κατάλογο</span><span><b>{d['n_gr']}</b> ελληνικές αλυσίδες</span>
    <span><b>{_int(lb['contested'])}</b> προϊόντα σε ≥2 αλυσίδες</span><a href="#methodology">Πηγές &amp; μεθοδολογία ↗</a></div>
  <nav class="takeaways" aria-label="Σημερινά ευρήματα">
    <a href="#retailers"><span>ΣΥΧΝΟΤΕΡΑ ΣΤΗ ΧΑΜΗΛΟΤΕΡΗ ΤΙΜΗ</span><strong>{retailer_summary}</strong><small>Στα συγκρίσιμα προϊόντα που διαθέτει ↗</small></a>
    <a href="#categories"><span>ΜΕΓΑΛΥΤΕΡΗ ΜΕΣΗ ΔΙΑΦΟΡΑ</span><strong>{category_summary}</strong><small>Μεταξύ καταστημάτων, στο ίδιο προϊόν ↗</small></a>
    <a href="#europe"><span>ΕΛΛΑΔΑ &amp; ΕΥΡΩΠΗ</span><strong>{europe_summary}</strong><small>Σε {_int(gve['n'])} συγκρίσιμα προϊόντα ↗</small></a>
  </nav>
  <nav class="section-nav" aria-label="Ενότητες"><a href="#retailers">01 Αλυσίδες</a><a href="#categories">02 Κατηγορίες</a><a href="#europe">03 Ευρώπη</a><a href="#price-gaps">04 Προϊόντα</a><a href="#private-label">05 Ιδιωτική ετικέτα</a></nav>
  <div class="chart-grid">
    <section id="retailers" class="panel">
      <p class="eyebrow">01 / ΑΛΥΣΙΔΕΣ</p><h2>Ποιος βγαίνει<br>συχνότερα φθηνότερος;</h2>
      <p>Μετράμε πόσο συχνά κάθε αλυσίδα έχει τη χαμηλότερη τιμή στα συγκρίσιμα προϊόντα που διαθέτει. Οι ισοπαλίες μετρούν για όλες τις αλυσίδες.</p>
      {_figure('retailers', 'Κατάταξη αλυσίδων: ποσοστό προϊόντων στη χαμηλότερη τιμή και μέγεθος δείγματος.', charts)}
      <details><summary>Αριθμοί &amp; μέση επιβάρυνση</summary><div class="table-scroll" tabindex="0" role="region" aria-label="Στοιχεία αλυσίδων"><table><thead><tr><th>Αλυσίδα</th><th>Προϊόντα</th><th>Χαμηλότερη</th><th>Επιβάρυνση</th></tr></thead><tbody>{retailer_table}</tbody></table></div>
      <p class="note">Η επιβάρυνση είναι ο μέσος όρος των ποσοστιαίων διαφορών από τη χαμηλότερη τιμή, μόνο για προϊόντα σε ≥3 αλυσίδες. Δεν είναι διαφορά κόστους ενός σταθερού καλαθιού. Κάθε αλυσίδα έχει διαφορετικό δείγμα.</p></details>
    </section>
    <section id="categories" class="panel">
      <p class="eyebrow">02 / ΚΑΤΗΓΟΡΙΕΣ</p><h2>Πού αξίζει<br>μια δεύτερη ματιά;</h2>
      <p>Οι κατηγορίες με τη μεγαλύτερη μέση διαφορά ανάμεσα στη χαμηλότερη και την υψηλότερη τιμή του ίδιου προϊόντος.</p>
      {_figure('categories', 'Οι δέκα κατηγορίες με τη μεγαλύτερη μέση ποσοστιαία διαφορά τιμής και τα αντίστοιχα δείγματα.', charts)}
      <p class="note">Ανά προϊόν: (υψηλότερη − χαμηλότερη) / χαμηλότερη τιμή. Κρατάμε κατηγορίες με τουλάχιστον 30 προϊόντα, μετά το φίλτρο ακραίων τιμών.</p>
    </section>
  </div>
  <section id="europe" class="europe panel">
    <div><p class="eyebrow">03 / ΕΛΛΑΔΑ &amp; ΕΥΡΩΠΗ</p><h2>Το ίδιο προϊόν,<br>πέρα από τα σύνορα.</h2>
    <p>Συγκρίνουμε τις διάμεσες τιμές ανά μονάδα στην Ελλάδα και στις άλλες ευρωπαϊκές χώρες του δείγματος. Κάθε προϊόν έχει τουλάχιστον δύο ελληνικές τιμές και παρουσία σε δύο άλλες χώρες.</p>
    <p class="note">Οι συγκρίσεις αφορούν το διαθέσιμο δείγμα, όχι το συνολικό κόστος ζωής. «Παρόμοια» σημαίνει από −2% έως +2%.</p></div>
    {_figure('europe', f'Ελλάδα και Ευρώπη: {gve["cheaper_pct"]}% φθηνότερα, {gve["similar_pct"]}% παρόμοια, {gve["pricier_pct"]}% ακριβότερα. Δείγμα {gve["n"]} προϊόντων.', charts)}
    <div class="examples"><h3>Χαμηλότερες τιμές στην Ελλάδα</h3><ul>{_europe_examples([r for r in gve['cheap_rows'] if r['pct'] < -2])}</ul></div>
    <div class="examples"><h3>Υψηλότερες τιμές στην Ελλάδα</h3><ul>{_europe_examples([r for r in gve['pricey_rows'] if r['pct'] > 2])}</ul></div>
  </section>
  <section id="price-gaps" class="panel spread-panel">
    <div class="section-heading"><div><p class="eyebrow">04 / ΙΔΙΟ ΠΡΟΪΟΝ, ΑΛΛΗ ΤΙΜΗ</p><h2>Μικρή σύγκριση.<br>Μεγάλη διαφορά.</h2></div><p>Οι μεγαλύτερες διαφορές σε προϊόντα με τιμές από τουλάχιστον τέσσερις ελληνικές αλυσίδες, μετά το φίλτρο ακραίων τιμών.</p></div>
    <p class="note">Τα σημεία δείχνουν τη χαμηλότερη και την υψηλότερη τιμή. Κοινή κλίμακα από €0 για όλα τα προϊόντα.</p>
    {_spread_rows(spread)}
  </section>
  <section id="private-label" class="panel">
    <div class="section-heading"><div><p class="eyebrow">05 / ΙΔΙΩΤΙΚΗ ΕΤΙΚΕΤΑ</p><h2>Η ετικέτα αλλάζει.<br>Η τιμή επίσης.</h2></div><p>Συγκρίνουμε διάμεσες τιμές ανά μονάδα, μέσα στην ίδια κατηγορία. Πρόκειται για διαφορετικά προϊόντα, όχι για ισοδύναμες επιλογές ή εγγυημένη οικονομία.</p></div>
    <div class="table-scroll" tabindex="0" role="region" aria-label="Σύγκριση ιδιωτικής ετικέτας"><table><thead><tr><th>Κατηγορία / μονάδα</th><th>Ιδιωτική ετικέτα</th><th>Επώνυμα</th><th>Διαφορά</th></tr></thead><tbody>{_private_rows(d['private_label'])}</tbody></table></div>
    <p class="note">Διάμεσοι τιμών προϊόντων ανά κατηγορία και μονάδα: τουλάχιστον 5 προϊόντα ιδιωτικής ετικέτας και 15 επώνυμα. Διαφορά = (ιδιωτική ετικέτα − επώνυμα) / επώνυμα.</p>
  </section>
</main>
<footer id="methodology">
  <div><a class="brand" href="#">posokanei.</a><p>Ανοιχτά δεδομένα. Καθημερινή εικόνα.</p><p class="note">Ανεξάρτητη ανάλυση δεδομένων του επίσημου Παρατηρητηρίου Τιμών.<br>Στιγμιότυπο {date}.</p></div>
  <div><h2>Πηγές &amp; μεθοδολογία</h2><p>Πηγή: <a href="{SOURCE_URL}">posokanei.gov.gr ↗</a> · <a href="{_esc(snapshot)}">Ακριβές στιγμιότυπο ↗</a></p>
    <p>Οι τιμές είναι αυτές του στιγμιότυπου και μπορεί να διαφέρουν στο κατάστημα. Στις διαφορές ανά προϊόν και κατηγορία αποκλείουμε ελάχιστες τιμές κάτω από €1 και ακραίες τιμές που απέχουν πάνω από 1,5× από τη δεύτερη χαμηλότερη ή υψηλότερη. Τα φίλτρα περιορίζουν πιθανά σφάλματα· δεν εγγυώνται την ακρίβεια της πηγής.</p>
    <p><a href="{REPO_URL}/blob/main/stats.py">Υπολογισμοί ↗</a> · <a href="{REPO_URL}">Κώδικας &amp; ιστορικό αρχείο ↗</a></p></div>
</footer>
</div>
</body>
</html>'''
_DEMO = {
    "date": "2026-06-24", "total": 8164, "n_gr": 10,
    "source_path": "data/2026/posokanei-2026-06-24.json",
    "leaderboard": {"contested": 5618, "best_name": "Lidl", "best_pct": 55,
                    "worst_name": "ΑΒ Βασιλόπουλος", "worst_premium": 19,
                    "rows": [{"name": "Lidl", "win_pct": 55, "premium": 7},
                             {"name": "Σκλαβενίτης", "win_pct": 44, "premium": 9},
                             {"name": "ΑΒ Βασιλόπουλος", "win_pct": 12, "premium": 19}]},
    "categories": [{"cat": "Παγωτά", "pct": 82, "count": 45},
                   {"cat": "Εσπρέσσο", "pct": 49, "count": 32}],
    "private_label": [{"cat": "Γάτα", "save_pct": 77, "mp": 1.8, "mb": 7.77},
                      {"cat": "Κρασί", "save_pct": 70, "mp": 2.09, "mb": 6.91}],
    "gve": {"n": 1425, "cheaper": 776, "similar": 96, "pricier": 553,
            "cheaper_pct": 54, "similar_pct": 7, "pricier_pct": 39, "median": -5,
            "much_ch": 337, "much_ch_pct": 24, "much_pr": 253, "much_pr_pct": 18,
            "cheap_rows": [{"name": "PARODONTAX 500ml", "gm": 7.72, "em": 22.18,
                            "unit": "L", "pct": -65}],
            "pricey_rows": [{"name": "NESTLE Φρουτοπουρές 90gr", "gm": 18.11,
                             "em": 6.56, "unit": "kg", "pct": 176}]},
    "spread": [{"name": "ΚΡΙ ΚΡΙ Παγωτό 1,5kg", "pct": 254, "lo": 3.99,
                "lo_chain": "Lidl", "hi": 14.12, "hi_chain": "ΣΥΝ.ΚΑ"}],
}


if __name__ == "__main__":
    import os
    import report_charts
    for row in _DEMO['leaderboard']['rows']:
        row['count'] = 100
    for row in _DEMO['private_label']:
        row['unit'] = 'kg'
    report_charts.write(_DEMO, os.path.join(OUT_DIR, 'assets'))
    with open(os.path.join(OUT_DIR, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(render(_DEMO))
    print(f'wrote {OUT_DIR}/index.html and charts (demo data)')
