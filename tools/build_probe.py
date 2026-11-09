"""2단계 출력 시험: 초반 대사 몇 줄만 한글로 넣은 시험 롬.

모드 name: 한글 이름 입력 시험(글꼴 고정 코드 = 완성형 2,350자 + 자모 51자, 0번 페이지 자모 격자,
오버레이 10 글자 붙이기 훅, 조합 루틴과 가짜 이름 한글 표는 글꼴 초기화가 부팅 때 RAM 0x802E4400 으로 올림)."""
from pathlib import Path
import json,re,struct,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from survey_rom import ROOT,decode
from codec import encode
from build_opening_probe import crc6102
import font_cache
import name_input
import fake_name
BLOB_VA=0x802e4400            # 빈 RAM 0x802E42B0~0x8033F800 안
CONTROL=re.compile(r'\$[A-Z]\d\d|\$[A-Z]|#[a-zA-Z]')
FONT=Path('C:/Users/hgyst/AppData/Local/Microsoft/Windows/Fonts/Galmuri11.ttf')

def literal(c):
    if c=='~':return '〜'
    if c==' ':return '\u3000'
    if 0x21<=ord(c)<=0x7e:return chr(ord(c)+0xfee0)
    return c

def enc(s,m):
    out=[];pos=0
    def two(c):
        c=literal(c);b=m[c] if c in m else c.encode('euc_jp');assert len(b)==2,repr(c);return b
    for x in CONTROL.finditer(s):
        out+=[two(c) for c in s[pos:x.start()]];out.append(x.group().encode());pos=x.end()
    out+=[two(c) for c in s[pos:]]
    return b''.join(out)

def glyph(font,c):
    im=Image.new('1',(12,12));ImageDraw.Draw(im).text((0,-1),c,font=font,fill=1)
    full=Image.new('1',(14,16));ImageDraw.Draw(full).text((0,1),c,font=font,fill=1)
    a=np.array(full);assert not a[:1].any() and not a[13:].any() and not a[:,12:].any(),c
    return np.packbits(np.array(im,dtype=np.uint8).reshape(-1)).tobytes()

def main(mode='full'):
    src=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes();rom=bytearray(src)
    assert crc6102(src)==src[16:24]
    free=(len(src.rstrip(b'\xff'))+15)&~15
    def append(data):
        nonlocal free
        a=free;assert src[a:a+len(data)]==b'\xff'*len(data);rom[a:a+len(data)]=data;free=(a+len(data)+15)&~15;return a
    tr=json.loads((ROOT/'work/translation/probe-ko.json').read_text(encoding='utf-8'))
    rows={r['id']:r for r in json.loads((ROOT/'work/translation/source-texts.json').read_text(encoding='utf-8'))}
    if mode=='name':
        hangul=name_input.KS+name_input.JAMO          # 고정 코드(최종 빌드와 같음)
        m={c:name_input.idx2code(i) for i,c in enumerate(hangul)}
    else:
        hangul=sorted({c for t in tr.values() for c in t if '가'<=c<='힣'})
        m={c:bytes([0x81+i//94,0xa1+i%94]) for i,c in enumerate(hangul)}
    font=ImageFont.truetype(str(FONT),12)
    tex=append(font_cache.original_expanded(src))
    ko=append(b''.join(font_cache.expand(glyph(font,c)) for c in hangul))
    blob=None
    if mode=='name':
        mod,entry=name_input.module(BLOB_VA)
        mod+=bytes((-len(mod))%16)
        tbl,ptrs=fake_name.place(src,BLOB_VA+len(mod))   # 가짜 이름($B00) 한글 표, 포인터 4개
        for o,v in ptrs:struct.pack_into('>I',rom,o,v)
        mod+=tbl
        blob=(append(mod),BLOB_VA,len(mod))
        from segments import segments
        s10=segments(src)[10]
        h=name_input.hook_bytes(entry);a=s10['rom_start']+name_input.HOOK-s10['ram']
        assert rom[a:a+4]==bytes.fromhex('3c098022'),rom[a:a+4].hex()   # lui $t1,0x8022
        rom[a:a+len(h)]=h
        g=name_input.GRID_ROM
        assert src[g:g+130].decode('euc_jp').startswith('アカサタナ') and src[g+130]==0
        rom[g:g+130]=b''.join(m.get(c) or c.encode('euc_jp') for c in name_input.GRID)
        a=0x11ad10;old=src[a:a+10];assert old==' カタカナ '.encode('euc_jp'),old   # 페이지 이름
        new=b' '+m['한']+m['글']+b' ';rom[a:a+10]=new+bytes(10-len(new))
    rep=font_cache.patch(rom,tex,ko,len(hangul),blob=blob,hook_lookup=mode!='initonly') if mode in ('full','font','initonly','name') else None
    if mode in ('font','initonly'):tr={}
    files=json.loads((ROOT/'manifests/script-files.json').read_text(encoding='utf-8'))
    per={}
    for k,t in tr.items():
        r=rows[k];assert CONTROL.findall(t)==CONTROL.findall(r['source']),k
        per.setdefault(r['script'],[]).append((r,t))
    for fid,items in per.items():
        f=files[fid];data=bytearray((ROOT/f'work/extracted/scripts/{fid:03d}.bin').read_bytes());pool=f['string_pool']
        words=struct.unpack_from('>%dI'%(pool//4),data,0)
        for r,t in (items if mode!='reloc' else []):
            b=enc(t,m);p=r['offset']
            assert data[p:p+r['bytes']]==r['source'].encode('euc_jp')
            if len(b)<=r['bytes']:data[p:p+r['bytes']]=b+bytes(r['bytes']-len(b))
            else:
                new=len(data)-pool;data+=b+b'\0'
                refs=[i+1 for i in range(len(words)-1) if words[i]>>16==0x1000 and words[i+1]==r['pool_offset']];assert refs
                for i in refs:struct.pack_into('>I',data,4*i,new)
        struct.pack_into('>I',data,0,len(data));assert len(data)<=0x28000
        packed=encode(bytes(data));assert decode(packed,0)[0]==bytes(data)
        if len(packed)<=f['compressed_size'] and mode!='reloc':a=f['rom_offset'];rom[a:a+f['compressed_size']]=packed+bytes(f['compressed_size']-len(packed))
        else:a=append(packed);struct.pack_into('>I',rom,f['table_entry'],a-0x44b8b0)
        assert decode(rom,struct.unpack_from('>I',rom,f['table_entry'])[0]+0x44b8b0)[0]==bytes(data)
    rom[16:24]=crc6102(rom)
    out=ROOT/('build/Custom Robo V2 (Japan) [KO probe].z64' if mode=='full' else
              'build/Custom Robo V2 (Japan) [KO name-input probe].z64' if mode=='name' else f'build/probe_{mode}.z64');out.write_bytes(rom)
    print(json.dumps({'file':str(out.relative_to(ROOT)),'lines':len(tr),'glyphs':len(hangul),'font':rep,'md5':hashlib.md5(rom).hexdigest()},ensure_ascii=False))

if __name__=='__main__':
    import sys;main(sys.argv[1] if len(sys.argv)>1 else 'full')
