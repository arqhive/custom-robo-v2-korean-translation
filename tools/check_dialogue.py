"""대사 넘침 검사: 한 쪽 3줄, 한 줄 204px (한글 12px, 그 밖은 원본 글꼴 폭, $A00·$B00=84px).
usage: python -X utf8 check_dialogue.py <번역.json {id: text}> [...]"""
import json,re,struct,sys
from survey_rom import ROOT
LINE_W=198;MAX_LINES=3;NAME_W=84   # 이름 7글자×12px($A00 플레이어·$B00 가짜 이름, 11/09 사용자 스샷 「규규규규규규규」). 198: 원문 최대 204 지만 한글은 201px 줄이 창 끝에서 잘림(11/07 스샷, 1편도 198)
rom=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes()
N=1672;codes=struct.unpack_from('>%dH'%N,rom,0x3ee40);adv=rom[0x3ee40+2*N:0x3ee40+3*N]
ADV={bytes.fromhex('%04x'%c).decode('euc_jp','replace'):adv[i] for i,c in enumerate(codes)}
THIN='誰'   # 쓰이지 않는 글자(font-unused 후보, 캐시 칸 밖)를 빈 글자 폭 3으로: 가운데 맞춤 미세 조정(1편과 같은 방식)
ADV_FIX={'…':12,THIN:3}   # 빌드가 롬 글자 폭 표를 이렇게 고침: 「…」 뒤 2px 여백(원래 10), THIN 빈 글자
ADV_FIX.update({c:ADV[c]+2 for c in '０１２３４５６７８９'})   # 숫자: 뒤 글자에 붙어 보여 모두 2px 더함(11/07 사용자)
ADV_FIX['ｎ']=ADV['ｎ']+2   # 「2on2」의 n 뒤가 붙어 보여 2px 더함(11/07 사용자)
ADV_FIX['〜']=ADV['〜']+2   # 물결표(~ → 〜) 뒤가 붙어 보여 2px 더함(11/07 사용자)
ADV_FIX['『']=ADV['『']+1; ADV_FIX['』']=ADV['』']+3   # 겹낫표: 『 뒤 1px, 』 뒤 3px 여백(11/07 사용자)
ADV_FIX['Ｐ']=ADV['Ｐ']+2   # 「1P와」의 P 뒤가 붙어 보여 2px 더함(11/07 사용자)
ADV_FIX['ｓ']=ADV['ｓ']+2   # 「vs2」의 s 뒤가 붙어 보여 2px 더함(11/07 사용자)
ADV_FIX['＋']=ADV['＋']+2   # 「2P+3P」의 + 뒤가 붙어 보여 2px 더함(11/07 사용자)
ADV_FIX['〓']=ADV['〓']+2   # 「레이〓」의 〓(2) 뒤가 붙어 보여 2px 더함(11/08 사용자)
ADV_FIX['Ｋ']=ADV['Ｋ']+2   # 「OK」의 K 뒤가 붙어 보여 2px 더함(11/08 사용자)
ADV_FIX['Ｓ']=ADV['Ｓ']+2   # 「100FKS는」의 S 뒤가 붙어 보여 2px 더함(11/09 사용자)
ADV.update(ADV_FIX)
def literal(c):
    if c=='~':return '〜'
    if c==' ':return '　'
    if 0x21<=ord(c)<=0x7e:return chr(ord(c)+0xfee0)
    return c
def width(s):
    w=0
    for m in re.split(r'(\$[A-Z]\d\d|\$[A-Z]|#[a-zA-Z])',s):
        if not m:continue
        if m in ('$A00','$B00'):w+=NAME_W
        elif re.fullmatch(r'\$[A-Z]\d\d|\$[A-Z]',m):pass
        elif re.fullmatch(r'#[a-zA-Z]',m):w+=12
        else:w+=sum(12 if '가'<=c<='힣' else ADV.get(literal(c),12) for c in m)
    return w
def check(text):
    probs=[]
    for i,p in enumerate(text.split('$P')):
        ls=p.split('$R')
        if len(ls)>MAX_LINES:probs.append(f'{i+1}쪽 {len(ls)}줄')
        for l in ls:
            w=width(l)
            if w>LINE_W:probs.append(f'{i+1}쪽 {w}px: {l}')
    return probs
if __name__=='__main__':
    bad=0
    for f in sys.argv[1:]:
        for k,v in json.loads(open(f,encoding='utf-8').read()).items():
            p=check(v)
            if p:bad+=1;print(k,'|','; '.join(p))
    print('넘침 항목:',bad)
