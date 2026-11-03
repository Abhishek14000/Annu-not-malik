"""Offline tests for retrieval (mock providers on localhost) and the render gate.

Run: python3 -m unittest discover -s tests -v   (from video/)
"""
import copy, http.server, io, json, os, shutil, sys, tempfile, threading, time, unittest
from collections import defaultdict

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(VIDEO, "src"))
import assets, retrieve_images as ri  # noqa: E402
import requests  # noqa: E402
from PIL import Image  # noqa: E402


def img_bytes(fmt, size):
    b = io.BytesIO(); Image.new("RGB", size, (120, 110, 100)).save(b, fmt); return b.getvalue()


JPG_BIG, PNG_SMALL = img_bytes("JPEG", (1200, 900)), img_bytes("PNG", (320, 240))


class Mock(http.server.BaseHTTPRequestHandler):
    hits = defaultdict(int); times = []

    def log_message(self, *a): pass

    def send(self, code, body=b"", ctype="application/json", headers=None):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]; Mock.hits[path] += 1; Mock.times.append(time.monotonic()); n = Mock.hits[path]
        base = f"http://127.0.0.1:{self.server.server_port}"
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        if path == "/ov/v1/images/":
            if "page_size=1&" in q + "&" and "q=stone" in q:  # probe
                return self.send(200, json.dumps({"results": []}).encode())
            if Mock.hits["ov_search"] == 0:
                Mock.hits["ov_search"] += 1
                return self.send(429, b"{}", headers={"Retry-After": "1"})
            Mock.hits["ov_search"] += 1
            res = [{"id": "aaa", "title": "Rock A", "creator": "Ann", "foreign_landing_url": base + "/landing/aaa", "url": base + "/img/a.jpg",
                    "thumbnail": base + "/img/a_thumb.png", "license": "by-sa", "license_version": "4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    "attribution": "\"Rock A\" by Ann is licensed under CC BY-SA 4.0.", "source": "flickr"},
                   {"id": "bbb", "title": "Rock B", "creator": "Bo", "foreign_landing_url": base + "/landing/bbb", "url": base + "/img/html",
                    "thumbnail": base + "/img/b_thumb.png", "license": "cc0", "license_version": "1.0", "source": "wikimedia"}]
            return self.send(200, json.dumps({"results": res}).encode())
        if path == "/ia/advancedsearch.php":
            if "rows=0" in q: return self.send(200, json.dumps({"response": {"docs": []}}).encode())
            return self.send(200, json.dumps({"response": {"docs": [{"identifier": "item1", "title": "Old plate", "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/"}]}}).encode())
        if path == "/ia/metadata/item1":
            if n == 1: return self.send(503)
            return self.send(200, json.dumps({"files": [{"name": "plate.jpg", "source": "original", "size": "5000"}, {"name": "plate_thumb.jpg", "source": "derivative", "size": "10"}], "metadata": {}}).encode())
        if path == "/ia/download/item1/plate.jpg": return self.send(200, JPG_BIG, "image/jpeg")
        if path == "/loc/photos/":
            if "c=1" in q and "q=stone" in q: return self.send(200, json.dumps({"results": []}).encode())
            return self.send(200, json.dumps({"results": [
                {"id": base + "/item/1/", "url": base + "/item/1/", "title": "Inscription", "image_url": [base + "/img/l_small.jpg#h=100&w=150", base + "/img/reset.jpg#h=900&w=1200"], "rights_advisory": "No known restrictions on publication."},
                {"id": base + "/item/2/", "url": base + "/item/2/", "title": "Restricted", "access_restricted": True, "image_url": [base + "/img/a.jpg"]}]}).encode())
        if path == "/img/reset.jpg":
            if n == 1:  # drop the connection once: transient
                self.wfile.flush(); self.connection.shutdown(2); return
            return self.send(200, JPG_BIG, "image/jpeg")
        if path == "/img/a.jpg": return self.send(200, JPG_BIG, "image/jpeg")
        if path in ("/img/a_thumb.png", "/img/b_thumb.png"): return self.send(200, PNG_SMALL, "image/png")
        if path == "/img/html": return self.send(200, b"<html>login</html>", "text/html")
        return self.send(404)


class RetrievalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Mock.hits.clear(); Mock.times.clear()
        self.tmp = tempfile.mkdtemp()
        m = assets.load()
        self.orig = copy.deepcopy(m)
        for sl in m["slots"].values():  # clean fixture: no selections or candidates
            sl.update(selected=None, candidates=[], download_status="not_attempted")
        self.man = os.path.join(self.tmp, "manifest.json"); assets.save(m, self.man)
        self.env = {k: os.environ.get(k) for k in ("OPENVERSE_API", "IA_BASE", "LOC_BASE")}

    def tearDown(self):
        shutil.rmtree(self.tmp)
        for k, v in self.env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def run_retrieval(self, providers="openverse,internet_archive,loc", bases=None):
        bases = bases or {"OPENVERSE_API": self.base + "/ov", "IA_BASE": self.base + "/ia", "LOC_BASE": self.base + "/loc"}
        os.environ.update(bases)
        return ri.main(["--manifest", self.man, "--out", os.path.join(self.tmp, "retrieved"), "--providers", providers, "--slots", "kalsi",
                        "--min-interval", "0.2", "--backoff", "0.05", "--retries", "3", "--timeout", "5", "--report", os.path.join(self.tmp, "rep.json")])

    def test_end_to_end_mock(self):
        rep = self.run_retrieval()
        self.assertEqual({p: v["status"] for p, v in rep["providers"].items()}, {"openverse": "reachable", "internet_archive": "reachable", "loc": "reachable"})
        m = assets.load(self.man); s = m["slots"]["kalsi"]
        by = {c["candidate_id"]: c for c in s["candidates"]}
        # 429 with Retry-After was retried
        self.assertGreaterEqual(Mock.hits["ov_search"], 2)
        self.assertEqual(by["openverse:aaa"]["download_status"], "downloaded")
        self.assertFalse(by["openverse:aaa"]["low_resolution"])
        # bbb: original was HTML -> fell back to thumbnail, flagged low-res
        self.assertEqual(by["openverse:bbb"]["download_status"], "downloaded")
        self.assertTrue(by["openverse:bbb"]["low_resolution"])
        self.assertTrue(by["openverse:bbb"]["download_url"].endswith("/img/b_thumb.png"))
        # IA: metadata 503 retried, original file chosen, licence parsed from URL but unverified
        ia = by["internet_archive:item1"]
        self.assertEqual(ia["download_status"], "downloaded"); self.assertTrue(ia["image_url"].endswith("/plate.jpg"))
        self.assertEqual(ia["licence"]["reported_name"], "Public Domain Mark 1.0")
        self.assertGreaterEqual(Mock.hits["/ia/metadata/item1"], 2)
        # LOC: largest image chosen, connection reset retried, restricted item skipped
        loc = [c for c in s["candidates"] if c["provider"] == "loc"]
        self.assertEqual(len(loc), 1); self.assertEqual(loc[0]["download_status"], "downloaded")
        self.assertTrue(loc[0]["image_url"].endswith("/img/reset.jpg"))
        # Nothing is verified or selected; slot still renders as a placeholder
        for c in s["candidates"]:
            self.assertIn(c["licence"]["status"], ("reported-unverified", "unknown"))
            self.assertFalse(c["authenticity"]["verified"])
            self.assertTrue(os.path.exists(os.path.join(VIDEO, c["file"]) if not os.path.isabs(c["file"]) else c["file"]))
            self.assertTrue(os.path.exists(os.path.join(VIDEO, c["file"]) + ".json"))
        self.assertIsNone(s["selected"])
        self.assertEqual(assets.slot_state(s)[0], "placeholder")
        self.assertIn("placeholder kept", s["download_status"])
        # files land under retrieved/<slot>/, not in manual/ or generated/
        for c in s["candidates"]:
            self.assertIn(os.path.join("retrieved", "kalsi"), c["file"])

    def test_rate_limit_interval(self):
        self.run_retrieval(providers="openverse")
        ts = Mock.times
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        self.assertTrue(gaps and min(gaps) >= 0.18, gaps)

    def test_unreachable_provider_keeps_placeholder(self):
        rep = self.run_retrieval(providers="openverse", bases={"OPENVERSE_API": "http://127.0.0.1:9"})
        self.assertEqual(rep["providers"]["openverse"]["status"], "unreachable")
        s = assets.load(self.man)["slots"]["kalsi"]
        self.assertEqual(s["candidates"], []); self.assertIsNone(s["selected"])
        self.assertIn("no provider reachable", s["download_status"])

    def test_blocked_not_retried(self):
        self.assertEqual(ri.classify_exception(requests.exceptions.ProxyError("Tunnel connection failed: 403 Forbidden")), "blocked")
        self.assertEqual(ri.classify_exception(requests.exceptions.ConnectTimeout("x")), "transient")
        calls = []
        h = ri.Http(min_interval=0, retries=3, sleep=lambda d: calls.append(d))
        h.s.get = lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.ProxyError("Tunnel connection failed: 403"))
        with self.assertRaises(ri.FetchError) as cm:
            h.get("https://blocked.example/")
        self.assertEqual(cm.exception.kind, "blocked"); self.assertEqual(calls, [])  # no backoff sleeps

    def test_review_gate(self):
        self.run_retrieval(providers="openverse")
        m = assets.load(self.man); s = m["slots"]["kalsi"]

        class A: pass
        a = A(); a.slot = "kalsi"; a.candidate_id = "openverse:aaa"
        assets.cmd_select(m, a)
        self.assertEqual(assets.slot_state(s)[0], "unverified")
        self.assertEqual(s["selected"]["licence"]["status"], "reported-unverified")
        page_dir = self.tmp
        self.assertNotIn("file", assets.resolve_slots(m, page_dir)["kalsi"])  # placeholder in normal render
        prev = assets.resolve_slots(m, page_dir, preview_unverified=True)["kalsi"]
        self.assertEqual(prev["status"], "unverified-preview")
        a.licence, a.licence_url, a.by, a.method, a.attribution = "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/", "Tester", "mock landing page", "Ann, CC BY-SA 4.0"
        assets.cmd_verify_licence(m, a)
        self.assertEqual(assets.slot_state(s)[0], "unverified")  # subject still unverified
        a.notes = "test"; assets.cmd_verify_subject(m, a)
        self.assertEqual(assets.slot_state(s)[0], "ready")
        self.assertIn("file", assets.resolve_slots(m, page_dir)["kalsi"])
        # tampering with the file drops it back to a placeholder
        f = os.path.join(VIDEO, s["selected"]["file"])
        with open(f, "ab") as fh: fh.write(b"x")
        self.assertEqual(assets.slot_state(s)[0], "placeholder")

    def test_existing_selection_preserved(self):
        m = assets.load(self.man)
        keep = {"origin": "manual", "file": "assets/manual/x.jpg", "licence": {"status": "reported-unverified"}, "authenticity": {"verified": True}}
        m["slots"]["kalsi"].update(selected=keep, download_status="manual_unverified"); assets.save(m, self.man)
        self.run_retrieval(providers="openverse")
        s = assets.load(self.man)["slots"]["kalsi"]
        self.assertEqual(s["selected"], keep); self.assertEqual(s["download_status"], "manual_unverified")
        self.assertTrue(s["candidates"])  # candidates are still recorded alongside

    def test_owner_accept(self):
        self.run_retrieval(providers="openverse")
        m = assets.load(self.man); s = m["slots"]["kalsi"]

        class A: pass
        a = A(); a.slot = "kalsi"; a.candidate_id = "openverse:aaa"
        assets.cmd_select(m, a)
        a.by, a.basis, a.attribution, a.licence_label = "Owner", "owner decision", "Photo: X / Wikimedia Commons", "CC BY-SA 4.0"
        assets.cmd_owner_accept(m, a)
        self.assertEqual(assets.slot_state(s)[0], "unverified")  # subject still required
        a.notes = "owner confirmed"; assets.cmd_verify_subject(m, a)
        st, why = assets.slot_state(s)
        self.assertEqual(st, "ready"); self.assertIn("NOT independently verified", why)
        r = assets.resolve_slots(m, self.tmp)["kalsi"]
        self.assertEqual(r["status"], "owner-accepted")
        self.assertEqual(r["credit"], "Photo: X / Wikimedia Commons · CC BY-SA 4.0")
        self.assertEqual(s["selected"]["licence"]["status"], "owner-accepted")  # never reported as verified

    def test_repo_manifest_untouched(self):
        self.run_retrieval(providers="openverse")
        self.assertEqual(assets.load(), self.orig)


if __name__ == "__main__":
    unittest.main()
