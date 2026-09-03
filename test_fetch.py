#!/usr/bin/env python3
"""Offline checks for fetch.py's truncation detection and category partitioning.

Runs against real archived snapshots, so it needs no network:
  python test_fetch.py
"""

import contextlib
import http.client
import io
import json
import os
import ssl
import unittest
import urllib.error
import urllib.parse

import fetch

DATA = os.path.join("data", "2026")


def snapshot(date):
    with open(os.path.join(DATA, f"posokanei-{date}.json"), encoding="utf-8") as fh:
        return json.load(fh)


class ExpectedTotal(unittest.TestCase):
    """The category metadata gives a catalogue count the 10k cap can't hide."""

    def test_matches_collected_before_the_cap_was_hit(self):
        snap = snapshot("2026-07-29")
        # 9818 vs 9820 collected: the two agree to within normal drift while
        # the catalogue was still under the API's 10k result window.
        self.assertAlmostEqual(
            fetch.expected_total(snap["categories"]), snap["collected"], delta=10
        )

    def test_detects_truncation_once_the_catalogue_passed_10k(self):
        snap = snapshot("2026-08-06")
        self.assertEqual(snap["collected"], 10000)
        self.assertEqual(fetch.expected_total(snap["categories"]), 10489)

    def test_root_categories_partition_the_catalogue_under_the_cap(self):
        snap = snapshot("2026-08-06")
        roots = fetch.root_categories(snap["categories"])
        self.assertEqual(len(roots), 39)
        self.assertLess(max(c["product_count"] for c in roots), fetch.RESULT_WINDOW)


class CategoryFilterDetection(unittest.TestCase):
    """The probe must reject a parameter the API silently ignores."""

    def setUp(self):
        self.snap = snapshot("2026-08-06")
        self.products = self.snap["products"]
        roots = fetch.root_categories(self.snap["categories"])
        self.cid = max(roots, key=lambda c: c["product_count"])["category_id"]

    def test_accepts_a_genuinely_filtered_page(self):
        page = [p for p in self.products if self.cid in p["category_ids"]][:100]
        self.assertTrue(fetch.filters_by_category(page, self.cid))

    def test_rejects_an_unfiltered_page(self):
        # What the API returns when it does not recognise the parameter.
        self.assertFalse(fetch.filters_by_category(self.products[:100], self.cid))

    def test_rejects_an_empty_or_too_small_page(self):
        self.assertFalse(fetch.filters_by_category([], self.cid))


class FakeAPI:
    """A /products endpoint that pages, filters by category, and clamps.

    Serves the real 2026-08-06 catalogue behind a deliberately small result
    window, so a flat crawl truncates exactly the way the live API does.
    """

    def __init__(self, products, window, param="category_ids"):
        self.products = products
        self.window = window
        self.param = param
        self.calls = 0

    def get_json(self, path, retries=None):
        self.calls += 1
        query = dict(urllib.parse.parse_qsl(path.split("?", 1)[1]))
        rows = self.products
        if self.param in query:
            cid = query[self.param]
            rows = [p for p in rows if cid in (p.get("category_ids") or [])]
        elif any(c in query for c in fetch.CATEGORY_PARAM_CANDIDATES):
            pass  # unrecognised filter: silently ignored, as the real API does

        total = min(len(rows), self.window)
        size = int(query["page_size"])
        page = int(query["page"])
        start = (page - 1) * size
        return {
            "total": total,
            "total_pages": max(1, -(-total // size)),
            "products": rows[start:min(start + size, self.window)],
        }


class PartitionedCrawl(unittest.TestCase):
    def setUp(self):
        snap = snapshot("2026-08-06")
        self.categories = snap["categories"]
        self.products = snap["products"]
        self._saved = (fetch.get_json, fetch.PER_PAGE_DELAY, fetch.RESULT_WINDOW)
        fetch.PER_PAGE_DELAY = 0

    def tearDown(self):
        fetch.get_json, fetch.PER_PAGE_DELAY, fetch.RESULT_WINDOW = self._saved

    def install(self, api):
        """Point fetch at the fake, with its window as the real one."""
        fetch.get_json = api.get_json
        fetch.RESULT_WINDOW = api.window
        return api

    def test_recovers_the_whole_catalogue_a_flat_crawl_would_truncate(self):
        api = self.install(FakeAPI(self.products, window=2000))

        flat = api.get_json("/products?page=1&page_size=100")
        self.assertEqual(flat["total"], 2000)  # a flat crawl sees only the cap

        total, got = fetch.fetch_all_products(self.categories)
        self.assertEqual(len(got), len(self.products))
        self.assertEqual(len({p["id"] for p in got}), len(self.products))
        self.assertEqual(total, fetch.expected_total(self.categories))

    def test_detects_the_parameter_the_api_actually_honours(self):
        self.install(FakeAPI(self.products, window=2000, param="category_id"))
        self.assertEqual(fetch.detect_category_param(self.categories), "category_id")

    def test_warns_when_a_single_category_outgrows_the_window(self):
        # The clamp means an oversized category reports exactly the window,
        # never more — so the guard has to trigger on equality.
        api = self.install(FakeAPI(self.products, window=100))
        cat = max(fetch.root_categories(self.categories),
                  key=lambda c: c["product_count"])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            fetch.fetch_category("category_ids", cat, {})
        self.assertIn("needs splitting by subcategory", err.getvalue())

    def test_aborts_when_no_parameter_filters(self):
        self.install(FakeAPI(self.products, window=2000, param="nope"))
        with self.assertRaises(RuntimeError) as ctx:
            fetch.fetch_all_products(self.categories)
        self.assertIn("silently drop", str(ctx.exception))


class FakeResponse:
    """Just enough of an http.client response for get_json's `with` block."""

    def __init__(self, body=b"", error=None):
        self.body, self.error = body, error

    def read(self):
        if self.error is not None:
            raise self.error
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class GetJsonRetries(unittest.TestCase):
    """Transient failures must be retried, not allowed to abort the crawl.

    urllib wraps only what fails while the connection is being opened; a
    failure part-way through the body arrives as its raw http.client or socket
    exception. The 2026-09-03 snapshot died on one such error 27 categories in,
    so every transient shape is pinned here.
    """

    def setUp(self):
        self._saved = (fetch.urllib.request.urlopen, fetch.time.sleep,
                       fetch.RETRY_BACKOFF)
        fetch.time.sleep = lambda _s: None
        fetch.RETRY_BACKOFF = 0

    def tearDown(self):
        fetch.urllib.request.urlopen, fetch.time.sleep, fetch.RETRY_BACKOFF = (
            self._saved)

    def install(self, *responses):
        """Serve `responses` in order, recording how many were consumed."""
        calls = []

        def urlopen(req, timeout=None):
            calls.append(req.full_url)
            return responses[min(len(calls) - 1, len(responses) - 1)]

        fetch.urllib.request.urlopen = urlopen
        return calls

    def transients(self):
        return [
            # What actually broke the 2026-09-03 run.
            http.client.IncompleteRead(b"", 45943),
            http.client.RemoteDisconnected("closed by remote"),
            http.client.BadStatusLine("garbage"),
            ConnectionResetError(104, "Connection reset by peer"),
            ssl.SSLError("read operation timed out"),
            TimeoutError("timed out"),
        ]

    def test_retries_every_transient_error_raised_while_reading_the_body(self):
        good = json.dumps({"ok": True}).encode("utf-8")
        for err in self.transients():
            with self.subTest(error=type(err).__name__):
                calls = self.install(FakeResponse(error=err),
                                     FakeResponse(body=good))
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(fetch.get_json("/x"), {"ok": True})
                self.assertEqual(len(calls), 2)

    def test_retries_a_body_that_is_not_valid_json(self):
        good = json.dumps({"ok": True}).encode("utf-8")
        calls = self.install(FakeResponse(body=b"<html>502</html>"),
                             FakeResponse(body=good))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fetch.get_json("/x"), {"ok": True})
        self.assertEqual(len(calls), 2)

    def test_retries_errors_raised_while_opening_the_connection(self):
        good = json.dumps({"ok": True}).encode("utf-8")
        opening = [urllib.error.URLError("no route to host"),
                   urllib.error.HTTPError("/x", 503, "Busy", {}, None)]
        for err in opening:
            with self.subTest(error=type(err).__name__):
                responses = [FakeResponse(body=good)]
                calls = []

                def urlopen(req, timeout=None, _e=err):
                    calls.append(req.full_url)
                    if len(calls) == 1:
                        raise _e
                    return responses[0]

                fetch.urllib.request.urlopen = urlopen
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(fetch.get_json("/x"), {"ok": True})
                self.assertEqual(len(calls), 2)

    def test_gives_up_after_the_retry_budget_and_names_the_cause(self):
        calls = self.install(
            FakeResponse(error=http.client.IncompleteRead(b"", 45943)))
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError) as ctx:
                fetch.get_json("/x", retries=3)
        self.assertEqual(len(calls), 3)
        self.assertIn("IncompleteRead", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
