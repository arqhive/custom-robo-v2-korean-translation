"""문자열을 위치상 연속 덩어리로 묶어 요약 (분류 판단용)."""
import json,collections
from survey_rom import ROOT
rows=json.loads((ROOT/'work/translation/raw-text-all.json').read_text(encoding='utf-8'))
v1=json.loads(open(r'G:/KoreanTranslation/GPT초벌작/[N64]커스텀로보/work/translation/raw-text-classified.json',encoding='utf-8').read())
v1s=collections.defaultdict(set)
for x in v1:v1s[x['source']].add('D' if x['scope']=='display_text' else 'I')
runs=[];cur=[]
for r in sorted(rows,key=lambda r:r['rom_offset']):
    if cur and (r['rom_offset']-(cur[-1]['rom_offset']+cur[-1]['bytes'])>0x100 or r['area']!=cur[-1]['area']):runs.append(cur);cur=[]
    cur.append(r)
runs.append(cur)
out=[]
for i,run in enumerate(runs):
    k=collections.Counter(''.join(sorted(v1s.get(r['source'],{'N'}))) for r in run)
    out.append({'run':i,'area':run[0]['area'],'start':hex(run[0]['rom_offset']),'end':hex(run[-1]['rom_offset']+run[-1]['bytes']),'count':len(run),'v1':dict(k),
                'sample':[r['source'][:24] for r in (run[:4]+run[len(run)//2:len(run)//2+2]+run[-2:])]})
(ROOT/'work/translation/text-runs.json').write_text(json.dumps(out,ensure_ascii=False,indent=0),encoding='utf-8')
for o in out:print(o['run'],o['area'],o['start'],o['count'],o['v1'],' | '.join(o['sample']))
