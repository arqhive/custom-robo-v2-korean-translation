"""3단계: 원문 대사의 줄 폭(px)·쪽당 줄 수 분포 (원본 글꼴 폭 표 기준)."""
import json,re,struct,collections
from survey_rom import ROOT
rom=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes()
N=1672;codes=struct.unpack_from('>%dH'%N,rom,0x3ee40);adv=rom[0x3ee40+2*N:0x3ee40+3*N]
ADV={bytes.fromhex('%04x'%c).decode('euc_jp','replace'):adv[i] for i,c in enumerate(codes)}
CTRL=re.compile(r'\$[A-Z]\d\d|\$[A-Z]|#[a-zA-Z]')
def width(s):return sum(ADV.get(c,12) for c in CTRL.sub('',s))
rows=json.loads((ROOT/'work/translation/source-texts.json').read_text(encoding='utf-8'))
debug=False;last=None;dl=[]
for r in rows:
    if r['script']!=last:debug=False;last=r['script']
    if r['source']=='全台詞':debug=True
    if r['kind']=='dialogue' and not debug:dl.append(r)
W=collections.Counter();L=collections.Counter();byface=collections.defaultdict(list);name=[]
for r in dl:
    s=r['source'];face='$F' in s
    for p in s.split('$P'):
        ls=p.split('$R');L[len(ls)]+=1
        for l in ls:
            w=width(l.replace('$A00',''))
            if '$A00' in l:name.append(w)
            byface[face].append(w);W[w]+=1
res={'dialogue_entries':len(dl),'lines_per_page':dict(sorted(L.items())),
     'max_width_with_face':max(byface[True]),'max_width_no_face':max(byface[False]) if byface[False] else None,
     'top_widths':sorted(W.items())[-8:],'max_width_line_with_name_excluding_name':max(name)}
print(json.dumps(res,ensure_ascii=False,indent=1))
