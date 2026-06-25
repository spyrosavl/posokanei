#!/usr/bin/env python3
"""Φτιάχνει μια έτοιμη για εκτύπωση/PDF αναφορά τιμών (docs/index.html).

Καθαρός renderer: δέχεται τα ίδια δεδομένα που υπολογίζει το stats.py και τα
μετατρέπει σε αυτόνομη HTML σελίδα (warm theme) για το GitHub Pages. Καμία
εξάρτηση — μόνο stdlib. Καλείται από το stats.main()· μπορεί όμως να τρέξει και
μόνο του με dummy δεδομένα για γρήγορο preview (python report.py).
"""

import html

OUT_DIR = "docs"

# Πηγές (ανοιχτά δεδομένα + κώδικας) — εμφανίζονται με συνδέσμους στη σελίδα.
SOURCE_URL = "https://posokanei.gov.gr"          # επίσημο Παρατηρητήριο Τιμών
REPO_URL = "https://github.com/spyrosavl/posokanei"  # ανοιχτός κώδικας + στιγμιότυπα

# Μήνες στη γενική (όπως στις ελληνικές ημερομηνίες) — με και χωρίς τόνο.
_MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου",
           "Ιουνίου", "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου",
           "Νοεμβρίου", "Δεκεμβρίου"]
_MONTHS_UP = ["ΙΑΝΟΥΑΡΙΟΥ", "ΦΕΒΡΟΥΑΡΙΟΥ", "ΜΑΡΤΙΟΥ", "ΑΠΡΙΛΙΟΥ", "ΜΑΪΟΥ",
              "ΙΟΥΝΙΟΥ", "ΙΟΥΛΙΟΥ", "ΑΥΓΟΥΣΤΟΥ", "ΣΕΠΤΕΜΒΡΙΟΥ", "ΟΚΤΩΒΡΙΟΥ",
              "ΝΟΕΜΒΡΙΟΥ", "ΔΕΚΕΜΒΡΙΟΥ"]

# Emoji ανά κατηγορία — όσες είναι γνωστές παίρνουν εικονίδιο, οι υπόλοιπες όχι.
_EMOJI = {
    "Παγωτά": "🍦", "Γάτα": "🐱", "Κρασί": "🍷", "Μαρμελάδα": "🍓",
    "Μακρύκοκο Ρύζι": "🍚", "Styling": "💇", "Σκύλος": "🐶", "Μπισκότα": "🍪",
    "Χλωρίνη": "🧴", "Αλεύρι": "🌾", "Μουστάρδα": "🌭", "Εσπρέσσο": "☕",
    "Κάψουλες Εσπρέσσο": "☕", "Βαφές Μαλλιών": "💈", "Αποσμητικά": "🧴",
    "Κρεμοσάπουνα": "🧼", "Μπάρες Δημητριακών": "🥣", "Πίτες και Πιτάκια": "🥧",
    "Πουλερικά, Αλλαντικά": "🍗", "Ρύζι": "🍚", "Καφές": "☕", "Γάλα": "🥛",
    "Τυρί": "🧀", "Νερό": "💧", "Μπύρα": "🍺", "Χυμοί": "🧃",
}

# Παλέτες μπαρών (fill, text-color) — τράκαρα τα χρώματα του αρχικού design.
_LEADER_PAL = [
    ("linear-gradient(90deg,#14796A,#1C9384)", "#fff"),
    ("#3C9285", "#fff"), ("#5CA89B", "#fff"), ("#82B6AB", "#fff"),
    ("#82B6AB", "#fff"), ("#A6C7BE", "#224A41"), ("#A6C7BE", "#224A41"),
    ("#C2D6CF", "#224A41"), ("#C2D6CF", "#224A41"), ("#E2542C", "#fff"),
]
_CAT_PAL = [
    ("linear-gradient(90deg,#E2542C,#E8772E)", "#fff"),
    ("#E56A33", "#fff"), ("#E8772E", "#fff"), ("#ED8B2C", "#fff"),
    ("#ED8B2C", "#fff"), ("#EBA22A", "#6B3410"), ("#EBA22A", "#6B3410"),
    ("#EBA22A", "#6B3410"), ("#EDB257", "#6B3410"), ("#EDB257", "#6B3410"),
]
_PL_PAL = ["#2E8C9A", "#4A9DA9", "#4A9DA9", "#4A9DA9", "#6BAFB8", "#6BAFB8",
           "#6BAFB8", "#8FC2C9", "#8FC2C9", "#8FC2C9"]


def _esc(s):
    return html.escape(str(s))


def _date_long(iso, upper=False):
    """'2026-06-24' -> '24 Ιουνίου 2026' (ή κεφαλαία)."""
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        month = (_MONTHS_UP if upper else _MONTHS)[m - 1]
        return f"{d} {month} {y}"
    except (ValueError, IndexError):
        return _esc(iso)


def _int(n):
    """8164 -> '8.164' (τελεία για χιλιάδες, ελληνικά)."""
    return f"{int(round(n)):,}".replace(",", ".")


def _eur(v):
    """3.99 -> '€3,99'."""
    return "€" + f"{v:.2f}".replace(".", ",")


def _pct_signed(p):
    """Ποσοστό με πρόσημο και ελληνικό/τυπογραφικό μείον."""
    p = round(p)
    return (f"+{p}%" if p > 0 else f"−{abs(p)}%") if p else "0%"


def _emoji(cat):
    e = _EMOJI.get(cat)
    return f"{e} " if e else ""


def _cat_label(cat):
    return _emoji(cat) + _esc(cat)


# ─────────────────────────── building blocks ────────────────────────────

def _leader_rows(rows):
    if not rows:
        return ""
    top = max(r["win_pct"] for r in rows) or 1
    out = []
    for i, r in enumerate(rows):
        fill, txt = _LEADER_PAL[min(i, len(_LEADER_PAL) - 1)]
        width = max(r["win_pct"] / top * 100, 8)
        medal = "<span>🥇</span>" if i == 0 else ""
        name_weight = 800 if i == 0 else 700
        prem_color = "#14796A" if i == 0 else (
            "#E2542C" if i == len(rows) - 1 else "#7C8077")
        pad = ("display:flex; align-items:center; padding-left:12px;"
               if r["win_pct"] / top * 100 >= 16 else
               "display:flex; align-items:center; justify-content:flex-end;"
               " padding-right:8px;")
        out.append(
            '<div style="display:flex; align-items:center; gap:12px;">'
            f'<div style="width:118px; flex:none; font-weight:{name_weight};'
            ' font-size:13.5px; display:flex; align-items:center; gap:6px;">'
            f'{medal}{_esc(r["name"])}</div>'
            '<div style="flex:1; background:#E6DDC6; border-radius:999px;'
            ' height:24px; position:relative;">'
            f'<div style="width:{width:.1f}%; height:100%; background:{fill};'
            f' border-radius:999px; {pad}">'
            "<span style=\"font-family:'Nunito',sans-serif; font-weight:900;"
            f' color:{txt}; font-size:13px;">{r["win_pct"]}%</span></div></div>'
            '<div style="width:54px; flex:none; text-align:right;'
            " font-family:'Nunito',sans-serif; font-weight:800; font-size:13px;"
            f' color:{prem_color};">+{r["premium"]}%</div></div>')
    return "\n".join(out)


def _category_rows(cats):
    if not cats:
        return ""
    top = max(c["pct"] for c in cats) or 1
    out = []
    for i, c in enumerate(cats):
        fill, txt = _CAT_PAL[min(i, len(_CAT_PAL) - 1)]
        width = max(c["pct"] / top * 100, 8)
        weight = 800 if i == 0 else 700
        out.append(
            '<div style="display:flex; align-items:center; gap:12px;">'
            f'<div style="width:150px; flex:none; font-weight:{weight};'
            f' font-size:13.5px;">{_cat_label(c["cat"])}</div>'
            '<div style="flex:1; background:#F0E2D4; border-radius:999px;'
            ' height:24px;">'
            f'<div style="width:{width:.1f}%; height:100%; background:{fill};'
            ' border-radius:999px; display:flex; align-items:center;'
            ' padding-left:12px;">'
            "<span style=\"font-family:'Nunito',sans-serif; font-weight:900;"
            f' color:{txt}; font-size:13px;">{c["pct"]}%</span></div></div>'
            '<div style="width:44px; flex:none; text-align:right;'
            f' font-weight:800; font-size:13px; color:#8A8472;">{c["count"]}'
            "</div></div>")
    return "\n".join(out)


def _private_label_rows(rows):
    out = []
    for i, r in enumerate(rows):
        fill = _PL_PAL[min(i, len(_PL_PAL) - 1)]
        width = max(min(r["save_pct"], 100), 6)
        out.append(
            '<div style="display:flex; align-items:center; gap:10px;">'
            f'<div style="width:118px; flex:none; font-weight:700;'
            f' font-size:13px;">{_cat_label(r["cat"])}</div>'
            '<div style="flex:1; background:#E2EFE9; border-radius:999px;'
            ' height:20px;">'
            f'<div style="width:{width:.1f}%; height:100%; background:{fill};'
            ' border-radius:999px;"></div></div>'
            '<div style="width:38px; flex:none; text-align:right;'
            " font-family:'Nunito',sans-serif; font-weight:900; font-size:13px;"
            f' color:#1F6F7C;">{r["save_pct"]}%</div></div>')
    return "\n".join(out)


def _gve_list(rows, color):
    out = []
    for r in rows:
        unit = _esc(r["unit"] or "μον.")
        out.append(
            '<div style="background:#FBF4E6; border:1.5px solid #DECFB0;'
            ' border-radius:12px; padding:10px 12px;">'
            '<div style="font-size:12px; font-weight:700; line-height:1.3;">'
            f'{_esc(r["name"])}</div>'
            '<div style="display:flex; justify-content:space-between;'
            ' align-items:center; margin-top:6px; font-size:11.5px;">'
            f'<span style="color:#7C8077;">{_eur(r["gm"])}/{unit} '
            f'<span style="color:#BBB3A1;">vs</span> {_eur(r["em"])}/{unit}</span>'
            "<span style=\"font-family:'Nunito',sans-serif; font-weight:900;"
            f' color:{color};">{_pct_signed(r["pct"])}</span></div></div>')
    return "\n".join(out)


def _spread_rows(rows):
    out = []
    for r in rows:
        # Πλάτος μπάρας = πόσο μικρή είναι η φθηνή τιμή ως προς την ακριβή.
        width = max(r["lo"] / r["hi"] * 100, 4) if r["hi"] else 100
        out.append(
            '<div style="background:#FBF4E6; border:2px solid #DECFB0;'
            ' border-radius:14px; padding:13px 16px;">'
            '<div style="display:flex; justify-content:space-between;'
            ' align-items:baseline; gap:10px;">'
            '<div style="font-size:13px; font-weight:700; line-height:1.25;">'
            f'{_esc(r["name"])}</div>'
            "<div style=\"font-family:'Nunito',sans-serif; font-weight:900;"
            f' font-size:16px; color:#E2542C; flex:none;">+{r["pct"]}%</div></div>'
            '<div style="display:flex; align-items:center; gap:0; margin-top:9px;'
            ' height:18px; border-radius:999px; overflow:hidden;'
            ' background:#F3E6DC;">'
            f'<div style="width:{width:.1f}%; height:100%; background:#14796A;">'
            "</div></div>"
            '<div style="display:flex; justify-content:space-between;'
            ' margin-top:6px; font-size:11.5px; font-weight:700;">'
            f'<span style="color:#14796A;">{_eur(r["lo"])} · {_esc(r["lo_chain"])}'
            "</span>"
            f'<span style="color:#E2542C;">{_eur(r["hi"])} · {_esc(r["hi_chain"])}'
            "</span></div></div>")
    return "\n".join(out)


# ───────────────────────────── page render ──────────────────────────────

def render(d):
    date_badge = _date_long(d["date"], upper=True)
    date_foot = _date_long(d["date"])
    lb = d["leaderboard"]
    cats = d["categories"]
    pl = d["private_label"]
    gve = d["gve"]
    spread = d["spread"]

    # Σύνδεσμος στο ακριβές στιγμιότυπο δεδομένων που χρησιμοποιήθηκε (αναπαραγωγή).
    src_path = d.get("source_path")
    snapshot_link = (
        f' · <a href="{REPO_URL}/blob/main/{_esc(src_path)}"'
        ' style="color:#14796A; font-weight:700;">δεδομένα στιγμιότυπου</a>'
        if src_path else "")

    top_cat = cats[0] if cats else {"cat": "—", "pct": 0}
    top_pl = pl[0] if pl else {"cat": "—", "save_pct": 0}
    top_spread = spread[0] if spread else None
    eu_n = gve["n"]
    # «Προϊόντα σε ≥2 αλυσίδες» = contested· «συγκρίσιμα με Ευρώπη» = gve n.
    contested = lb["contested"]

    median = gve["median"]
    if median < 0:
        gve_word, gve_color = "ελαφρώς φθηνότερη", "#14796A"
        gve_dir = "λίγο φθηνότερα"
    elif median > 0:
        gve_word, gve_color = "ελαφρώς ακριβότερη", "#E2542C"
        gve_dir = "λίγο ακριβότερα"
    else:
        gve_word, gve_color = "περίπου στα ίδια", "#8A7A56"
        gve_dir = "ουσιαστικά ίδια"

    spread_factor = f"{top_spread['pct'] / 100 + 1:.1f}".replace(".", ",") \
        if top_spread else "—"

    if top_spread:
        s4_para = (
            f'Πρωταθλητής σήμερα: {_esc(top_spread["name"])} — '
            f'<b>{_eur(top_spread["lo"])}</b> στο {_esc(top_spread["lo_chain"])}, '
            f'<b>{_eur(top_spread["hi"])}</b> στο {_esc(top_spread["hi_chain"])} — '
            f'διαφορά <b>+{top_spread["pct"]}%</b> για πανομοιότυπο προϊόν.')
    else:
        s4_para = "Δεν βρέθηκαν αρκετά συγκρίσιμα προϊόντα σήμερα."

    return f"""<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Παρατηρητήριο Τιμών · Καθημερινή Ανάλυση — {_esc(date_foot)}</title>
<meta name="description" content="Καθημερινή ανάλυση τιμών από το ελληνικό Παρατηρητήριο Τιμών: ποιο σούπερ μάρκετ είναι φθηνότερο, πού αξίζει η σύγκριση, Ελλάδα vs Ευρώπη και ιδιωτική ετικέτα.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Mulish:wght@400;500;600;700;800&family=Nunito:wght@600;700;800;900&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #E8DCC4; font-family: 'Mulish', sans-serif; color: #232826; -webkit-font-smoothing: antialiased; }}
  .doc {{ box-sizing: border-box; max-width: 8.5in; margin: 0 auto; background: #FBF4E6; padding: 0 0 0.9in 0; box-shadow: 0 24px 60px rgba(20,30,25,.14); }}
  .pad {{ padding: 0 0.7in; }}
  h1, h2, h3 {{ text-wrap: balance; margin: 0; }}
  p, li {{ text-wrap: pretty; }}
  @page {{ size: letter; margin: 0; }}
  @media print {{
    html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    html, body {{ margin: 0; padding: 0; background: #fff; }}
    .doc {{ max-width: none !important; margin: 0 !important; box-shadow: none !important; }}
    h2, h3 {{ break-after: avoid; }}
    .keep, figure, tr {{ break-inside: avoid; }}
    .screen-only {{ display: none !important; }}
  }}
</style>
</head>
<body>
<main class="doc">
  <div class="screen-only" style="position:fixed; right:18px; bottom:18px; z-index:50;">
    <button onclick="window.print()" style="font-family:'Nunito',sans-serif; font-weight:800; font-size:14px; color:#fff; background:#14796A; border:none; border-radius:999px; padding:12px 20px; box-shadow:0 8px 20px rgba(21,160,107,.4); cursor:pointer;">⬇︎ Εκτύπωση / PDF</button>
  </div>

  <!-- ============ HERO ============ -->
  <header style="position:relative; overflow:hidden; background:#14796A; color:#FBF4E6; padding:46px 0.7in 38px;">
    <div style="position:absolute; right:-60px; top:-60px; width:240px; height:240px; border-radius:50%; background:#178577;"></div>
    <div style="position:absolute; right:70px; bottom:-90px; width:170px; height:170px; border-radius:50%; background:#E8A33C; opacity:.9;"></div>
    <div style="position:relative;">
      <div style="display:inline-flex; align-items:center; gap:8px; background:rgba(255,252,244,.16); border:1.5px solid rgba(255,252,244,.4); padding:6px 14px; border-radius:999px; font-family:'Nunito',sans-serif; font-weight:800; font-size:12.5px; letter-spacing:.04em;">🛒 ΚΑΘΗΜΕΡΙΝΗ ΕΡΕΥΝΑ ΤΙΜΩΝ · {_esc(date_badge)}</div>
      <h1 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:46px; line-height:1.04; letter-spacing:-.01em; margin:18px 0 0; max-width:8.3in;">Τι κρύβουν οι τιμές<br>των σούπερ μάρκετ;</h1>
      <p style="font-size:16px; line-height:1.55; max-width:5.6in; margin:16px 0 0; color:#FBEFE0;">Κάθε μέρα κατεβάζουμε ολόκληρο τον κατάλογο του Παρατηρητηρίου Τιμών και ψάχνουμε τις πιο ενδιαφέρουσες ιστορίες που κρύβονται στους αριθμούς. Να τι βρήκαμε σήμερα.</p>
    </div>
  </header>

  <!-- stat strip -->
  <div class="pad keep" style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:-22px; position:relative;">
    <div style="background:#FBF4E6; border:2px solid #DECFB0; border-radius:16px; padding:16px 14px; box-shadow:0 8px 20px rgba(30,40,30,.06);">
      <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:28px; color:#14796A; line-height:1;">{_int(d["total"])}</div>
      <div style="font-size:12.5px; font-weight:700; color:#6B7370; margin-top:5px;">προϊόντα στον κατάλογο</div>
    </div>
    <div style="background:#FBF4E6; border:2px solid #DECFB0; border-radius:16px; padding:16px 14px; box-shadow:0 8px 20px rgba(30,40,30,.06);">
      <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:28px; color:#E2542C; line-height:1;">{_int(d["n_gr"])}</div>
      <div style="font-size:12.5px; font-weight:700; color:#6B7370; margin-top:5px;">ελληνικά σούπερ μάρκετ</div>
    </div>
    <div style="background:#FBF4E6; border:2px solid #DECFB0; border-radius:16px; padding:16px 14px; box-shadow:0 8px 20px rgba(30,40,30,.06);">
      <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:28px; color:#B06A1F; line-height:1;">{_int(contested)}</div>
      <div style="font-size:12.5px; font-weight:700; color:#6B7370; margin-top:5px;">προϊόντα σε ≥2 αλυσίδες</div>
    </div>
    <div style="background:#FBF4E6; border:2px solid #DECFB0; border-radius:16px; padding:16px 14px; box-shadow:0 8px 20px rgba(30,40,30,.06);">
      <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:28px; color:#7A4E8C; line-height:1;">{_int(eu_n)}</div>
      <div style="font-size:12.5px; font-weight:700; color:#6B7370; margin-top:5px;">συγκρίσιμα με Ευρώπη</div>
    </div>
  </div>
  <p class="pad" style="font-size:11.5px; color:#9A9384; margin:14px 0 0; font-style:italic;">Πηγή δεδομένων: <a href="{SOURCE_URL}" style="color:#7C8077; font-weight:700;">Παρατηρητήριο Τιμών</a>. Οι συγκρίσεις αφορούν μόνο ελληνικές αλυσίδες και έχουν καθαριστεί από λάθη του Παρατηρητηρίου (τιμές μονάδας λανθασμένα συνδεδεμένες με πολυσυσκευασίες).</p>

  <!-- ============ SECTION 1 — CHEAPEST RANKING ============ -->
  <section class="pad" style="margin-top:40px;">
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-family:'Nunito',sans-serif; font-weight:900; font-size:13px; color:#fff; background:#14796A; border-radius:8px; padding:4px 10px;">01</span>
      <span style="font-family:'Nunito',sans-serif; font-weight:800; font-size:13px; color:#14796A; letter-spacing:.04em;">ΠΟΙΟ ΕΙΝΑΙ ΤΟ ΦΘΗΝΟΤΕΡΟ;</span>
    </div>
    <h2 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:30px; line-height:1.08; margin:10px 0 0; max-width:6.6in;">Πιο συχνά φθηνότερο βγαίνει το <span style="color:#14796A;">{_esc(lb["best_name"])}</span></h2>
    <p style="font-size:15px; line-height:1.6; color:#454B48; max-width:6.4in; margin:10px 0 0;">Συγκρίναμε <b>{_int(contested)}</b> προϊόντα που πωλούνται σε τουλάχιστον δύο ελληνικές αλυσίδες. Το {_esc(lb["best_name"])} έχει την καλύτερη τιμή στο <b>{lb["best_pct"]}%</b> των περιπτώσεων. Στο άλλο άκρο, το {_esc(lb["worst_name"])} σπανιότερα βγαίνει το φθηνότερο: αν αγόραζες όλο το καλάθι εκεί θα πλήρωνες κατά μέσο όρο <b>+{lb["worst_premium"]}%</b> σε σχέση με το να έπαιρνες κάθε προϊόν εκεί που είναι φθηνότερο.</p>

    <figure class="keep" style="margin:22px 0 0; background:#FBF4E6; border:2px solid #DECFB0; border-radius:18px; padding:20px 22px;">
      <div style="display:flex; justify-content:space-between; font-family:'Nunito',sans-serif; font-weight:800; font-size:11.5px; color:#8A8472; letter-spacing:.03em; margin-bottom:14px;">
        <span>ΣΟΥΠΕΡ ΜΑΡΚΕΤ · ΦΟΡΕΣ ΦΘΗΝΟΤΕΡΟ</span><span>ΜΕΣΗ ΕΠΙΒΑΡΥΝΣΗ</span>
      </div>
      <div style="display:flex; flex-direction:column; gap:11px;">
        {_leader_rows(lb["rows"])}
      </div>
      <figcaption style="font-size:11.5px; color:#9A9384; margin-top:14px;">«Φορές φθηνότερο» = ποσοστό προϊόντων όπου η αλυσίδα έχει τη χαμηλότερη τιμή. «Μέση επιβάρυνση» = πόσο παραπάνω πληρώνεις κατά μέσο όρο σε σχέση με το φθηνότερο. Κάθε αλυσίδα μετριέται μόνο στα προϊόντα που πράγματι διαθέτει.</figcaption>
    </figure>
  </section>

  <!-- ============ SECTION 2 — SHOP AROUND ============ -->
  <section class="pad" style="margin-top:44px;">
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-family:'Nunito',sans-serif; font-weight:900; font-size:13px; color:#fff; background:#E2542C; border-radius:8px; padding:4px 10px;">02</span>
      <span style="font-family:'Nunito',sans-serif; font-weight:800; font-size:13px; color:#E2542C; letter-spacing:.04em;">ΠΟΥ ΑΞΙΖΕΙ ΝΑ ΨΑΞΕΙΣ</span>
    </div>
    <h2 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:30px; line-height:1.08; margin:10px 0 0; max-width:6.6in;">Μεγαλύτερη διαφορά τιμής: «<span style="color:#E2542C;">{_esc(top_cat["cat"])}</span>»</h2>
    <p style="font-size:15px; line-height:1.6; color:#454B48; max-width:6.4in; margin:10px 0 0;">Σε κάποιες κατηγορίες η τιμή για το ίδιο πράγμα αλλάζει δραματικά από μαγαζί σε μαγαζί. Πρωταθλητής η κατηγορία «{_esc(top_cat["cat"])}», όπου η μέση διαφορά τιμής μεταξύ καταστημάτων αγγίζει το <b>{top_cat["pct"]}%</b>.</p>

    <figure class="keep" style="margin:22px 0 0; background:#FBF4E6; border:2px solid #DECFB0; border-radius:18px; padding:20px 22px;">
      <div style="display:flex; justify-content:space-between; font-family:'Nunito',sans-serif; font-weight:800; font-size:11.5px; color:#8A8472; letter-spacing:.03em; margin-bottom:14px;">
        <span>ΚΑΤΗΓΟΡΙΑ · ΜΕΣΗ ΔΙΑΦΟΡΑ ΜΕΤΑΞΥ ΜΑΓΑΖΙΩΝ</span><span>ΠΡΟΪΟΝΤΑ</span>
      </div>
      <div style="display:flex; flex-direction:column; gap:11px;">
        {_category_rows(cats)}
      </div>
    </figure>
  </section>

  <!-- ============ SECTION 3 — GREECE vs EUROPE ============ -->
  <section class="pad" style="margin-top:44px;">
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-family:'Nunito',sans-serif; font-weight:900; font-size:13px; color:#fff; background:#7A4E8C; border-radius:8px; padding:4px 10px;">03</span>
      <span style="font-family:'Nunito',sans-serif; font-weight:800; font-size:13px; color:#7A4E8C; letter-spacing:.04em;">🇬🇷 ΕΛΛΑΔΑ vs ΕΥΡΩΠΗ 🇪🇺</span>
    </div>
    <h2 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:30px; line-height:1.08; margin:10px 0 0; max-width:6.6in;">Η Ελλάδα βγαίνει <span style="color:{gve_color};">{gve_word}</span> — με μεγάλες ακρότητες</h2>
    <p style="font-size:15px; line-height:1.6; color:#454B48; max-width:6.5in; margin:10px 0 0;">Συγκρίναμε <b>{_int(eu_n)}</b> προϊόντα που πωλούνται και στην Ελλάδα και σε τουλάχιστον δύο άλλες ευρωπαϊκές χώρες, <b>ανά μονάδα</b> (κιλό ή λίτρο). Η διάμεση διαφορά είναι <b>{_pct_signed(median)}</b>: {gve_dir} εδώ. Όμως οι ακρότητες είναι έντονες.</p>

    <figure class="keep" style="margin:20px 0 0; background:#FBF4E6; border:2px solid #DECFB0; border-radius:18px; padding:20px 22px;">
      <div style="display:flex; height:46px; border-radius:12px; overflow:hidden; font-family:'Nunito',sans-serif; font-weight:900; color:#fff;">
        <div style="width:{gve["cheaper_pct"]}%; background:#14796A; display:flex; align-items:center; justify-content:center; font-size:15px;">{gve["cheaper_pct"]}%</div>
        <div style="width:{gve["similar_pct"]}%; background:#C9B894; display:flex; align-items:center; justify-content:center; font-size:11px; color:#5C4A2E;">{gve["similar_pct"]}%</div>
        <div style="width:{gve["pricier_pct"]}%; background:#E2542C; display:flex; align-items:center; justify-content:center; font-size:15px;">{gve["pricier_pct"]}%</div>
      </div>
      <div style="display:flex; justify-content:space-between; margin-top:10px; font-size:12.5px; font-weight:700;">
        <span style="color:#14796A;">◄ Φθηνότερα στην Ελλάδα ({_int(gve["cheaper"])})</span>
        <span style="color:#8A7A56;">ίδια ({_int(gve["similar"])})</span>
        <span style="color:#E2542C;">Ακριβότερα στην Ελλάδα ({_int(gve["pricier"])}) ►</span>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:18px;">
        <div style="background:#E2F0EA; border-radius:12px; padding:14px 16px;">
          <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:24px; color:#14796A; line-height:1;">{_int(gve["much_ch"])} <span style="font-size:14px;">προϊόντα · {gve["much_ch_pct"]}%</span></div>
          <div style="font-size:12.5px; font-weight:700; color:#2E5C52; margin-top:5px;">πάνω από 20% φθηνότερα εδώ</div>
        </div>
        <div style="background:#F6E7DF; border-radius:12px; padding:14px 16px;">
          <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:24px; color:#E2542C; line-height:1;">{_int(gve["much_pr"])} <span style="font-size:14px;">προϊόντα · {gve["much_pr_pct"]}%</span></div>
          <div style="font-size:12.5px; font-weight:700; color:#9C3415; margin-top:5px;">πάνω από 20% ακριβότερα εδώ</div>
        </div>
      </div>
    </figure>

    <div class="keep" style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:16px;">
      <div>
        <h3 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:15px; color:#14796A; margin-bottom:10px;">💚 Πολύ φθηνότερα στην Ελλάδα</h3>
        <div style="display:flex; flex-direction:column; gap:8px;">
          {_gve_list(gve["cheap_rows"][:4], "#14796A")}
        </div>
      </div>
      <div>
        <h3 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:15px; color:#E2542C; margin-bottom:10px;">❤️ Πολύ ακριβότερα στην Ελλάδα</h3>
        <div style="display:flex; flex-direction:column; gap:8px;">
          {_gve_list(gve["pricey_rows"][:4], "#E2542C")}
        </div>
      </div>
    </div>
  </section>

  <!-- ============ SECTION 4 — SAME PRODUCT SPREAD ============ -->
  <section class="pad" style="margin-top:44px;">
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-family:'Nunito',sans-serif; font-weight:900; font-size:13px; color:#fff; background:#B06A1F; border-radius:8px; padding:4px 10px;">04</span>
      <span style="font-family:'Nunito',sans-serif; font-weight:800; font-size:13px; color:#8A5114; letter-spacing:.04em;">ΙΔΙΟ ΠΡΟΪΟΝ, ΑΛΛΗ ΤΙΜΗ</span>
    </div>
    <h2 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:30px; line-height:1.08; margin:10px 0 0; max-width:6.6in;">Το ίδιο προϊόν, έως και <span style="color:#E2542C;">{spread_factor} φορές</span> πιο ακριβό</h2>
    <p style="font-size:15px; line-height:1.6; color:#454B48; max-width:6.5in; margin:10px 0 0;">{s4_para}</p>

    <div class="keep" style="margin-top:18px; display:flex; flex-direction:column; gap:10px;">
      {_spread_rows(spread)}
    </div>
  </section>

  <!-- ============ SECTION 5 — PRIVATE LABEL ============ -->
  <section class="pad" style="margin-top:44px;">
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-family:'Nunito',sans-serif; font-weight:900; font-size:13px; color:#fff; background:#2E8C9A; border-radius:8px; padding:4px 10px;">05</span>
      <span style="font-family:'Nunito',sans-serif; font-weight:800; font-size:13px; color:#1F6F7C; letter-spacing:.04em;">ΕΠΩΝΥΜΟ ή ΙΔΙΩΤΙΚΗ ΕΤΙΚΕΤΑ;</span>
    </div>
    <h2 style="font-family:'Nunito',sans-serif; font-weight:900; font-size:30px; line-height:1.08; margin:10px 0 0; max-width:6.6in;">Με το προϊόν του σούπερ μάρκετ γλιτώνεις <span style="color:#2E8C9A;">έως {top_pl["save_pct"]}%</span></h2>
    <p style="font-size:15px; line-height:1.6; color:#454B48; max-width:6.5in; margin:10px 0 0;">Τα προϊόντα ιδιωτικής ετικέτας κοστίζουν σταθερά πολύ λιγότερο ανά μονάδα από τα επώνυμα. Η μεγαλύτερη διαφορά είναι στην κατηγορία <b>{_esc(top_pl["cat"])}</b>.</p>

    <figure class="keep" style="margin:18px 0 0; background:#FBF4E6; border:2px solid #DECFB0; border-radius:18px; padding:18px 22px;">
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px 26px;">
        {_private_label_rows(pl)}
      </div>
      <figcaption style="font-size:11.5px; color:#9A9384; margin-top:14px;">Ποσοστό που γλιτώνεις ανά μονάδα (κιλό/λίτρο/τεμάχιο) επιλέγοντας το προϊόν ιδιωτικής ετικέτας αντί για το επώνυμο.</figcaption>
    </figure>
  </section>

  <!-- ============ FOOTER ============ -->
  <footer class="pad" style="margin-top:46px;">
    <div style="border-top:2px dashed #C9B894; padding-top:18px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
      <div style="font-family:'Nunito',sans-serif; font-weight:900; font-size:15px; color:#14796A;">🛒 Παρατηρητήριο Τιμών · Καθημερινή Ανάλυση</div>
      <div style="font-size:11.5px; color:#9A9384;">Στιγμιότυπο {_esc(date_foot)}</div>
    </div>
    <div style="font-size:11.5px; color:#9A9384; line-height:1.85; margin-top:12px;">
      <b style="color:#7C8077;">Πηγές &amp; μεθοδολογία.</b>
      Δεδομένα: επίσημο <a href="{SOURCE_URL}" style="color:#14796A; font-weight:700;">Παρατηρητήριο Τιμών (posokanei.gov.gr)</a>{snapshot_link}.
      Ανοιχτός κώδικας: <a href="{REPO_URL}/blob/main/stats.py" style="color:#14796A; font-weight:700;">stats.py</a> (υπολογισμοί) ·
      <a href="{REPO_URL}/blob/main/report.py" style="color:#14796A; font-weight:700;">report.py</a> (αυτή η σελίδα) ·
      <a href="{REPO_URL}" style="color:#14796A; font-weight:700;">όλο το αποθετήριο &amp; τα ημερήσια στιγμιότυπα στο GitHub</a>.
      Όλες οι συγκρίσεις είναι ανά μονάδα όπου χρειάζεται και καθαρισμένες από προφανή σφάλματα τιμών.
    </div>
  </footer>
</main>
</body>
</html>
"""


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
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render(_DEMO))
    print(f"wrote {OUT_DIR}/index.html (demo data)")
