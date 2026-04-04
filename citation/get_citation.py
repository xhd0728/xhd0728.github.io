#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

BASE_URL = "https://scholar.google.com/citations"
DIGIT_RE = re.compile(r"\d+")


class ScholarFetchError(RuntimeError):
    """Raised when Google Scholar stats cannot be fetched with scholarly."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Google Scholar citation stats for a public profile with scholarly."
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("SCHOLAR_USER_ID"),
        help="Google Scholar profile user id, e.g. 8VCnj3sAAAAJ.",
    )
    parser.add_argument(
        "--hl",
        default=os.environ.get("SCHOLAR_LANGUAGE", "en"),
        help="Google Scholar UI language used in the output profile URL. Defaults to en.",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("SCHOLAR_OUTPUT", "gs_data.json"),
        help="Output JSON path. Defaults to gs_data.json.",
    )
    parser.add_argument(
        "--pagesize",
        type=int,
        default=int(os.environ.get("SCHOLAR_PAGE_SIZE", "100")),
        help="Virtual page size used to derive the scholarly publication limit.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=int(os.environ.get("SCHOLAR_MAX_PAGES", "5")),
        help="Virtual page count used to derive the scholarly publication limit.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("SCHOLAR_TIMEOUT", "20")),
        help="Per-request timeout in seconds for scholarly. Defaults to 20.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("SCHOLAR_RETRIES", "3")),
        help="Number of retries used by scholarly. Defaults to 3.",
    )
    args = parser.parse_args()
    if not args.user_id:
        parser.error("--user-id is required unless SCHOLAR_USER_ID is set.")
    if args.pagesize <= 0:
        parser.error("--pagesize must be greater than 0.")
    if args.max_pages <= 0:
        parser.error("--max-pages must be greater than 0.")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0.")
    if args.retries <= 0:
        parser.error("--retries must be greater than 0.")
    return args


def build_profile_url(user_id: str, hl: str) -> str:
    return f"{BASE_URL}?{urlencode({'user': user_id, 'hl': hl})}"


def extract_first_int(text: str | None) -> int | None:
    if not text:
        return None
    match = DIGIT_RE.search(text.replace(",", ""))
    if not match:
        return None
    return int(match.group(0))


def normalize_publication_id(publication_id: str | None) -> str | None:
    if not publication_id:
        return None
    _, _, suffix = publication_id.partition(":")
    return suffix or publication_id


def build_payload(
    *,
    user_id: str,
    hl: str,
    scholar_name: str | None,
    citedby: int,
    publications: dict[str, dict[str, int | str]],
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "profile_url": build_profile_url(user_id=user_id, hl=hl),
        "scholar_name": scholar_name,
        "citedby": citedby,
        "publications": publications,
        "source_backend": "scholarly",
    }


def collect_stats(
    *,
    user_id: str,
    hl: str,
    pagesize: int,
    max_pages: int,
    timeout: int,
    retries: int,
) -> dict[str, object]:
    try:
        from scholarly import scholarly as scholarly_client
    except ImportError as exc:
        raise ScholarFetchError(
            "scholarly is not installed. Run `pip install -r citation/requirements.txt`."
        ) from exc

    if hasattr(scholarly_client, "set_logger"):
        scholarly_client.set_logger(False)
    if hasattr(scholarly_client, "set_timeout"):
        scholarly_client.set_timeout(timeout)
    if hasattr(scholarly_client, "set_retries"):
        scholarly_client.set_retries(retries)

    publication_limit = pagesize * max_pages

    try:
        author = scholarly_client.search_author_id(
            user_id,
            filled=False,
            sortby="citedby",
            publication_limit=publication_limit,
        )
        author = scholarly_client.fill(
            author,
            sections=["basics", "indices", "publications"],
            sortby="citedby",
            publication_limit=publication_limit,
        )
    except Exception as exc:
        raise ScholarFetchError(f"scholarly failed to fetch the profile: {exc}") from exc

    citedby = extract_first_int(str(author.get("citedby")))
    if citedby is None:
        raise ScholarFetchError("scholarly returned an author object without total citations.")

    publications: dict[str, dict[str, int | str]] = {}
    for publication in author.get("publications", []):
        publication_id = normalize_publication_id(
            str(publication.get("author_pub_id") or publication.get("scholar_id") or "")
        )
        if not publication_id:
            continue

        bib = publication.get("bib") or {}
        title = str(bib.get("title") or publication.get("title") or publication_id).strip()
        num_citations = extract_first_int(str(publication.get("num_citations"))) or 0

        entry: dict[str, int | str] = {
            "title": title,
            "num_citations": num_citations,
        }

        year = extract_first_int(str(bib.get("pub_year") or publication.get("year") or ""))
        if year is not None:
            entry["year"] = year

        publications[publication_id] = entry

    return build_payload(
        user_id=user_id,
        hl=hl,
        scholar_name=author.get("name"),
        citedby=citedby,
        publications=publications,
    )


def write_stats(output_path: str, payload: dict[str, object]) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> int:
    args = parse_args()
    try:
        payload = collect_stats(
            user_id=args.user_id,
            hl=args.hl,
            pagesize=args.pagesize,
            max_pages=args.max_pages,
            timeout=args.timeout,
            retries=args.retries,
        )
        destination = write_stats(args.output, payload)
    except ScholarFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote Google Scholar stats for {args.user_id} "
        f"(cited by {payload['citedby']}, backend=scholarly) to {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
