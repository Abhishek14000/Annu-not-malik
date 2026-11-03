#!/usr/bin/env python3
"""Asset manifest: render gate, scene report, and manual review commands.

The manifest (assets/manifest.json) is the single record of where every image
came from and what has been verified. Nothing here marks an image as verified
on its own; only the verify-licence and verify-subject commands do, and they
require a reviewer name.

Commands:
  report                         write ASSET_MANIFEST.md and ASSET_MANIFEST.csv
  status                         print each slot's state
  select SLOT CANDIDATE_ID       choose a downloaded candidate (stays unverified)
  add-manual SLOT FILE ...       copy an image you obtained yourself into assets/manual/
  verify-licence SLOT ...        record that a person checked the licence at the source
  verify-subject SLOT ...        record that a person checked the image shows the subject
  clear SLOT                     drop the selection; the slot goes back to a placeholder
"""
import argparse, csv, datetime, hashlib, json, os, shutil, sys

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(VIDEO, "assets", "manifest.json")
TIMELINE = os.path.join(VIDEO, "generated", "timeline.json")


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def load(path=MANIFEST):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(m, path=MANIFEST):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- render gate
def slot_state(slot):
    """Return (state, reason). States: placeholder, unverified, ready."""
    sel = slot.get("selected")
    if not sel:
        n = sum(1 for c in slot.get("candidates", []) if c.get("download_status") == "downloaded")
        return "placeholder", (f"{n} candidate(s) downloaded, none selected" if n else "no image selected")
    f = os.path.join(VIDEO, sel.get("file", ""))
    if not sel.get("file") or not os.path.isfile(f):
        return "placeholder", f"selected file missing: {sel.get('file')}"
    if sel.get("sha256") and sha256(f) != sel["sha256"]:
        return "placeholder", "selected file changed since selection (sha256 mismatch)"
    missing = []
    if (sel.get("licence") or {}).get("status") != "verified":
        missing.append("licence not verified")
    if not (sel.get("authenticity") or {}).get("verified"):
        missing.append("subject not verified")
    if missing:
        return "unverified", "; ".join(missing)
    return "ready", "licence and subject verified"


def credit_line(sel):
    lic = sel.get("licence") or {}
    name = lic.get("name") if lic.get("status") == "verified" else (f'{lic["reported_name"]} (reported, unverified)' if lic.get("reported_name") else "licence unverified")
    parts = [p for p in [sel.get("attribution") or "", name] if p]
    return " · ".join(parts)


def resolve_slots(m, page_dir, preview_unverified=False):
    """Slot data for page.template.html (PHOTOS). File paths are relative to page_dir."""
    out = {}
    for key, s in m["slots"].items():
        state, reason = slot_state(s)
        p = {"label": s["on_frame_label"], "note": s["on_frame_note"], "credit": "", "state": state, "reason": reason}
        if s.get("focus"):
            p["focus"] = s["focus"]  # CSS object-position for the crop
        use = state == "ready" or (state == "unverified" and preview_unverified)
        if use:
            sel = s["selected"]
            p["file"] = os.path.relpath(os.path.join(VIDEO, sel["file"]), page_dir)
            p["credit"] = credit_line(sel)
            p["status"] = "verified" if state == "ready" else "unverified-preview"
        out[key] = p
    return out


# ---------------------------------------------------------------- report
def narration(tl, n):
    beat = next(b for b in tl["beats"] if b["name"] == n["beat"])
    a, b = n["sentences"]
    ss = beat["sentences"][a:b + 1]
    return ss[0]["start"], ss[-1]["end"], " ".join(s["text"] for s in ss)


def fmt_t(x):
    return f"{int(x // 60)}:{x % 60:04.1f}"


def scene_rows(m, tl):
    rows = []
    for sc in m["scenes"]:
        t0, t1, text = narration(tl, sc["narration"])
        base = {"scene_id": sc["scene_id"], "name": sc["name"], "time": f"{fmt_t(t0)}–{fmt_t(t1)}",
                "narration_excerpt": text, "visual_description": sc["visual"], "asset": "", "search_queries": "",
                "source_url": "", "image_url": "", "licence_status": "", "attribution": "", "download_status": ""}
        if not sc["slots"]:
            comps = [m["components"][c] for c in sc["components"]]
            base.update(asset="generated graphics (" + ", ".join(sc["components"]) + ")",
                        source_url="; ".join(c.get("source_url", "") for c in comps if c.get("source_url")),
                        licence_status="; ".join(f'{k}: {m["components"][k]["licence"]["status"]}' for k in sc["components"] if "licence" in m["components"][k]),
                        attribution="; ".join(c["attribution"] for c in comps if c.get("attribution")),
                        download_status="n/a (generated)")
            rows.append(base)
            continue
        for ref in sc["slots"]:
            s = m["slots"][ref["slot"]]
            state, reason = slot_state(s)
            sel = s.get("selected") or {}
            r = dict(base)
            r.update(asset=f'photo slot "{ref["slot"]}" ({ref["role"]})',
                     search_queries=" | ".join(s["search_queries"]["general"]),
                     source_url=sel.get("source_url", "") or "; ".join(l["url"] for l in s.get("reference_leads", [])[:1]) + (" (lead, unopened)" if s.get("reference_leads") else ""),
                     image_url=sel.get("image_url", ""),
                     licence_status=((sel.get("licence") or {}).get("status", "") + (f' ({(sel.get("licence") or {}).get("name") or (sel.get("licence") or {}).get("reported_name") or ""})' if sel else "")) if sel else "no image",
                     attribution=sel.get("attribution", ""),
                     download_status=f'{s.get("download_status", "not_attempted")}; renders as {state} ({reason})')
            rows.append(r)
    return rows


def write_report(m, tl, md_path, csv_path):
    rows = scene_rows(m, tl)
    cols = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    L = ["# Asset manifest: scene by scene", "",
         f"Generated from `assets/manifest.json` and `generated/timeline.json` by `src/assets.py report`. Don't edit by hand.", "",
         "A photo slot renders a real image only when its licence **and** its subject have been verified by a named person. Otherwise it renders as a labelled placeholder.", "",
         "## Scenes", "",
         "| Scene | Time | Narration excerpt | Visual | Asset | Search queries | Source URL | Image URL | Licence status | Attribution | Download status |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| " + " | ".join(esc(x) for x in [f'{r["scene_id"]} {r["name"]}', r["time"], r["narration_excerpt"], r["visual_description"], r["asset"], r["search_queries"], r["source_url"], r["image_url"], r["licence_status"], r["attribution"], r["download_status"]]) + " |")
    L += ["", "## Photo slots", ""]
    for key, s in m["slots"].items():
        state, reason = slot_state(s)
        L += [f"### `{key}`: {state}", "", f"- **Intended subject:** {s['intended_subject']}",
              f"- **Renders as:** {state} ({reason})", f"- **Download status:** {s.get('download_status', 'not_attempted')}",
              "- **Search queries:** " + "; ".join(f"{k}: " + ", ".join(f'“{q}”' for q in v) for k, v in s["search_queries"].items())]
        if s.get("reference_leads"):
            L.append("- **Leads (not verified):** " + "; ".join(f"<{l['url']}> ({l['status']})" for l in s["reference_leads"]))
        cands = s.get("candidates", [])
        if cands:
            L += ["", "| Candidate | Provider | Title | Source URL | Image URL | Licence (as reported) | Status | File |", "|---|---|---|---|---|---|---|---|"]
            for c in cands:
                lic = c.get("licence", {})
                L.append("| " + " | ".join(esc(x) for x in [c["candidate_id"], c["provider"], c.get("title", ""), c.get("source_url", ""), c.get("image_url", ""), f'{lic.get("status", "unknown")}: {lic.get("reported_name") or "—"}', c.get("download_status", ""), c.get("file", "")]) + " |")
        L.append("")
    L += ["## Generated and third-party components", ""]
    for k, c in m["components"].items():
        lic = c.get("licence", {})
        L.append(f"- **{k}** ({c['kind']}): {c.get('source') or c.get('made_by', '')}. Licence: {lic.get('status', 'n/a')}" + (f" ({lic.get('reported_name')})" if lic.get("reported_name") else "") + (f". {lic['notes']}" if lic.get("notes") else "") + (f" Attribution: {c['attribution']}" if c.get("attribution") else ""))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return rows


# ---------------------------------------------------------------- review commands
def cmd_select(m, a):
    s = m["slots"][a.slot]
    c = next((c for c in s.get("candidates", []) if c["candidate_id"] == a.candidate_id), None)
    if not c:
        sys.exit(f"no candidate {a.candidate_id!r} in slot {a.slot}")
    if c.get("download_status") != "downloaded":
        sys.exit(f"candidate {a.candidate_id} has no downloaded file ({c.get('download_status')})")
    s["selected"] = {"origin": "retrieved", "candidate_id": c["candidate_id"], "file": c["file"], "sha256": c.get("sha256"),
                     "source_url": c.get("source_url", ""), "image_url": c.get("image_url", ""), "download_url": c.get("download_url", ""),
                     "title": c.get("title", ""), "creator": c.get("creator", ""), "attribution": c.get("attribution_reported", ""),
                     "licence": dict(c.get("licence", {"status": "unknown"})), "authenticity": {"verified": False},
                     "low_resolution": c.get("low_resolution", False), "selected_on": now()}
    if s["selected"]["licence"].get("status") == "verified":  # never inherit verification
        s["selected"]["licence"]["status"] = "reported-unverified"
    s["download_status"] = "selected_unverified"


def cmd_add_manual(m, a):
    s = m["slots"][a.slot]
    ext = os.path.splitext(a.file)[1].lower() or ".jpg"
    rel = os.path.join("assets", "manual", f"{a.slot}{ext}")
    dst = os.path.join(VIDEO, rel)
    if os.path.abspath(a.file) != os.path.abspath(dst):
        shutil.copyfile(a.file, dst)
    lic = {"status": "reported-unverified" if a.licence else "unknown"}
    if a.licence:
        lic.update(reported_name=a.licence, reported_url=a.licence_url or "", reported_by="person adding the file")
    s["selected"] = {"origin": "manual", "file": rel, "sha256": sha256(dst), "source_url": a.source_url, "image_url": a.image_url or "",
                     "title": a.title or "", "creator": a.creator or "", "attribution": a.attribution or "",
                     "licence": lic, "authenticity": {"verified": False}, "selected_on": now()}
    with open(dst + ".json", "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in s["selected"].items()}, f, indent=2, ensure_ascii=False)
    s["download_status"] = "manual_unverified"


def cmd_verify_licence(m, a):
    sel = m["slots"][a.slot].get("selected") or sys.exit("select an image first")
    if not sel.get("source_url"):
        sys.exit("the selection has no source_url; a licence can only be verified against a source page")
    sel["licence"].update(status="verified", name=a.licence, url=a.licence_url, verified_by=a.by, verified_on=now(), method=a.method)
    sel["attribution"] = a.attribution
    _refresh(m, a.slot)


def cmd_verify_subject(m, a):
    sel = m["slots"][a.slot].get("selected") or sys.exit("select an image first")
    sel["authenticity"] = {"verified": True, "verified_by": a.by, "verified_on": now(), "notes": a.notes}
    _refresh(m, a.slot)


def _refresh(m, slot):
    s = m["slots"][slot]
    st, _ = slot_state(s)
    s["download_status"] = {"ready": "ready", "unverified": "selected_unverified", "placeholder": s.get("download_status")}[st]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=MANIFEST)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report"); r.add_argument("--timeline", default=TIMELINE)
    sub.add_parser("status")
    p = sub.add_parser("select"); p.add_argument("slot"); p.add_argument("candidate_id")
    p = sub.add_parser("add-manual"); p.add_argument("slot"); p.add_argument("file")
    p.add_argument("--source-url", required=True, help="page the image came from, e.g. its Commons file page")
    p.add_argument("--image-url"); p.add_argument("--title"); p.add_argument("--creator"); p.add_argument("--attribution")
    p.add_argument("--licence", help="licence as stated by the source (stays unverified)"); p.add_argument("--licence-url")
    p = sub.add_parser("verify-licence"); p.add_argument("slot")
    p.add_argument("--licence", required=True); p.add_argument("--licence-url", required=True)
    p.add_argument("--attribution", required=True, help="exact credit line to print on frame")
    p.add_argument("--by", required=True, help="name of the person who checked"); p.add_argument("--method", required=True, help="what was checked, e.g. 'Commons file page, licence section'")
    p = sub.add_parser("verify-subject"); p.add_argument("slot")
    p.add_argument("--by", required=True); p.add_argument("--notes", required=True, help="how the subject was confirmed")
    p = sub.add_parser("clear"); p.add_argument("slot")
    a = ap.parse_args()
    m = load(a.manifest)
    if a.cmd == "report":
        tl = json.load(open(a.timeline, encoding="utf-8"))
        rows = write_report(m, tl, os.path.join(VIDEO, "ASSET_MANIFEST.md"), os.path.join(VIDEO, "ASSET_MANIFEST.csv"))
        print(f"wrote ASSET_MANIFEST.md / .csv ({len(rows)} rows)")
        return
    if a.cmd == "status":
        for k, s in m["slots"].items():
            st, why = slot_state(s)
            print(f"{k:8} {st:12} {why}  [download_status={s.get('download_status')}, candidates={len(s.get('candidates', []))}]")
        return
    if a.slot not in m["slots"]:
        sys.exit(f"unknown slot {a.slot!r}; slots: {', '.join(m['slots'])}")
    {"select": cmd_select, "add-manual": cmd_add_manual, "verify-licence": cmd_verify_licence,
     "verify-subject": cmd_verify_subject, "clear": lambda m, a: m["slots"][a.slot].update(selected=None, download_status="not_attempted")}[a.cmd](m, a)
    save(m, a.manifest)
    st, why = slot_state(m["slots"][a.slot])
    print(f"{a.slot}: {st} ({why})")


if __name__ == "__main__":
    main()
