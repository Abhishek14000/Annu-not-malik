import json, os
P=json.load(open('photos.json'))
for k,v in P.items():
    for ext in ('jpg','jpeg','png','webp'):
        f=f'photos/{k}.{ext}'
        if os.path.exists(f): v['file']=f
s=open('page.template.html').read()
s=s.replace('__TIMELINE__',open('timeline.json').read()).replace('__MAP__',open('map.json').read()).replace('__PHOTOS__',json.dumps(P))
open('page.html','w').write(s)
