import json,sys
rows=json.load(open('../work/translation/raw-text-all.json',encoding='utf-8'))
area=sys.argv[1];gap=int(sys.argv[2]) if len(sys.argv)>2 else 0x80
u=[r for r in rows if r['rule']=='unknown' and r['area']==area]
runs=[];cur=[]
for r in sorted(u,key=lambda r:r['rom_offset']):
    if cur and r['rom_offset']-cur[-1]['rom_offset']>gap:runs.append(cur);cur=[]
    cur.append(r)
if cur:runs.append(cur)
for run in runs:print(hex(run[0]['rom_offset']),len(run),' | '.join(x['source'][:16] for x in run[:9]))
