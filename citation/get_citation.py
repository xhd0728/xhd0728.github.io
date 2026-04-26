#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

BASE_URL = "https://scholar.google.com/citations"
HOME_URL = "https://scholar.google.com/"
DEFAULT_PROFILE_PAGE_SIZE = 20
DIGIT_RE = re.compile(r"\d+")
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}
BLOCK_HINTS = (
    "our systems have detected unusual traffic",
    "not a robot",
    "verify you're not a robot",
    "please show you're not a robot",
    "recaptcha",
    "/sorry/",
    "gs_captcha_ccl",
    "g-recaptcha",
)
PROFILE_METRIC_KEYS = (
    ("citedby", "citedby5y"),
    ("hindex", "hindex5y"),
    ("i10index", "i10index5y"),
)


class ScholarFetchError(RuntimeError):
    """Raised when Google Scholar stats cannot be fetched from the public profile."""


@dataclass
class LiveFetchResult:
    payload: dict[str, object]
    partial_publications: bool = False
    warnings: tuple[str, ...] = ()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Google Scholar citation stats from a public profile page."
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
        help="Google Scholar page size for page 2+. Defaults to 100.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=int(os.environ.get("SCHOLAR_MAX_PAGES", "1")),
        help="Maximum number of profile pages to scan. Defaults to 1.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("SCHOLAR_TIMEOUT", "20")),
        help="Per-request timeout in seconds. Defaults to 20.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("SCHOLAR_RETRIES", "3")),
        help="Number of retries for each Google Scholar page. Defaults to 3.",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=float(os.environ.get("SCHOLAR_MIN_DELAY", "0.8")),
        help="Minimum delay in seconds between retries/pages. Defaults to 0.8.",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=float(os.environ.get("SCHOLAR_MAX_DELAY", "1.8")),
        help="Maximum delay in seconds between retries/pages. Defaults to 1.8.",
    )
    parser.add_argument(
        "--proxy-url",
        default=os.environ.get("SCHOLAR_PROXY"),
        help="Optional proxy URL for both http and https requests.",
    )
    parser.add_argument(
        "--fallback-url",
        default=os.environ.get("SCHOLAR_FALLBACK_URL"),
        help="Optional URL for the last known good gs_data.json used when live fetch is blocked.",
    )
    parser.add_argument(
        "--fallback-file",
        default=os.environ.get("SCHOLAR_FALLBACK_FILE"),
        help="Optional local fallback gs_data.json path used before fallback-url.",
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
    if args.min_delay < 0 or args.max_delay < 0:
        parser.error("--min-delay and --max-delay must be non-negative.")
    if args.max_delay < args.min_delay:
        parser.error("--max-delay must be greater than or equal to --min-delay.")
    return args


def build_profile_url(user_id: str, hl: str) -> str:
    return f"{BASE_URL}?{urlencode({'user': user_id, 'hl': hl})}"


def build_page_url(user_id: str, hl: str, *, cstart: int, pagesize: int) -> str:
    return f"{BASE_URL}?{urlencode({'user': user_id, 'hl': hl, 'cstart': cstart, 'pagesize': pagesize})}"


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


def is_blocked_response(html: str) -> bool:
    lowered = html.lower()
    return any(hint in lowered for hint in BLOCK_HINTS)


def sleep_with_jitter(min_delay: float, max_delay: float) -> None:
    if max_delay <= 0:
        return
    if min_delay == max_delay:
        time.sleep(min_delay)
        return
    time.sleep(random.uniform(min_delay, max_delay))


def build_payload(
    *,
    user_id: str,
    hl: str,
    scholar_name: str | None,
    metrics: dict[str, int | None],
    publications: dict[str, dict[str, int | str]],
    source_backend: str,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "profile_url": build_profile_url(user_id=user_id, hl=hl),
        "scholar_name": scholar_name,
        "citedby": metrics.get("citedby"),
        "citedby5y": metrics.get("citedby5y"),
        "hindex": metrics.get("hindex"),
        "hindex5y": metrics.get("hindex5y"),
        "i10index": metrics.get("i10index"),
        "i10index5y": metrics.get("i10index5y"),
        "publications": publications,
        "source_backend": source_backend,
    }


def validate_payload(payload: object, user_id: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ScholarFetchError("stats payload is not a JSON object.")

    if "citedby" not in payload or "publications" not in payload:
        raise ScholarFetchError("stats payload is missing required keys.")

    if not isinstance(payload["publications"], dict):
        raise ScholarFetchError("stats payload has an invalid publications field.")

    payload_user_id = str(payload.get("user_id") or "")
    if payload_user_id and payload_user_id != user_id:
        raise ScholarFetchError(
            f"stats payload user id mismatch: expected {user_id}, got {payload_user_id}"
        )

    return payload


def extract_publication_id(href: str | None) -> str | None:
    if not href:
        return None
    params = parse_qs(urlparse(href).query)
    values = params.get("citation_for_view")
    if not values:
        return None
    return normalize_publication_id(values[0])


def create_session(proxy_url: str | None):
    try:
        import requests
    except ImportError as exc:
        raise ScholarFetchError(
            "Missing dependencies. Run `pip install -r citation/requirements.txt`."
        ) from exc

    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    return session


def warm_up_google_scholar(
    *,
    session,
    timeout: int,
    min_delay: float,
    max_delay: float,
) -> None:
    try:
        session.get(HOME_URL, timeout=timeout)
    except Exception:
        return
    sleep_with_jitter(min_delay=min_delay, max_delay=max_delay)


def fetch_profile_page(
    *,
    session,
    user_id: str,
    hl: str,
    cstart: int,
    pagesize: int,
    timeout: int,
    retries: int,
    min_delay: float,
    max_delay: float,
):
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ScholarFetchError(
            "Missing dependencies. Run `pip install -r citation/requirements.txt`."
        ) from exc

    url = (
        build_profile_url(user_id=user_id, hl=hl)
        if cstart == 0
        else build_page_url(user_id=user_id, hl=hl, cstart=cstart, pagesize=pagesize)
    )
    referer = HOME_URL if cstart == 0 else build_profile_url(user_id=user_id, hl=hl)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout, headers={"Referer": referer})
        except Exception as exc:
            last_error = exc
        else:
            if response.status_code == 403:
                last_error = ScholarFetchError(f"403 Client Error: Forbidden for url: {url}")
            elif response.status_code >= 400:
                last_error = ScholarFetchError(
                    f"{response.status_code} Client Error for url: {url}"
                )
            else:
                html = response.text
                if is_blocked_response(html):
                    last_error = ScholarFetchError(
                        "Google Scholar returned an anti-bot page for the public profile."
                    )
                else:
                    return BeautifulSoup(html, "html.parser")

        if attempt < retries:
            sleep_with_jitter(min_delay=min_delay, max_delay=max_delay)

    raise ScholarFetchError(
        f"failed to fetch Google Scholar profile page at offset {cstart}: {last_error}"
    )


def parse_author_metrics(soup) -> dict[str, int | None]:
    metrics = {key: None for pair in PROFILE_METRIC_KEYS for key in pair}
    rows = []
    for row in soup.select("#gsc_rsb_st tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) >= 3:
            rows.append(cells)

    for row_index, (all_key, five_year_key) in enumerate(PROFILE_METRIC_KEYS):
        if row_index >= len(rows):
            break
        metrics[all_key] = extract_first_int(rows[row_index][1])
        metrics[five_year_key] = extract_first_int(rows[row_index][2])

    return metrics


def parse_publications_on_page(soup) -> dict[str, dict[str, int | str]]:
    publications: dict[str, dict[str, int | str]] = {}

    for row in soup.select("tr.gsc_a_tr"):
        title_link = row.select_one("a.gsc_a_at")
        if title_link is None:
            continue

        publication_id = extract_publication_id(title_link.get("href"))
        if not publication_id:
            continue

        title = title_link.get_text(" ", strip=True)
        citations_element = row.select_one(".gsc_a_c a, .gsc_a_c span")
        year_element = row.select_one(".gsc_a_y span, .gsc_a_y")

        entry: dict[str, int | str] = {
            "title": title,
            "num_citations": extract_first_int(
                citations_element.get_text(" ", strip=True) if citations_element else ""
            )
            or 0,
        }

        year = extract_first_int(year_element.get_text(" ", strip=True) if year_element else "")
        if year is not None:
            entry["year"] = year

        publications[publication_id] = entry

    return publications


def collect_stats(
    *,
    user_id: str,
    hl: str,
    pagesize: int,
    max_pages: int,
    timeout: int,
    retries: int,
    min_delay: float,
    max_delay: float,
    proxy_url: str | None,
) -> LiveFetchResult:
    session = create_session(proxy_url=proxy_url)
    warm_up_google_scholar(
        session=session,
        timeout=timeout,
        min_delay=min_delay,
        max_delay=max_delay,
    )

    publications: dict[str, dict[str, int | str]] = {}
    scholar_name: str | None = None
    metrics = {key: None for pair in PROFILE_METRIC_KEYS for key in pair}
    partial_publications = False
    warnings: list[str] = []
    cstart = 0

    for page_index in range(max_pages):
        try:
            soup = fetch_profile_page(
                session=session,
                user_id=user_id,
                hl=hl,
                cstart=cstart,
                pagesize=pagesize,
                timeout=timeout,
                retries=retries,
                min_delay=min_delay,
                max_delay=max_delay,
            )
        except ScholarFetchError as exc:
            if page_index == 0:
                raise
            partial_publications = True
            warnings.append(str(exc))
            break

        if page_index == 0:
            name_element = soup.select_one("#gsc_prf_in")
            scholar_name = name_element.get_text(" ", strip=True) if name_element else None
            metrics = parse_author_metrics(soup)
            if scholar_name is None or metrics.get("citedby") is None:
                raise ScholarFetchError("Google Scholar profile page did not contain author stats.")

        page_publications = parse_publications_on_page(soup)
        if not page_publications:
            if page_index == 0:
                warnings.append("Google Scholar profile page did not contain publication rows.")
            break

        new_count = 0
        for publication_id, publication in page_publications.items():
            if publication_id not in publications:
                new_count += 1
            publications[publication_id] = publication

        requested_page_size = DEFAULT_PROFILE_PAGE_SIZE if cstart == 0 else pagesize
        if len(page_publications) < requested_page_size or new_count == 0:
            break

        cstart += len(page_publications)
        sleep_with_jitter(min_delay=min_delay, max_delay=max_delay)

    if metrics.get("citedby") is None:
        raise ScholarFetchError("Google Scholar profile page did not contain total citations.")

    payload = build_payload(
        user_id=user_id,
        hl=hl,
        scholar_name=scholar_name,
        metrics=metrics,
        publications=publications,
        source_backend="direct-html",
    )
    return LiveFetchResult(
        payload=payload,
        partial_publications=partial_publications,
        warnings=tuple(warnings),
    )


def load_fallback_payload_from_file(fallback_file: str, user_id: str) -> dict[str, object]:
    path = Path(fallback_file)
    if not path.exists():
        raise ScholarFetchError(f"fallback file does not exist: {path}")
    return validate_payload(json.loads(path.read_text(encoding="utf-8")), user_id=user_id)


def load_fallback_payload_from_url(
    fallback_url: str,
    timeout: int,
    user_id: str,
) -> dict[str, object]:
    session = create_session(proxy_url=None)
    try:
        response = session.get(fallback_url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise ScholarFetchError(f"failed to load fallback stats from {fallback_url}: {exc}") from exc
    return validate_payload(payload, user_id=user_id)


def load_fallback_payload(
    *,
    fallback_file: str | None,
    fallback_url: str | None,
    timeout: int,
    user_id: str,
) -> dict[str, object]:
    errors: list[str] = []

    if fallback_file:
        try:
            return load_fallback_payload_from_file(fallback_file=fallback_file, user_id=user_id)
        except ScholarFetchError as exc:
            errors.append(str(exc))

    if fallback_url:
        try:
            return load_fallback_payload_from_url(
                fallback_url=fallback_url,
                timeout=timeout,
                user_id=user_id,
            )
        except ScholarFetchError as exc:
            errors.append(str(exc))

    raise ScholarFetchError("; ".join(errors) or "no fallback source configured")


def merge_live_payload_with_fallback(
    live_payload: dict[str, object],
    fallback_payload: dict[str, object],
) -> dict[str, object]:
    merged = dict(fallback_payload)
    merged.update(live_payload)

    merged_publications = dict(fallback_payload.get("publications") or {})
    merged_publications.update(live_payload.get("publications") or {})
    merged["publications"] = merged_publications
    merged["source_backend"] = "direct-html+cached-publications"
    return merged


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
        result = collect_stats(
            user_id=args.user_id,
            hl=args.hl,
            pagesize=args.pagesize,
            max_pages=args.max_pages,
            timeout=args.timeout,
            retries=args.retries,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            proxy_url=args.proxy_url,
        )
        payload = result.payload
        if result.partial_publications and (args.fallback_file or args.fallback_url):
            fallback_payload = load_fallback_payload(
                fallback_file=args.fallback_file,
                fallback_url=args.fallback_url,
                timeout=args.timeout,
                user_id=args.user_id,
            )
            payload = merge_live_payload_with_fallback(
                live_payload=payload,
                fallback_payload=fallback_payload,
            )
            for warning in result.warnings:
                print(f"warning: {warning}", file=sys.stderr)
    except ScholarFetchError as exc:
        if not args.fallback_file and not args.fallback_url:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"warning: live fetch failed, using fallback stats: {exc}", file=sys.stderr)
        try:
            payload = load_fallback_payload(
                fallback_file=args.fallback_file,
                fallback_url=args.fallback_url,
                timeout=args.timeout,
                user_id=args.user_id,
            )
        except ScholarFetchError as fallback_exc:
            print(f"error: {fallback_exc}", file=sys.stderr)
            return 1

    destination = write_stats(args.output, payload)
    print(
        f"Wrote Google Scholar stats for {args.user_id} "
        f"(cited by {payload['citedby']}, backend={payload.get('source_backend', 'unknown')}) "
        f"to {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
