"""4단계: 스크립트 밖 문자열 전수 목록 (세그먼트 데이터·코드 영역, 글자 든 무압축 묶음)."""
import json,re,collections
from survey_rom import ROOT
from segments import segments
rom=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes()
S=segments(rom)
areas=[(f"seg{s['id']}",s['data_rom'],s['rom_end']) for s in S]
areas+=[('robo_moves',0x3fae70,0x41f7d0),('battle_setup',0x980340,0x9b5980),('demo_setup',0x9b5980,0x9b6600)]
pat=re.compile(rb'(?:[\xa1-\xfe][\xa1-\xfe]|[\x20-\x7e\n]){1,}\x00')
rows=[]
for name,a,b in areas:
    for m in pat.finditer(rom,a,b):
        t=m.group()[:-1]
        if m.start()>a and rom[m.start()-1] not in (0,):continue   # must start after NUL
        try:u=t.decode('euc_jp')
        except UnicodeDecodeError:continue
        if not re.search('[ぁ-ゟァ-ヺ一-鿿]',u):continue
        jp=re.findall('[ぁ-ゟァ-ヺ一-鿿]',u)
        if not re.search('[ぁ-ゟァ-ヺ]',u) and len(jp)<2:continue
        if any(ord(c)<32 and c!=chr(10) for c in u):continue
        rows.append({'id':f'R{m.start():08X}','area':name,'rom_offset':m.start(),'bytes':len(t),'source':u})
cnt=collections.Counter(r['area'] for r in rows)
src=collections.defaultdict(set)
for r in rows:src[r['source']].add(r['area'])
shared=[s for s,a in src.items() if len(a)>1]
for r in rows:r['shared_areas']=sorted(src[r['source']]) if len(src[r['source']])>1 else []
(ROOT/'work/translation').mkdir(parents=True,exist_ok=True)
(ROOT/'work/translation/raw-text-all.json').write_text(json.dumps(rows,ensure_ascii=False,indent=0),encoding='utf-8')
rep={'strings':len(rows),'unique':len(src),'per_area':dict(cnt),'sources_shared_between_areas':len(shared)}
(ROOT/'manifests/raw-text-extraction.json').write_text(json.dumps(rep,ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps(rep,ensure_ascii=False,indent=1));print(shared[:40])
