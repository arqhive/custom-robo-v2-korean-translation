"""모델 묶음 안의 재질 그림(1편 규칙: 머리 12/8바이트 + 팔레트 512 + 끝부분 CI8 배열) 추출 시도."""
import json,struct,math,collections
import numpy as np
from PIL import Image,ImageDraw
from survey_rom import ROOT
banks=json.loads((ROOT/'manifests/banks.json').read_text())
streams=json.loads((ROOT/'manifests/compressed-streams.json').read_text())
def rgba16(raw):
    v=np.frombuffer(raw,dtype='>u2').astype(np.uint16);out=np.empty((len(v),4),np.uint8)
    for i,s in enumerate((11,6,1)):n=(v>>s)&31;out[:,i]=(n<<3)|(n>>2)
    out[:,3]=(v&1)*255;return out
model_banks=['0x1529b0','0x30b480','0x371f70','0x396f20','0x3b78a0','0x3d6b10','0x3e7f40','0x41f7d0','0x55ffc0','0x92cf40','0x94daf0','0x96be10','0x979ce0']
out=ROOT/'work/survey/materials';out.mkdir(parents=True,exist_ok=True)
res=collections.Counter();tiles=collections.defaultdict(list);fail=collections.defaultdict(list)
for bk in banks:
    if bk['start'] not in model_banks:continue
    a=int(bk['start'],16);b=int(bk['end'],16)
    for r in [r for r in streams if a<=r['offset']<b]:
        raw=(ROOT/r['file']).read_bytes();ok=False
        for prefix in (12,8):
            if len(raw)<prefix+512+16:continue
            w,h=(raw[10],raw[11]) if prefix==12 else (raw[5],raw[6])
            count=raw[9] if prefix==12 else 1
            if not(8<=w<=128 and 8<=h<=128 and 1<=count<=16):continue
            start=len(raw)-w*h*count;pat=prefix+512+(32 if prefix==12 else 8)
            if start<prefix+512 or pat+4>len(raw) or struct.unpack_from('>I',raw,pat)[0]!=start:continue
            pal=rgba16(raw[prefix:prefix+512])
            for j in range(count):
                idx=np.frombuffer(raw[start+j*w*h:start+(j+1)*w*h],np.uint8)
                im=Image.fromarray(pal[idx].reshape(h,w,4),'RGBA');n=f"{r['offset']:08X}-{j:02d}"
                im.save(out/f'{n}.png');tiles[bk['start']].append((n,im))
            ok=True;res[(bk['start'],'material')]+=1;break
        if not ok:res[(bk['start'],'other')]+=1;fail[bk['start']].append(r['offset'])
for k in sorted(res):print(k,res[k])
for bank,tl in tiles.items():
    for k in range(0,len(tl),64):
        batch=tl[k:k+64];cols=8;cw,ch=200,150
        sheet=Image.new('RGB',(cols*cw,math.ceil(len(batch)/cols)*ch),(70,80,90));dr=ImageDraw.Draw(sheet)
        for i,(n,im) in enumerate(batch):
            t=im.resize((im.width*2,im.height*2),Image.NEAREST);t.thumbnail((cw-6,ch-20));x=i%cols*cw;y=i//cols*ch
            bg=Image.new('RGBA',t.size,(40,40,40,255));bg.alpha_composite(t);sheet.paste(bg.convert('RGB'),(x+3,y+3));dr.text((x+3,y+ch-16),n,fill='white')
        sheet.save(out/f"sheet_{bank[2:]}_{k//64:02d}.png")
json.dump({k:[hex(x) for x in v] for k,v in fail.items()},open(ROOT/'work/survey/materials/unresolved.json','w'),indent=0)
