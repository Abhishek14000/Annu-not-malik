"""Build page.html in the current directory from page.template.html.

Inputs in the current directory: timeline.json, map.json.
Photo slots come from assets/manifest.json via assets.resolve_slots(): a slot
gets an image only if it passes the render gate; otherwise it stays a placeholder.
Pass --preview-unverified to also show selected-but-unverified images (watermarked).
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); VIDEO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import assets

preview = '--preview-unverified' in sys.argv
P = assets.resolve_slots(assets.load(), os.getcwd(), preview_unverified=preview)
s = open(os.path.join(HERE, 'page.template.html'), encoding='utf-8').read()
nm = os.path.relpath(os.path.join(VIDEO, 'node_modules'), os.getcwd()).replace(os.sep, '/')
s = s.replace('npm/node_modules/', nm + '/')
s = s.replace('__TIMELINE__', open('timeline.json', encoding='utf-8').read()).replace('__MAP__', open('map.json', encoding='utf-8').read()).replace('__PHOTOS__', json.dumps(P, ensure_ascii=False))
open('page.html', 'w', encoding='utf-8').write(s)
json.dump(P, open('slots_resolved.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
for k, v in P.items():
    print(f"slot {k}: {v.get('status') or 'placeholder'} ({v['reason']})")
