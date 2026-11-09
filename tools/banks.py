"""ROM 묶음(bank) 목록: 메인 코드 디버그 함수(0x80031E00~0x80032400)의 경계 상수로 만든다."""
import json,collections
from survey_rom import ROOT
from segments import segments,code_refs
rom=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes()
S=segments(rom)
B=sorted({r[5] for r in code_refs(rom,S[0]) if 0x80031e00<=r[0]<0x80032400 and r[2]==9 and 0x14b420<=r[5]<0x1000000})
streams=json.loads((ROOT/'manifests/compressed-streams.json').read_text())
refs=collections.defaultdict(set)
for s in S:
    for r in code_refs(rom,s):
        if not(0x80031e00<=r[0]<0x80032400) and r[5] in B:refs[r[5]].add((s['id'],hex(r[0])))
out=[]
for a,b in zip(B,B[1:]):
    st=[r for r in streams if a<=r['offset']<b]
    cov=sum(r['stored_size'] for r in st)
    out.append({'start':hex(a),'end':hex(b),'bytes':b-a,'lzss_streams':len(st),'lzss_coverage':round(cov/(b-a),3),
                'decoded_total':sum(r['decoded_size'] for r in st),'loaders':sorted(refs.get(a,[]))[:6]})
json.dump(out,open(ROOT/'manifests/banks.json','w'),indent=1)
for o in out:print(o['start'],o['end'],o['bytes'],'streams',o['lzss_streams'],'cov',o['lzss_coverage'],o['loaders'][:3])
