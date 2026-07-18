import unittest
from unittest.mock import Mock, patch

from citation.get_citation import (
    ScholarFetchError,
    build_payload,
    collect_serpapi_stats,
    extract_serpapi_remaining_credits,
    mark_fallback_payload,
    parse_serpapi_metrics,
    parse_serpapi_publications,
)


class CitationPayloadTests(unittest.TestCase):
    @patch("citation.get_citation.utc_now_iso", return_value="2026-07-14T04:18:03Z")
    def test_live_payload_records_fetch_time(self, _mock_now):
        payload = build_payload(
            user_id="8VCnj3sAAAAJ",
            hl="en",
            scholar_name="Haidong Xin",
            metrics={
                "citedby": 69,
                "citedby5y": 69,
                "hindex": 5,
                "hindex5y": 5,
                "i10index": 2,
                "i10index5y": 2,
            },
            publications={},
            source_backend="direct-html",
        )

        self.assertEqual(payload["citedby"], 69)
        self.assertEqual(payload["fetched_at"], "2026-07-14T04:18:03Z")
        self.assertEqual(payload["source_backend"], "direct-html")

    @patch("citation.get_citation.utc_now_iso", return_value="2026-07-14T04:49:57Z")
    def test_fallback_payload_is_explicitly_marked(self, _mock_now):
        original = {
            "user_id": "8VCnj3sAAAAJ",
            "citedby": 59,
            "publications": {},
            "source_backend": "direct-html",
            "fetched_at": "2026-07-04T04:54:37Z",
        }

        payload = mark_fallback_payload(original, source_backend="fallback-url")

        self.assertEqual(payload["source_backend"], "fallback-url")
        self.assertEqual(payload["fallback_source_backend"], "direct-html")
        self.assertEqual(payload["fallback_used_at"], "2026-07-14T04:49:57Z")
        self.assertEqual(payload["fetched_at"], "2026-07-04T04:54:37Z")
        self.assertEqual(original["source_backend"], "direct-html")


class SerpApiTests(unittest.TestCase):
    def setUp(self):
        self.api_payload = {
            "search_metadata": {"status": "Success"},
            "search_parameters": {
                "engine": "google_scholar_author",
                "author_id": "8VCnj3sAAAAJ",
            },
            "author": {"name": "Haidong Xin"},
            "cited_by": {
                "table": [
                    {"citations": {"all": 72, "since_2021": 72}},
                    {"h_index": {"all": 5, "since_2021": 5}},
                    {"i10_index": {"all": 2, "since_2021": 2}},
                ]
            },
            "articles": [
                {
                    "title": "Example Paper",
                    "citation_id": "8VCnj3sAAAAJ:example",
                    "cited_by": {"value": 12},
                    "year": "2026",
                }
            ],
        }

    def test_extracts_remaining_free_quota(self):
        self.assertEqual(
            extract_serpapi_remaining_credits(
                {"plan_searches_left": 200, "extra_credits": 3}
            ),
            203,
        )

    def test_parses_author_metrics_and_publications(self):
        metrics = parse_serpapi_metrics(self.api_payload)
        publications = parse_serpapi_publications(self.api_payload)

        self.assertEqual(metrics["citedby"], 72)
        self.assertEqual(metrics["citedby5y"], 72)
        self.assertEqual(publications["example"]["num_citations"], 12)
        self.assertEqual(publications["example"]["year"], 2026)

    @patch("citation.get_citation.utc_now_iso", return_value="2026-07-18T04:00:00Z")
    @patch("citation.get_citation.create_session")
    def test_collects_serpapi_payload_after_quota_check(self, mock_session, _mock_now):
        account_response = Mock(status_code=200)
        account_response.json.return_value = {"total_searches_left": 250}
        search_response = Mock(status_code=200)
        search_response.json.return_value = self.api_payload
        mock_session.return_value.get.side_effect = [account_response, search_response]

        result = collect_serpapi_stats(
            api_key="secret",
            user_id="8VCnj3sAAAAJ",
            hl="en",
            pagesize=100,
            timeout=20,
            min_credits=5,
        )

        self.assertEqual(result.payload["citedby"], 72)
        self.assertEqual(result.payload["source_backend"], "serpapi-google-scholar-author")
        self.assertEqual(mock_session.return_value.get.call_count, 2)

    @patch("citation.get_citation.create_session")
    def test_quota_guard_does_not_start_a_search(self, mock_session):
        account_response = Mock(status_code=200)
        account_response.json.return_value = {"total_searches_left": 5}
        mock_session.return_value.get.return_value = account_response

        with self.assertRaisesRegex(ScholarFetchError, "quota guard"):
            collect_serpapi_stats(
                api_key="secret",
                user_id="8VCnj3sAAAAJ",
                hl="en",
                pagesize=100,
                timeout=20,
                min_credits=5,
            )

        self.assertEqual(mock_session.return_value.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
