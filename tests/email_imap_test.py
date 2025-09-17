import os
import sys
import ssl
import json
import imaplib
import argparse
from typing import List, Dict, Any
from email.parser import BytesParser
from email.policy import default as default_policy

# Load .env (searches upward from CWD)
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore

    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass


def connect_imap(host: str, port: int, secure: str) -> imaplib.IMAP4:
    mode = (secure or "").lower()
    if mode in {"ssl", "imaps"} or port == 993:
        ctx = ssl.create_default_context()
        return imaplib.IMAP4_SSL(host, port or 993, ssl_context=ctx)
    # STARTTLS or plain
    client = imaplib.IMAP4(host, port or 143)
    if mode in {"starttls", "tls", "1", "true", "yes"}:
        client.starttls(ssl_context=ssl.create_default_context())
    return client


def fetch_headers(client: imaplib.IMAP4, ids: List[bytes]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for msg_id in ids:
        # Fetch size and selected headers only
        typ, resp = client.fetch(
            msg_id,
            b"(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID)])",
        )
        if typ != "OK" or not resp:
            out.append({"id": msg_id.decode(), "error": "fetch_failed"})
            continue
        size = None
        headers_bytes = b""
        for part in resp:
            if isinstance(part, tuple):
                meta, data = part
                headers_bytes = data or b""
                # Extract size from meta if present
                if b"RFC822.SIZE" in meta:
                    try:
                        size = int(meta.split(b"RFC822.SIZE")[1].split()[0])
                    except Exception:
                        size = None
        msg = BytesParser(policy=default_policy).parsebytes(headers_bytes or b"")
        out.append(
            {
                "id": msg_id.decode(),
                "subject": (msg["subject"] or "").strip(),
                "from": (msg["from"] or "").strip(),
                "to": (msg["to"] or "").strip(),
                "date": (msg["date"] or "").strip(),
                "size": size,
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="IMAP inbound email health-check")
    parser.add_argument(
        "--folder",
        default=os.getenv("IMAP_FOLDER", "INBOX"),
        help="IMAP folder to open",
    )
    parser.add_argument(
        "--search",
        default=os.getenv("IMAP_SEARCH", "UNSEEN"),
        help="IMAP search query (e.g., UNSEEN or ALL)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("IMAP_TEST_LIMIT", "5")),
        help="Max messages to sample from the end",
    )
    parser.add_argument("--debug", action="store_true", help="Enable IMAP debug output")
    args = parser.parse_args()

    host = os.getenv("IMAP_HOST", "")
    port = int(os.getenv("IMAP_PORT", "0") or "0")
    user = os.getenv("IMAP_USER", "")
    pwd = os.getenv("IMAP_PASS", "")
    secure = os.getenv("IMAP_SECURE", "ssl" if (port or 0) in (0, 993) else "starttls")

    if not host or not user or not pwd:
        print(
            json.dumps({"ok": False, "error": "Missing IMAP_HOST/IMAP_USER/IMAP_PASS"})
        )
        return 2

    try:
        if args.debug:
            imaplib.Debug = 4  # verbose
        client = connect_imap(host, port, secure)
        typ, _ = client.login(user, pwd)
        if typ != "OK":
            raise RuntimeError("login_failed")

        typ, _ = client.select(args.folder, readonly=True)
        if typ != "OK":
            raise RuntimeError(f"cannot_select_folder:{args.folder}")

        # IMAP search: pass criteria as separate strings
        criteria = args.search.strip().split()
        typ, data = client.search(None, *criteria)  # e.g., ("UNSEEN",) or ("ALL",)
        if typ != "OK":
            raise RuntimeError(f"search_failed:{args.search}")

        ids = data[0].split() if data and data[0] else []
        sampled = ids[-args.limit :] if args.limit > 0 else ids

        headers = fetch_headers(client, sampled)

        result = {
            "ok": True,
            "host": host,
            "port": port or (993 if secure.lower() in {"ssl", "imaps"} else 143),
            "secure": secure,
            "folder": args.folder,
            "search": args.search,
            "matched_total": len(ids),
            "sampled_count": len(sampled),
            "messages": headers,
        }
        print(json.dumps(result, ensure_ascii=False))
        try:
            client.logout()
        except Exception:
            pass
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
