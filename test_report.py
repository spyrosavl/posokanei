"""Check the data semantics and reusable charts without browser dependencies."""
import copy
import unittest
from xml.etree import ElementTree as ET

import report
import report_charts
import stats


class ReportTests(unittest.TestCase):
    def data(self):
        d = copy.deepcopy(report._DEMO)
        for row in d['leaderboard']['rows']:
            row['count'] = 100
        for row in d['private_label']:
            row['unit'] = 'kg'
        return d

    def test_ranking_counts_stocked_products_and_ties(self):
        products = [{'retailer_prices': [{'retailer': 1, 'price': 2},
                                         {'retailer': 2, 'price': 2}]} for _ in range(50)]
        products += [{'retailer_prices': [{'retailer': 1, 'price': 3},
                                          {'retailer': 3, 'price': 2}]} for _ in range(50)]
        result = stats.stat_leaderboard(products, {1, 2, 3}, {1: 'A', 2: 'B', 3: 'C'})
        rows = {r['name']: r for r in result['rows']}
        self.assertEqual((rows['A']['win_pct'], rows['A']['count']), (50, 100))
        self.assertEqual((rows['B']['win_pct'], rows['B']['count']), (100, 50))
        self.assertEqual(result['contested'], 100)

    def test_ranking_uses_absolute_percent_scale(self):
        svg = ET.fromstring(report_charts.render(self.data())['retailers.svg'])
        fills = [r for r in svg.iter('{http://www.w3.org/2000/svg}rect')
                 if r.get('fill') == report_charts.TEAL]
        self.assertAlmostEqual(float(fills[0].get('width')), 426 * .55)

    def test_europe_segments_use_counts_not_rounded_percentages(self):
        d = self.data()
        d['gve'].update(n=3, cheaper=1, similar=1, pricier=1,
                        cheaper_pct=33, similar_pct=33, pricier_pct=33)
        svg = ET.fromstring(report_charts.render(d)['europe.svg'])
        segments = [r for r in svg.iter('{http://www.w3.org/2000/svg}rect') if r.get('y') == '194']
        self.assertEqual(sum(float(r.get('width')) for r in segments), 552)

    def test_names_are_escaped_and_svg_is_valid(self):
        d = self.data()
        d['leaderboard']['rows'][0]['name'] = '<shop & "co">'
        d['spread'][0]['name'] = '<script>unsafe</script>'
        for svg in report_charts.render(d).values():
            ET.fromstring(svg)
        page = report.render(d)
        self.assertNotIn('<script>unsafe</script>', page)
        self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;', page)
        self.assertIn('width="600" height="', page)

    def test_empty_snapshot_has_no_claim_of_price_parity(self):
        d = self.data()
        d['leaderboard'] = stats.stat_leaderboard([], set(), {})
        d['categories'], d['spread'], d['private_label'] = [], [], []
        d['gve'] = stats.stat_greece_vs_europe([], set(), set())
        self.assertIn('Δεν υπάρχουν αρκετά δεδομένα', report.render(d))
        svg = report_charts.render(d)['europe.svg']
        ET.fromstring(svg)
        self.assertNotIn('>+0%</text>', svg)


if __name__ == '__main__':
    unittest.main()
