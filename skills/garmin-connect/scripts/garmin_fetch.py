#!/usr/bin/env python3
"""Garmin Connect Personal API fetcher (stdlib only).

Garmin's official Personal API for an athlete's own data:
https://developer.garmin.com/gc-developer-program/personal/personal-api/

Auth: a personal API key (created at connect.garmin.com → Settings → Personal API key,
starts with "GCDC_") is exchanged for a 24 h bearer token:
  POST https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token
  Authorization: ApiKey <key>      (Accept must be */*; application/json gets HTTP 406)
The token comes back as plain text (a JWT) and goes on every call as `Authorization: Bearer <token>`.

The key is read from $GARMIN_API_KEY (or $GARMIN_PERSONAL_API_KEY), or from --key-file. Never print or commit it.

Usage:
  garmin_fetch.py check                         # exchange the key, print token scopes and expiry
  garmin_fetch.py get PATH [-o OUT]             # one GET, e.g. /hrv-service/hrv/2026-11-02
  garmin_fetch.py archive START END [-d DIR] [--details] [--fit] [--work CACHE]
        HRV, sleep, daily summaries, weight, activities, fitness age, HR zones (+ every activity's
        detail record, + metrics from every original FIT file via garmin_fit.py, which needs
        fitdecode and numpy) -> DIR/garmin_<kind>_<START>_<END>.json.gz
        GPS, place names and owner fields are dropped. FIT files are deleted after extraction.
"""
import argparse
import base64
import concurrent.futures
import gzip
import io
import datetime as dt
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

API = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"


def _http(method, url, headers, retries=6):
    """One request with retries. HTTP 429 waits as long as Garmin asks (retryInSeconds; the
    Personal API allows about 100 requests a minute) and does not count against `retries`."""
    i = waits = 0
    while True:
        req = urllib.request.Request(url, data=b"" if method == "POST" else None, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 429 and waits < 60:
                try:
                    wait = float(json.loads(body).get("retryInSeconds", 30))
                except ValueError:
                    wait = 30
                waits += 1
                time.sleep(wait + 1)
                continue
            if e.code in (500, 502, 503, 504) and i < retries - 1:
                i += 1
                time.sleep(2 ** i)
                continue
            return e.code, body
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            if i >= retries - 1:
                raise
            i += 1
            time.sleep(2 ** i)  # proxy cut-offs, resets


class Garmin:
    def __init__(self, key):
        status, body = _http("POST", API + TOKEN_PATH, {"Authorization": f"ApiKey {key}", "Accept": "*/*"})
        if status != 200:
            sys.exit(f"Token exchange failed: HTTP {status}. Key expired, revoked or mistyped?")
        self.token = body.decode().strip().strip('"')

    def claims(self):
        part = self.token.split(".")[1]
        part += "=" * (-len(part) % 4)
        c = json.loads(base64.urlsafe_b64decode(part))
        return {"scope": c.get("scope"), "expires_in_h": round((c.get("exp", 0) - time.time()) / 3600, 1)}

    def get(self, path):
        status, body = _http("GET", API + path, {"Authorization": f"Bearer {self.token}", "Accept": "*/*"})
        if status == 204:
            return None
        if status != 200:
            raise RuntimeError(f"HTTP {status} GET {path}: {body[:200]!r}")
        try:
            return json.loads(body)
        except ValueError:
            return body


def api_key():
    """The personal API key from the environment: GARMIN_API_KEY, else GARMIN_PERSONAL_API_KEY."""
    for name in ("GARMIN_API_KEY", "GARMIN_PERSONAL_API_KEY"):
        key = os.environ.get(name, "").strip()
        if key:
            return key
    return ""


_PRIVATE = ("latitude", "longitude", "location", "owner", "polyline", "geo")


def scrub(x):
    """Drop GPS coordinates, place names and owner identity before anything is written to the repo."""
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items() if not any(t in k.lower() for t in _PRIVATE)}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def chunks(start, end, days):
    a, z = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    while a <= z:
        b = min(a + dt.timedelta(days=days - 1), z)
        yield a.isoformat(), b.isoformat()
        a = b + dt.timedelta(days=1)


FIT_TYPES = ("running", "trail_running", "treadmill_running", "track_running", "cycling", "road_biking",
             "virtual_ride", "indoor_cycling", "mountain_biking", "gravel_cycling", "lap_swimming",
             "open_water_swimming", "strength_training")


def _save(out_dir, kind, tag, data):
    p = os.path.join(out_dir, f"garmin_{kind}_{tag}.json.gz")
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(scrub(data), f, separators=(",", ":"))
    n = len(data) if isinstance(data, list) else 1
    print(f"{kind:16} {n:5} rows -> {p}", file=sys.stderr, flush=True)


def _fit_job(token, aid, work):
    """Worker: download one original FIT, extract metrics, delete the file. Returns (id, metrics|None)."""
    import garmin_fit  # needs fitdecode + numpy
    cache = os.path.join(work, "fit", f"{aid}.json")
    if os.path.exists(cache):
        return aid, json.load(open(cache))
    status, body = _http("GET", f"{API}/download-service/files/activity/{aid}",
                         {"Authorization": f"Bearer {token}", "Accept": "*/*"})
    if status != 200 or body[:2] != b"PK":
        return aid, None
    tmp = os.path.join(work, "tmp", f"{aid}.fit")
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            fits = [n for n in z.namelist() if n.lower().endswith(".fit")]
            if not fits:
                return aid, None
            with open(tmp, "wb") as f:
                f.write(z.read(fits[0]))
        m = garmin_fit.metrics(tmp)
    except Exception as e:  # a corrupt or exotic file must not stop the archive
        m = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    json.dump(m, open(cache, "w"))
    return aid, m


def archive(g, start, end, out_dir, details=False, fit=False, work=None, workers=3):
    """Everything the Personal API holds between START and END, gzipped into OUT_DIR.
    Wellness (HRV, sleep, daily summaries, weight), activities, fitness age and HR zones always;
    per-activity detail records with --details; metrics from every original FIT file with --fit.
    WORK holds a resumable per-activity cache (default: a temp dir)."""
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{start}_{end}"
    work = work or tempfile.mkdtemp(prefix="garmin-archive-")
    for sub_ in ("details", "fit", "tmp"):
        os.makedirs(os.path.join(work, sub_), exist_ok=True)

    hrv = []
    for a, b in chunks(start, end, 28):
        hrv += ((g.get(f"/hrv-service/hrv/daily/{a}/{b}") or {}).get("hrvSummaries") or [])
    _save(out_dir, "hrv", tag, hrv)

    sleep = []
    for a, b in chunks(start, end, 28):
        sleep += [x for x in (g.get(f"/sleep-service/sleep/dailySleepSummariesByDate?startDate={a}&endDate={b}") or []) if x]
    _save(out_dir, "sleep", tag, sleep)

    daily = []
    for a, b in chunks(start, end, 28):
        d = g.get(f"/usersummary-service/v2/dailysummaries?startDate={a}&endDate={b}") or {}
        daily += [x for x in (d.get("data", []) if isinstance(d, dict) else d) if x]
    _save(out_dir, "daily", tag, daily)

    weight = []
    for a, b in chunks(start, end, 366):
        w = g.get(f"/weight-service/weight/range/{a}/{b}") or {}
        weight += w.get("dailyWeightSummaries", []) if isinstance(w, dict) else []
    _save(out_dir, "weight", tag, weight)

    acts, i = [], 0
    while True:
        page = g.get(f"/activitylist-service/activities/search/activities?start={i}&limit=100") or []
        if not page:
            break
        acts += page
        if page[-1].get("startTimeLocal", "")[:10] < start:
            break
        i += 100
    acts = [a for a in acts if start <= a.get("startTimeLocal", "")[:10] <= end]
    _save(out_dir, "activities", tag, acts)
    _save(out_dir, "fitnessage", tag, g.get(f"/fitnessage-service/fitnessage/v2/{end}"))
    _save(out_dir, "hrzones", tag, g.get("/biometric-service/heartRateZones/v2"))

    if details:
        out = {}
        for n, a in enumerate(acts):
            aid = a["activityId"]
            cache = os.path.join(work, "details", f"{aid}.json")
            if os.path.exists(cache):
                d = json.load(open(cache))
            else:
                try:
                    d = g.get(f"/activity-service/activity/{aid}") or {}
                except RuntimeError as e:
                    d = {"error": str(e)[:120]}
                d = {k: d.get(k) for k in ("activityTypeDTO", "eventTypeDTO", "summaryDTO", "splitSummaries", "isMultiSportParent", "error") if k in d}
                json.dump(d, open(cache, "w"))
            out[str(aid)] = d
            if n % 200 == 0:
                print(f"details {n}/{len(acts)}", file=sys.stderr, flush=True)
        _save(out_dir, "activity_details", tag, out)

    if fit:
        todo = [a["activityId"] for a in acts if (a.get("activityType") or {}).get("typeKey") in FIT_TYPES]
        out, done = {}, 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            for aid, m in ex.map(_fit_job, [g.token] * len(todo), todo, [work] * len(todo), chunksize=4):
                if m is not None:
                    out[str(aid)] = m
                done += 1
                if done % 100 == 0:
                    print(f"fit {done}/{len(todo)}", file=sys.stderr, flush=True)
        _save(out_dir, "fit_metrics", tag, out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--key-file", help="file holding the personal API key (default: $GARMIN_API_KEY)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    a = sub.add_parser("get"); a.add_argument("path"); a.add_argument("-o", "--out")
    b = sub.add_parser("archive"); b.add_argument("start"); b.add_argument("end")
    b.add_argument("-d", "--dir", default="garmin-archive")
    b.add_argument("--details", action="store_true", help="also fetch every activity's detail record")
    b.add_argument("--fit", action="store_true", help="also download every original FIT and extract metrics")
    b.add_argument("--work", help="resumable cache dir (default: a new temp dir)")
    b.add_argument("--workers", type=int, default=3)
    args = p.parse_args()

    key = open(args.key_file).read().strip() if args.key_file else api_key()
    if not key:
        sys.exit("No key: set GARMIN_API_KEY (environment secret) or pass --key-file.")
    g = Garmin(key)
    if args.cmd == "check":
        print(json.dumps(g.claims()))
    elif args.cmd == "get":
        data = g.get(args.path)
        text = json.dumps(data, indent=1, ensure_ascii=False) if not isinstance(data, bytes) else None
        if args.out:
            open(args.out, "w" if text else "wb").write(text if text else data)
        else:
            print(text if text else f"<{len(data)} bytes binary>")
    else:
        archive(g, args.start, args.end, args.dir, args.details, args.fit, args.work, args.workers)


if __name__ == "__main__":
    main()
