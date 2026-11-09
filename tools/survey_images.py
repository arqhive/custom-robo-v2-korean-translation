"""4단계 그림 전수 조사: 모든 압축 스트림을 그림 후보 형식으로 그려 묶음별 대조 시트를 만든다.
형식은 크기로 고른다(CI8+팔레트, CI4+팔레트, RGBA16 머리 있는 묶음, RGBA16, RGBA32). 폭은 행 사이 차이가 가장 작은 값."""
import json,math,struct,sys
import numpy as np
from PIL import Image,ImageDraw
from survey_rom import ROOT
banks=json.loads((ROOT/'manifests/banks.json').read_text())
streams=json.loads((ROOT/'manifests/compressed-streams.json').read_text())
def rgba16(raw):
    v=np.frombuffer(raw[:len(raw)//2*2],dtype='>u2').astype(np.uint16)
    out=np.empty((len(v),4),np.uint8)
    for i,s in enumerate((11,6,1)):n=(v>>s)&31;out[:,i]=(n<<3)|(n>>2)
    out[:,3]=(v&1)*255;return out
def best_width(px,n):
    best=None
    for w in range(8,min(n,640)+1,4):
        if n%w:continue
        h=n//w
        if h<4 or h>1024:continue
        a=px[:w*h].reshape(h,w,-1).astype(np.int32)
        score=np.abs(a[1:]-a[:-1]).mean()
        if best is None or score<best[0]:best=(score,w)
    return best[1] if best else None
def render(d):
    n=len(d);cands=[]
    if n>512:
        m=n-512
        if m>=64:
            pal=rgba16(d[:512]);idx=np.frombuffer(d[512:],np.uint8);w=best_width(idx[:,None],m)
            if w:cands.append(('CI8',w,pal[idx].reshape(m//w,w,4)))
    if n>32 and (n-32)*2>=64:
        pal=rgba16(d[:32]);p=np.frombuffer(d[32:],np.uint8);idx=np.empty(len(p)*2,np.uint8);idx[::2]=p>>4;idx[1::2]=p&15
        w=best_width(idx[:,None],len(idx))
        if w:cands.append(('CI4',w,pal[idx].reshape(len(idx)//w,w,4)))
    if n>=8:
        size,wx,hy,cnt=struct.unpack_from('>IBBH',d)
        if size==n and 1<=wx<=10 and 1<=hy<=10 and 1<=cnt<=64 and 8+cnt*(1<<wx)*(1<<hy)*2==n:
            w,h=1<<wx,1<<hy;px=rgba16(d[8:]);cands=[('RGBA16H',w,px.reshape(cnt*h,w,4))]
            return cands
    px=rgba16(d);w=best_width(px[:,:3],len(px))
    if w:cands.append(('RGBA16',w,px[:len(px)//w*w].reshape(-1,w,4)))
    if n%4==0:
        p=np.frombuffer(d,np.uint8).reshape(-1,4);w=best_width(p[:,:3],len(p))
        if w:cands.append(('RGBA32',w,p.reshape(-1,w,4)))
    return cands
def score(im):
    a=im.astype(np.int32);return np.abs(a[1:]-a[:-1]).mean()+np.abs(a[:,1:]-a[:,:-1]).mean()
out=ROOT/'work/survey/images';out.mkdir(parents=True,exist_ok=True)
index=[]
for bk in banks:
    a=int(bk['start'],16);b=int(bk['end'],16)
    st=[r for r in streams if a<=r['offset']<b]
    if not st:continue
    tiles=[]
    for r in st:
        d=(ROOT/r['file']).read_bytes();c=render(d)
        if not c:continue
        fmt,w,img=min(c,key=lambda x:score(x[2][...,:3]))
        im=Image.fromarray(img,'RGBA');name=f"{r['offset']:08X}"
        p=out/bk['start'][2:];p.mkdir(exist_ok=True);im.save(p/f'{name}.png')
        index.append({'bank':bk['start'],'stream':hex(r['offset']),'format':fmt,'width':w,'height':img.shape[0]})
        tiles.append((name,fmt,im))
    # contact sheets
    for k in range(0,len(tiles),48):
        batch=tiles[k:k+48];cols=8;cw,ch=200,170
        sheet=Image.new('RGB',(cols*cw,math.ceil(len(batch)/cols)*ch),(70,80,90));dr=ImageDraw.Draw(sheet)
        for i,(n,f,im) in enumerate(batch):
            t=im.copy();t.thumbnail((cw-6,ch-22));x=i%cols*cw;y=i//cols*ch
            bg=Image.new('RGBA',t.size,(40,40,40,255));bg.alpha_composite(t);sheet.paste(bg.convert('RGB'),(x+3,y+3))
            dr.text((x+3,y+ch-18),f'{n} {f} {im.width}x{im.height}',fill='white')
        sheet.save(out/f"sheet_{bk['start'][2:]}_{k//48:02d}.png")
json.dump(index,open(ROOT/'manifests/image-survey.json','w'),indent=0)
print(len(index))
