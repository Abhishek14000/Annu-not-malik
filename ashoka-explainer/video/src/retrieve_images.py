#!/usr/bin/env python3
"""Optional image retrieval: Openverse, Internet Archive and Library of Congress.

What it does, in order:
  1. Probes each provider with one small request. Unreachable providers are skipped.
  2. Searches each slot's queries and records candidate metadata (source page, image URL,
     creator, licence *as reported*).
  3. Downloads up to --per-slot candidates per slot into assets/retrieved/<slot>/, each with a
     .json sidecar, and validates them (content type, size, decodable, dimensions).
  4. Adds the candidates to assets/manifest.json. It never selects or verifies anything:
     slots stay placeholders until a person runs `assets.py select / verify-licence / verify-subject`.

Network behaviour:
  - Per-host minimum interval between requests (--min-interval, default 2s) so we stay under
    each provider's anonymous rate limit.
  - Retries transient failures (timeouts, connection resets, 429, 500, 502, 503, 504) with
    exponential backoff and jitter, honouring Retry-After (capped).
  - Does not retry policy blocks (proxy CONNECT 403), 401/403/404 or other client errors.
  - Generic User-Agent; no personal data is sent.

Licence rule: every licence recorded here has status 'reported-unverified' or 'unknown'.
"""
import argparse, datetime, hashlib, io, json, os, random, re, sys, time, urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__)); VIDEO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import assets  # noqa: E402

UA = "ashoka-explainer-pipeline/1.0 (educational video; image search)"
TRANSIENT_STATUS = {429, 500, 502, 503, 504}
MAX_BYTES = 30 * 1024 * 1024
MIN_SIDE = 800  # below this the image is flagged low_resolution


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


class FetchError(Exception):
    def __init__(self, kind, msg, status=None):
        super().__init__(msg); self.kind, self.status = kind, status  # kind: blocked | transient | client | invalid


def classify_exception(e):
    """Map a requests exception to blocked/transient."""
    s = str(e)
    if isinstance(e, requests.exceptions.ProxyError) or "Tunnel connection failed: 403" in s or "CONNECT tunnel failed" in s:
        return "blocked"
    if isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError)):
        return "transient"
    return "client"


class Http:
    def __init__(self, min_interval=2.0, retries=4, backoff=2.0, timeout=20, max_retry_after=60, log=None, sleep=time.sleep):
        self.s = requests.Session(); self.s.headers["User-Agent"] = UA
        self.min_interval, self.retries, self.backoff, self.timeout, self.max_retry_after = min_interval, retries, backoff, timeout, max_retry_after
        self.last = {}; self.log = log if log is not None else []; self.sleep = sleep

    def _wait_turn(self, host):
        gap = time.monotonic() - self.last.get(host, -1e9)
        if gap < self.min_interval:
            self.sleep(self.min_interval - gap)
        self.last[host] = time.monotonic()

    def get(self, url, params=None, stream=False, accept=None):
        host = urllib.parse.urlsplit(url).netloc
        for attempt in range(self.retries + 1):
            self._wait_turn(host)
            entry = {"t": now(), "url": url, "params": params, "attempt": attempt + 1}
            try:
                r = self.s.get(url, params=params, timeout=self.timeout, stream=stream, headers={"Accept": accept} if accept else None)
            except requests.RequestException as e:
                kind = classify_exception(e)
                entry.update(result=kind, error=str(e)[:300]); self.log.append(entry)
                if kind == "transient" and attempt < self.retries:
                    self.sleep(self._delay(attempt)); continue
                raise FetchError(kind, f"{kind}: {str(e)[:200]}")
            entry.update(result=r.status_code); self.log.append(entry)
            if r.status_code in TRANSIENT_STATUS and attempt < self.retries:
                ra = r.headers.get("Retry-After")
                d = min(float(ra), self.max_retry_after) if ra and ra.replace(".", "", 1).isdigit() else self._delay(attempt)
                r.close(); self.sleep(d); continue
            if r.status_code >= 400:
                kind = "transient" if r.status_code in TRANSIENT_STATUS else "client"
                r.close(); raise FetchError(kind, f"HTTP {r.status_code} for {url}", r.status_code)
            return r
        raise FetchError("transient", "retries exhausted")

    def _delay(self, attempt):
        return self.backoff * (2 ** attempt) * (0.75 + random.random() * 0.5)

    def json(self, url, params=None):
        r = self.get(url, params=params, accept="application/json")
        try:
            return r.json()
        except ValueError:
            raise FetchError("invalid", f"non-JSON response from {url}")


# ---------------------------------------------------------------- providers
OPENVERSE_LICENCES = {"by": "CC BY", "by-sa": "CC BY-SA", "by-nd": "CC BY-ND", "by-nc": "CC BY-NC", "by-nc-sa": "CC BY-NC-SA",
                      "by-nc-nd": "CC BY-NC-ND", "cc0": "CC0", "pdm": "Public Domain Mark", "sampling+": "CC Sampling+", "nc-sampling+": "CC NC-Sampling+"}


class Openverse:
    name = "openverse"

    def __init__(self, http, base=None, licences="by,by-sa,cc0,pdm"):
        self.h, self.base, self.licences = http, (base or os.environ.get("OPENVERSE_API") or "https://api.openverse.org").rstrip("/"), licences

    def probe(self):
        self.h.json(f"{self.base}/v1/images/", {"q": "stone", "page_size": 1})

    def search(self, q, n):
        d = self.h.json(f"{self.base}/v1/images/", {"q": q, "page_size": n, "license": self.licences, "mature": "false"})
        out = []
        for r in d.get("results", []):
            lic = r.get("license") or ""
            out.append({
                "provider": self.name, "provider_id": r["id"], "title": r.get("title") or "", "creator": r.get("creator") or "",
                "creator_url": r.get("creator_url") or "", "source_url": r.get("foreign_landing_url") or "", "image_url": r.get("url") or "",
                "fallback_url": r.get("thumbnail") or f"{self.base}/v1/images/{r['id']}/thumb/", "width": r.get("width"), "height": r.get("height"),
                "upstream_source": r.get("source") or r.get("provider") or "",
                "licence": {"status": "reported-unverified" if lic else "unknown", "reported_name": (OPENVERSE_LICENCES.get(lic, lic.upper()) + (f" {r['license_version']}" if r.get("license_version") else "")).strip(),
                            "reported_url": r.get("license_url") or "", "reported_by": "Openverse API"},
                "attribution_reported": r.get("attribution") or ""})
        return out


class InternetArchive:
    name = "internet_archive"

    def __init__(self, http, base=None):
        self.h, self.base = http, (base or os.environ.get("IA_BASE") or "https://archive.org").rstrip("/")

    def probe(self):
        self.h.json(f"{self.base}/advancedsearch.php", {"q": "stone", "rows": 0, "output": "json"})

    def search(self, q, n):
        d = self.h.json(f"{self.base}/advancedsearch.php", {"q": f"({q}) AND mediatype:(image)", "fl[]": ["identifier", "title", "creator", "licenseurl", "rights", "date"], "rows": n, "output": "json"})
        out = []
        for doc in d.get("response", {}).get("docs", []):
            ident = doc["identifier"]
            lic_url = doc.get("licenseurl") or ""
            rights = doc.get("rights") or ""
            rights = rights if isinstance(rights, str) else "; ".join(rights)
            c = {"provider": self.name, "provider_id": ident, "title": _s(doc.get("title")), "creator": _s(doc.get("creator")),
                 "source_url": f"{self.base}/details/{ident}", "image_url": "", "date": _s(doc.get("date")),
                 "licence": {"status": "reported-unverified" if (lic_url or rights) else "unknown", "reported_name": _cc_name(lic_url) or rights[:200],
                             "reported_url": lic_url, "reported_by": "Internet Archive item metadata"},
                 "attribution_reported": ""}
            out.append(c)
        return out

    def resolve_image(self, c):
        """Pick the largest original JPEG/PNG from the item's file list."""
        md = self.h.json(f"{self.base}/metadata/{urllib.parse.quote(c['provider_id'])}")
        files = [f for f in md.get("files", []) if re.search(r"\.(jpe?g|png)$", f.get("name", ""), re.I) and f.get("source", "original") == "original"]
        files = [f for f in files if int(f.get("size") or 0) <= MAX_BYTES] or files
        if not files:
            raise FetchError("invalid", "no original JPEG/PNG in item")
        f = max(files, key=lambda f: int(f.get("size") or 0))
        c["image_url"] = f"{self.base}/download/{urllib.parse.quote(c['provider_id'])}/{urllib.parse.quote(f['name'])}"
        meta = md.get("metadata", {})
        if not c["licence"].get("reported_url") and meta.get("licenseurl"):
            c["licence"].update(status="reported-unverified", reported_url=meta["licenseurl"], reported_name=_cc_name(meta["licenseurl"]))


class LibraryOfCongress:
    name = "loc"

    def __init__(self, http, base=None):
        self.h, self.base = http, (base or os.environ.get("LOC_BASE") or "https://www.loc.gov").rstrip("/")

    def probe(self):
        self.h.json(f"{self.base}/photos/", {"q": "stone", "fo": "json", "c": 1})

    def search(self, q, n):
        d = self.h.json(f"{self.base}/photos/", {"q": q, "fo": "json", "c": n})
        out = []
        for r in d.get("results", []):
            if r.get("access_restricted"):
                continue
            imgs = [u for u in (r.get("image_url") or []) if isinstance(u, str)]
            img = _largest_loc(imgs)
            rights = r.get("rights_advisory") or r.get("rights") or ""
            rights = rights if isinstance(rights, str) else "; ".join(rights)
            out.append({"provider": self.name, "provider_id": r.get("id") or r.get("url"), "title": _s(r.get("title")),
                        "creator": _s(r.get("contributor") or r.get("contributor_names") or ""), "source_url": r.get("url") or r.get("id") or "",
                        "image_url": img, "date": _s(r.get("date")),
                        "licence": {"status": "reported-unverified" if rights else "unknown", "reported_name": rights[:200], "reported_url": "",
                                    "reported_by": "Library of Congress search result"},
                        "attribution_reported": ""})
        return out


def _s(v):
    return "; ".join(map(str, v)) if isinstance(v, list) else (str(v) if v else "")


def _cc_name(url):
    m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-+]+)/?([\d.]+)?", url or "")
    if not m:
        return ""
    code, ver = m.group(2), m.group(3) or ""
    name = {"zero": "CC0", "mark": "Public Domain Mark"}.get(code) or "CC " + code.upper()
    return f"{name} {ver}".strip()


def _largest_loc(urls):
    if not urls:
        return ""
    def width(u):
        m = re.search(r"#h=(\d+)&w=(\d+)", u) or re.search(r"pct:(\d+)", u)
        return int(m.groups()[-1]) if m else 0
    return max(urls, key=width).split("#")[0]


PROVIDERS = {"openverse": Openverse, "internet_archive": InternetArchive, "loc": LibraryOfCongress}


# ---------------------------------------------------------------- download
def download(http, url, dest_base):
    """Download url to dest_base + ext. Returns dict with file info. Raises FetchError."""
    from PIL import Image
    r = http.get(url, stream=True)
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if not ctype.startswith("image/"):
        r.close(); raise FetchError("invalid", f"not an image (Content-Type {ctype or 'missing'})")
    buf = io.BytesIO()
    for chunk in r.iter_content(1 << 16):
        buf.write(chunk)
        if buf.tell() > MAX_BYTES:
            r.close(); raise FetchError("invalid", "file larger than 30 MB")
    data = buf.getvalue()
    try:
        im = Image.open(io.BytesIO(data)); im.verify()
        im = Image.open(io.BytesIO(data)); w, h = im.size; fmt = (im.format or "").lower()
    except Exception as e:
        raise FetchError("invalid", f"not a decodable image: {e}")
    ext = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif", "tiff": ".tif"}.get(fmt, ".img")
    if ext in (".tif", ".img", ".gif"):
        raise FetchError("invalid", f"unsupported format for render: {fmt}")
    path = dest_base + ext
    with open(path, "wb") as f:
        f.write(data)
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "width": w, "height": h, "content_type": ctype, "final_url": r.url}


def safe_id(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s))[-80:].strip("_") or "item"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=assets.MANIFEST)
    ap.add_argument("--out", default=os.path.join(VIDEO, "assets", "retrieved"))
    ap.add_argument("--providers", default="openverse,internet_archive,loc")
    ap.add_argument("--slots", help="comma list (default: all)")
    ap.add_argument("--per-query", type=int, default=5, help="search results requested per query")
    ap.add_argument("--per-slot", type=int, default=3, help="max downloads per slot per provider")
    ap.add_argument("--min-interval", type=float, default=2.0, help="seconds between requests to the same host")
    ap.add_argument("--retries", type=int, default=4); ap.add_argument("--backoff", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--metadata-only", action="store_true", help="search but don't download")
    ap.add_argument("--report", default=os.path.join(VIDEO, "build", "retrieval_report.json"))
    a = ap.parse_args(argv)

    m = assets.load(a.manifest)
    log = []
    http = Http(a.min_interval, a.retries, a.backoff, a.timeout, log=log)
    report = {"started": now(), "providers": {}, "slots": {}}
    live = []
    for name in [p.strip() for p in a.providers.split(",") if p.strip()]:
        prov = PROVIDERS[name](http)
        try:
            prov.probe(); live.append(prov); report["providers"][name] = {"status": "reachable", "base": prov.base}
        except FetchError as e:
            report["providers"][name] = {"status": "unreachable", "kind": e.kind, "reason": str(e), "base": prov.base}
        print(f"probe {name}: {report['providers'][name]['status']}" + (f" ({report['providers'][name].get('reason')})" if name not in [p.name for p in live] else ""), flush=True)

    slots = a.slots.split(",") if a.slots else list(m["slots"])
    for key in slots:
        s = m["slots"][key]
        existing = {c["candidate_id"]: c for c in s.get("candidates", [])}
        srep = {"downloaded": 0, "failed": 0, "searched": 0, "errors": []}
        for prov in live:
            queries = s["search_queries"].get(prov.name) or s["search_queries"]["general"]
            got = 0
            for q in queries:
                if got >= a.per_slot:
                    break
                try:
                    results = prov.search(q, a.per_query); srep["searched"] += 1
                except FetchError as e:
                    srep["errors"].append(f"{prov.name} search {q!r}: {e}")
                    if e.kind == "blocked":
                        break
                    continue
                for c in results:
                    if got >= a.per_slot:
                        break
                    cid = f"{prov.name}:{c['provider_id']}"
                    if cid in existing and existing[cid].get("download_status") == "downloaded" and os.path.exists(os.path.join(VIDEO, existing[cid]["file"])):
                        continue
                    c.update(candidate_id=cid, slot=key, query=q, retrieved_at=now(), authenticity={"verified": False, "note": "search result; subject not confirmed"})
                    if a.metadata_only:
                        c["download_status"] = "metadata_only"; existing[cid] = c; continue
                    os.makedirs(os.path.join(a.out, key), exist_ok=True)
                    base = os.path.join(a.out, key, safe_id(f"{prov.name}-{c['provider_id']}"))
                    try:
                        if prov.name == "internet_archive" and not c["image_url"]:
                            prov.resolve_image(c)
                        urls = [u for u in [c.get("image_url"), c.get("fallback_url")] if u]
                        info, last_err = None, None
                        for u in urls:
                            try:
                                info = download(http, u, base); c["download_url"] = u
                                c["low_resolution"] = (u != c.get("image_url")) or min(info["width"], info["height"]) < MIN_SIDE
                                break
                            except FetchError as e:
                                last_err = e
                        if not info:
                            raise last_err or FetchError("invalid", "no image URL")
                        c.update(file=os.path.relpath(info["path"], VIDEO), sha256=info["sha256"], bytes=info["bytes"], pixel_width=info["width"],
                                 pixel_height=info["height"], content_type=info["content_type"], download_status="downloaded")
                        with open(info["path"] + ".json", "w", encoding="utf-8") as f:
                            json.dump(c, f, indent=2, ensure_ascii=False)
                        got += 1; srep["downloaded"] += 1
                    except FetchError as e:
                        c["download_status"] = f"failed: {e}"; srep["failed"] += 1
                    existing[cid] = c
        s["candidates"] = list(existing.values())
        n_ok = sum(1 for c in s["candidates"] if c.get("download_status") == "downloaded")
        if s.get("selected"):
            pass  # never touch an existing selection
        elif not live:
            s["download_status"] = "failed: no provider reachable (placeholder kept)"
        elif n_ok:
            s["download_status"] = f"candidates_downloaded ({n_ok}); awaiting review (placeholder kept)"
        else:
            s["download_status"] = "no usable candidates (placeholder kept)"
        s["last_retrieval"] = now()
        srep["download_status"] = s["download_status"]; report["slots"][key] = srep
        print(f"slot {key}: {s['download_status']}", flush=True)

    assets.save(m, a.manifest)
    report["finished"] = now(); report["requests"] = log
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    with open(a.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "retrieval_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in report.items() if k != "requests"}, ensure_ascii=False) + "\n")
    return report


if __name__ == "__main__":
    main()
