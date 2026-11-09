"""4단계: ROM 0~16MB 전체 구역 지도 (빈 바이트 없이)."""
import json,re,collections
from survey_rom import ROOT
from segments import segments
rom=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes()
S=segments(rom)
streams=json.loads((ROOT/'manifests/compressed-streams.json').read_text())
regions=[(0,0x40,'header','ROM 헤더'),(0x40,0x1000,'boot','IPL3 부트 코드'),(0x1000,0x1060,'entry','진입 코드(0x80025C00)')]
for s in S:regions.append((s['rom_start'],s['rom_end'],'segment',f"세그먼트 {s['id']} (텍스트 0x{s['ram']:08X}~0x{s['text_end']:08X}, 데이터 ~0x{s['data_end']:08X})"))
regions.append((0x14b420,0x14b420+1672*18,'font','글꼴 1bpp 1,672자'))
for r in streams:regions.append((r['offset'],r['offset']+r['stored_size'],'lzss',f"압축 스트림 해제 {r['decoded_size']}바이트"))
regions.append((0x980340,0x9b5980,'battle_table','배틀 설정 표(0x238바이트 레코드)'))
regions.append((0x9b6600,0xfad5f0,'audio','사운드 뱅크(N64 PtrTablesV2)'))
regions.sort()
def describe(a,b):
    d=rom[a:b]
    if not d.strip(b'\0'):return 'zero','0x00 채움'
    if not d.strip(b'\xff'):return 'ff','0xFF 채움'
    t=len(re.findall(rb'[\xa1-\xfe][\xa1-\xfe]',d))
    z=d.count(0)
    return 'data',f'미분류 데이터(EUC 2바이트 쌍 {t}, 0바이트 {z*100//len(d)}%)'
full=[];pos=0
for a,b,k,n in regions:
    if a>pos:
        kk,nn=describe(pos,a);full.append((pos,a,kk,nn))
    if a<pos:assert b<=pos or k=='lzss',(hex(a),hex(pos),n)
    full.append((max(a,pos),b,k,n));pos=max(pos,b)
if pos<len(rom):kk,nn=describe(pos,len(rom));full.append((pos,len(rom),kk,nn))
assert sum(b-a for a,b,_,_ in full)==len(rom)
cnt=collections.Counter();size=collections.Counter()
for a,b,k,n in full:cnt[k]+=1;size[k]+=b-a
json.dump([{'start':hex(a),'end':hex(b),'bytes':b-a,'kind':k,'note':n} for a,b,k,n in full],open(ROOT/'manifests/region-map.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
for k in cnt:print(k,cnt[k],size[k])
for a,b,k,n in full:
    if k=='data' and b-a>=0x200:print(hex(a),hex(b),b-a,n)
