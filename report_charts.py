"""Dependency-free SVG charts shared by the report and GitHub README."""

import html
import math
import textwrap
from pathlib import Path

TEAL = "#127567"
ORANGE = "#bb4b28"
INK = "#183b35"
MUTED = "#536860"


def text(x, y, value, size=20, fill=INK, **attrs):
    extra = " ".join(f'{k.replace("_", "-")}="{html.escape(str(v))}"'
                     for k, v in attrs.items())
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>'
            f'{html.escape(str(value))}</text>')


def frame(title, date, body, height, notes):
    footer = height - len(notes) * 22 - 22
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="{height}" '
            f'viewBox="0 0 600 {height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{html.escape(title)} — {date}</title>'
            f'<desc id="desc">{html.escape(" ".join(notes))}</desc>'
            '<rect width="100%" height="100%" rx="16" fill="#fffdf8"/>'
            '<g font-family="Arial, sans-serif">'
            + text(24, 38, title, 24, font_weight=700)
            + text(24, 66, f'{date} · posokanei.gov.gr', 16, MUTED)
            + body
            + ''.join(text(24, footer + i * 22, line, 16, MUTED)
                      for i, line in enumerate(notes))
            + '</g></svg>')


def bars(title, date, rows, color, notes, maximum=100):
    body = ""
    y = 108
    for label, value, count in rows:
        lines = textwrap.wrap(label, 37)
        for line in lines:
            body += text(24, y, line, 22, font_weight=600)
            y += 26
        body += text(576, y - 26, f'{value}%', 24, color,
                     text_anchor="end", font_weight=700)
        body += (f'<rect x="24" y="{y - 12}" width="426" height="10" rx="5" fill="#e6ece7"/>'
                 f'<rect x="24" y="{y - 12}" width="{426 * value / maximum:.2f}" '
                 f'height="10" rx="5" fill="{color}"/>')
        body += text(576, y, f'n={count:,}'.replace(',', '.'), 16, MUTED, text_anchor="end")
        y += 30
    if not rows:
        body += text(24, y, 'Δεν υπάρχουν αρκετά συγκρίσιμα δεδομένα.', 20)
        y += 42
    body += text(24, y + 8, '0%', 16, MUTED)
    body += text(450, y + 8, f'{maximum}%', 16, MUTED, text_anchor="end")
    return frame(title, date, body, y + 70 + len(notes) * 22, notes)


def europe(date, gve):
    n = gve['n']
    body = text(24, 128, f'{gve["median"]:+d}%'.replace('-', '−') if n else '—',
                54, TEAL if gve['median'] <= 0 else ORANGE, font_weight=700)
    body += text(24, 164, 'διάμεση διαφορά τιμής στην Ελλάδα', 22)
    x = 24
    for count, color in [(gve['cheaper'], TEAL), (gve['similar'], '#a99b7a'),
                         (gve['pricier'], ORANGE)]:
        width = 552 * count / n if n else 0
        body += f'<rect x="{x:.3f}" y="194" width="{width:.3f}" height="36" fill="{color}"/>'
        x += width
    for i, (label, key, color) in enumerate([
        ('Φθηνότερα στην Ελλάδα', 'cheaper', TEAL),
        ('Παρόμοια τιμή (±2%)', 'similar', '#766847'),
        ('Ακριβότερα στην Ελλάδα', 'pricier', ORANGE),
    ]):
        y = 276 + i * 66
        body += f'<circle cx="32" cy="{y - 7}" r="7" fill="{color}"/>'
        body += text(52, y, label, 22)
        body += text(576, y, f'{gve[key + "_pct"]}%' if n else '—', 26,
                     color, text_anchor="end", font_weight=700)
        body += text(52, y + 24, f'{gve[key]} προϊόντα', 17, MUTED)
    return frame('Ελλάδα & Ευρώπη', date, body, 564, [
        f'{n} προϊόντα · τιμές ανά κιλό, λίτρο ή τεμάχιο.',
        'Διάμεσοι τιμών Ελλάδας / άλλων ευρωπαϊκών χωρών.',
        '≥2 ελληνικές τιμές και ≥2 άλλες χώρες ανά προϊόν.',
        'Το δείγμα δεν είναι δείκτης κόστους ζωής.',
    ])


def render(d):
    cats = d['categories']
    maximum = max(100, math.ceil(max((r['pct'] for r in cats), default=0) / 25) * 25)
    return {
        'retailers.svg': bars('Ποιος έχει συχνότερα τη χαμηλότερη τιμή;', d['date'],
            [(r['name'], r['win_pct'], r['count']) for r in d['leaderboard']['rows']],
            TEAL, ['Μερίδιο συγκρίσιμων προϊόντων κάθε αλυσίδας.',
                   'Οι ισοπαλίες μετρούν · n = προϊόντα που συγκρίθηκαν.',
                   'Διαφορετικό δείγμα ανά αλυσίδα · τουλάχιστον 50 προϊόντα.']),
        'categories.svg': bars('Πού διαφέρουν περισσότερο οι τιμές;', d['date'],
            [(r['cat'], r['pct'], r['count']) for r in cats], ORANGE,
            ['Μέση διαφορά (μέγιστη − ελάχιστη) / ελάχιστη τιμή.',
             '≥3 αλυσίδες ανά προϊόν · ≥30 προϊόντα ανά κατηγορία.',
             'Με φίλτρο ακραίων τιμών · n = προϊόντα στο δείγμα.'], maximum),
        'europe.svg': europe(d['date'], d['gve']),
    }


def write(d, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, svg in render(d).items():
        (directory / name).write_text(svg, encoding='utf-8')
