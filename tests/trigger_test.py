import os
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple

# Ensure repo root on sys.path so "integrations" works when run from tests/
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load .env (search upwards)
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore

    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass

from integrations.google_oauth import build_user_credentials  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from core.trigger_words import load_trigger_words

CAL_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


def _parse_calendar_ids(value: str | None) -> List[str]:
    if not value:
        return ["primary"]
    value = value.strip()
    if value.startswith("["):
        try:
            import json as _json

            arr = _json.loads(value)
            ids = [str(x).strip() for x in arr if str(x).strip()]
            return list(dict.fromkeys(ids)) or ["primary"]
        except ImportError as e:
            import logging
            logging.getLogger(__name__).warning("Failed to load dotenv: %s", e)
    parts = [p.strip() for p in re.split(r"[,\s;]+", value) if p.strip()]
    return list(dict.fromkeys(parts)) or ["primary"]


def _split_words(raw: str | None) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[,\n;]\s*|\s{2,}", raw.strip())
    return [p.strip() for p in parts if p.strip()]


def _build_pattern(words: List[str], raw_regex: str | None) -> re.Pattern | None:
    if raw_regex:
        try:
            return re.compile(raw_regex, re.IGNORECASE)
        except re.error:
            return None
    if not words:
        return None
    escaped = [re.escape(w) for w in words if w]
    if not escaped:
        return None
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


def _time_window(lookback_days: int, lookahead_days: int) -> Tuple[str, str]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    tmin = (now - timedelta(days=lookback_days)).isoformat().replace("+00:00", "Z")
    tmax = (now + timedelta(days=lookahead_days)).isoformat().replace("+00:00", "Z")
    return tmin, tmax


def _event_text(ev: Dict[str, Any]) -> str:
    fields: List[str] = []
    fields.append(str(ev.get("summary", "") or ""))
    fields.append(str(ev.get("description", "") or ""))
    fields.append(str(ev.get("location", "") or ""))
    for a in ev.get("attendees", []) or []:
        fields.append(str(a.get("email", "") or ""))
        fields.append(str(a.get("displayName", "") or ""))
    return "\n".join([f for f in fields if f])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Google Calendar events for trigger matches."
    )
    parser.add_argument(
        "--cal-ids",
        help="Calendar IDs (comma/semicolon/space separated). Overrides GOOGLE_CALENDAR_IDS.",
    )
    parser.add_argument(
        "--words",
        help="Trigger words (comma/semicolon/newline separated). Overrides TRIGGER_WORDS.",
    )
    parser.add_argument(
        "--regex",
        help="Trigger regex (case-insensitive recommended, e.g., (?i)\\b(word1|word2)\\b). Overrides TRIGGER_REGEX.",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=int(os.getenv("CAL_LOOKBACK_DAYS", "2")),
        help="Lookback days (default from CAL_LOOKBACK_DAYS or 2).",
    )
    parser.add_argument(
        "--lookahead",
        type=int,
        default=int(os.getenv("CAL_LOOKAHEAD_DAYS", "30")),
        help="Lookahead days (default from CAL_LOOKAHEAD_DAYS or 30).",
    )
    parser.add_argument(
        "--max-hits", type=int, default=50, help="Max hits to include in output."
    )
    parser.add_argument(
        "--include-misses",
        action="store_true",
        help="Include up to 10 non-matching event summaries in diagnostics.",
    )
    args = parser.parse_args()

    cal_ids = _parse_calendar_ids(args.cal_ids or os.getenv("GOOGLE_CALENDAR_IDS"))
    words = _split_words(args.words or os.getenv("TRIGGER_WORDS"))
    if not words:
        words = load_trigger_words()
    raw_regex = args.regex or os.getenv("TRIGGER_REGEX")
    pattern = _build_pattern(words, raw_regex)

    creds = build_user_credentials([CAL_SCOPE])
    if not creds:
        print(json.dumps({"ok": False, "error": "missing_google_credentials"}))
        return 2

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    tmin, tmax = _time_window(args.lookback, args.lookahead)

    hits: List[Dict[str, Any]] = []
    misses = 0
    miss_samples: List[Dict[str, Any]] = []
    per_calendar_stats: Dict[str, int] = {}

    for cid in cal_ids:
        per_calendar_stats[cid] = 0
        try:
            service.calendarList().get(calendarId=cid).execute()
        except Exception as e:
            print(
                json.dumps(
                    {"ok": False, "calendar_id": cid, "error": f"access_failed: {e}"}
                )
            )
            continue

        token = None
        while True:
            resp = (
                service.events()
                .list(
                    calendarId=cid,
                    timeMin=tmin,
                    timeMax=tmax,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=2500,
                    pageToken=token,
                )
                .execute()
            )
            for ev in resp.get("items", []):
                per_calendar_stats[cid] += 1
                text = _event_text(ev)
                matched_terms: List[str] = []
                matched = False
                if pattern:
                    m = pattern.search(text)
                    matched = bool(m)
                    if matched:
                        try:
                            # Use match groups instead of separate findall call
                            if m.groups():
                                matched_terms = [m.group(1).lower()]
                            else:
                                matched_terms = [m.group(0).lower()]
                        except Exception:
                            matched_terms = []
                rec = {
                    "calendar_id": cid,
                    "event_id": ev.get("id"),
                    "start": ev.get("start", {}),
                    "end": ev.get("end", {}),
                    "summary": ev.get("summary"),
                    "matched": matched,
                    "matched_terms": matched_terms,
                }
                if matched:
                    hits.append(rec)
                else:
                    misses += 1
                    if args.include_misses and len(miss_samples) < 10:
                        miss_samples.append(
                            {
                                "calendar_id": cid,
                                "event_id": ev.get("id"),
                                "summary": ev.get("summary"),
                            }
                        )
            token = resp.get("nextPageToken")
            if not token:
                break

    result = {
        "ok": True,
        "calendars": cal_ids,
        "lookback_days": args.lookback,
        "lookahead_days": args.lookahead,
        "trigger_words": words,
        "trigger_regex": raw_regex,
        "stats": {
            "per_calendar_total": per_calendar_stats,
            "hits": len(hits),
            "misses": misses,
        },
        "hits": hits[: args.max_hits],
        "miss_samples": miss_samples,
    }
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
