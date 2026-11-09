"""스크립트 밖 문자열 분류 1차(규칙): debug / v1_display / v1_internal / desc_fragment / unknown."""
import json,re,collections
from survey_rom import ROOT
rows=json.loads((ROOT/'work/translation/raw-text-all.json').read_text(encoding='utf-8'))
v1=json.loads(open(r'G:/KoreanTranslation/GPT초벌작/[N64]커스텀로보/work/translation/raw-text-classified.json',encoding='utf-8').read())
v1s=collections.defaultdict(set)
for x in v1:v1s[x['source']].add('D' if x['scope']=='display_text' else 'I')
DEBUG=re.compile(r'(ありません|オーバーしました|間違って|違います|見つかりません|足りません|使われています|できません|異常終了|反応しません|ません\.|\.\n?$|%[sd].*[\.:]|座標|Dash\d|\(\)|_)')
for r in rows:
    s=r['source'];k=v1s.get(s,set())
    if DEBUG.search(s) and 'D' not in k:c='debug'
    elif 'D' in k:c='v1_display'
    elif 'I' in k:c='v1_internal'
    elif re.match(r'[ZMNIHKL][ \u3000]*[^\x00-\x7f]',s) or re.match(r'[ZMNIHKL]$',s):c='desc_fragment'
    else:c='unknown'
    r['rule']=c
cnt=collections.Counter(r['rule'] for r in rows);print(cnt)
per=collections.defaultdict(collections.Counter)
for r in rows:per[r['area']][r['rule']]+=1
for a,v in per.items():print(a,dict(v))
(ROOT/'work/translation/raw-text-all.json').write_text(json.dumps(rows,ensure_ascii=False,indent=0),encoding='utf-8')

# ---- 2차: 원문 단위 분류
INTERNAL=re.compile(r'(呼吸|歩き|走り|勝ち\d|負け\d|パワーアップ|足音|ポーズ$|エフェクト|バレット|爆発|ミサイル|とげ|音$|音（|マップ|全体街|^＞|ｏｕｔ|ＶＳ|デモ|テスト|^Ｖ２|ＣＲ２|^Ｃ２|^[#0-9]|〓|ガレージ（|（昼）|（夜）|夜$|昼$|^道場街|ジェネレータがオーバー|引き抜き|着地|被弾|ピンチ|ため音|近接\d|バウンド|回転$|射出|出現$|崩壊|^ＲポッドＧ|^Ｒポッド|^Ｆポッド|^ニセボム|ステーション１Ｆ２|リビング２|ぼくの部屋２)')
KEYAREAS={'robo_moves','battle_setup','demo_setup'}
INTERNAL2=re.compile(r'([├│└┌┐┘┤┼─＊]|【|パラメータ|．[Ａ-Ｚ０-９]|．\d|^　[^ぁ-ん]*[#]|頻度|確率|距離範囲|属性)')
disp=set()
for r in rows:
    if r['area'] in KEYAREAS:continue
    if r['rule'] in ('v1_display','desc_fragment'):disp.add(r['source'])
    elif r['rule']=='unknown' and r['area']!='seg3' and not INTERNAL.search(r['source']) and not INTERNAL2.search(r['source']):disp.add(r['source'])
for r in rows:
    if r['rule']=='debug':r['class']='internal_debug'
    elif r['source'] in disp:r['class']='display'
    else:r['class']='internal'
c2=collections.Counter(r['class'] for r in rows);print(c2)
print('unique display',len(disp))
per=collections.defaultdict(collections.Counter)
for r in rows:per[r['area']][r['class']]+=1
for a,v in per.items():print(a,dict(v))
(ROOT/'work/translation/raw-text-all.json').write_text(json.dumps(rows,ensure_ascii=False,indent=0),encoding='utf-8')
