"""Deterministic smoke check for a running Spendly instance.

Usage: python scripts/smoke_check.py [BASE_URL]
Exit 0 when every check passes, 1 otherwise. Stdlib only, so loops can call it
cheaply instead of having the model reason through the same steps every time.
"""
import json
import sys
import urllib.error
import urllib.request

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5001").rstrip("/")
PAGES = ("/", "/login", "/register", "/terms", "/privacy")


def fetch(path):
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, ""
    except (urllib.error.URLError, TimeoutError) as err:
        return 0, str(err)


def main():
    failures = []

    status, body = fetch("/health")
    try:
        ok = status == 200 and json.loads(body).get("status") == "ok"
    except ValueError:
        ok = False
    print(f"{'PASS' if ok else 'FAIL'} /health -> {status}")
    if not ok:
        failures.append("/health")

    for path in PAGES:
        status, _ = fetch(path)
        ok = status == 200
        print(f"{'PASS' if ok else 'FAIL'} {path} -> {status}")
        if not ok:
            failures.append(path)

    print(f"\n{len(failures)} failing check(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
