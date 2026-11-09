"""「~짱」 호칭을 이름으로 바꾸는 수정안 만들기(2026-11-07 사용자 지시: 전부, 이름만).

usage: python -X utf8 drop_jjang.py            → work/translation/jjang-proposals.json 만 씀(번역 파일은 안 건드림)
       python -X utf8 drop_jjang.py --apply    → 수정안 파일을 번역 파일(out/*.json)에 반영
바뀐 이름은 모두 받침이 없으니 뒤 조사도 받침 없는 꼴로 바꾼다(이→가, 은→는, 이야→야 …). 「후짱」(후타바 자칭)·배짱·알짱거리다는 뺀다.
"""
import glob, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/translation/out'
PROP = ROOT / 'work/translation/jjang-proposals.json'
NAMES = {'겐짱': '겐타', '유리에짱': '유리에', '돌고래짱': '돌고래', '신짱': '신이치', '후타바짱': '후타바',
         '클레오파트라짱': '클레오파트라', '마모루짱': '마모루', '타쿠짱': '타쿠마', '쿠미짱': '쿠미', '카나짱': '카나',
         '클리오네짱': '클리오네', '지로짱': '지로', '이쿠짱': '이쿠', '마리짱': '마리', '사치코짱': '사치코'}
# 받침 있는 「짱」 뒤 → 받침 없는 이름 뒤 (긴 것부터)
PARTICLE = [('이다', '다'), ('이에요', '예요'), ('이었', '였'), ('이야', '야'), ('이랑', '랑'), ('이라고', '라고'), ('이라도', '라도'),
            ('이라는', '라는'), ('이라면', '라면'), ('이라', '라'), ('이니까', '니까'), ('이지', '지'), ('이네', '네'),
            ('이나', '나'), ('이고', '고'), ('이면', '면'), ('이란', '란'), ('이여', '여'), ('이잖아', '잖아'),
            ('으로', '로'), ('이', '가'), ('은', '는'), ('을', '를'), ('과', '와'), ('아', '야')]
WORD = re.compile(r'(\$A00코짱|게~+엔짱|' + '|'.join(sorted(NAMES, key=len, reverse=True)) + r")(['’]?[가-힣]*)")


def fix(m):
    w, tail = m.group(1), m.group(2)
    if w == '$A00코짱':
        new = '$A00코'
    elif w.startswith('게'):
        new = w[:-2] + '엔타'          # 게~~~엔짱 → 게~~~엔타 (길게 부르는 겐짱)
    else:
        new = NAMES[w]
    q = tail[:1] if tail[:1] in "'’" else ''      # 'OO짱'이라고 처럼 따옴표 뒤 조사
    tail = tail[len(q):]
    for a, b in PARTICLE:
        if tail.startswith(a):
            tail = b + tail[len(a):]; break
    return new + q + tail


def main():
    props = []
    for p in sorted(glob.glob(glob.escape(str(OUT)) + '/*.json')):
        d = json.load(open(p, encoding='utf-8'))['translations']
        for k, v in d.items():
            nv = WORD.sub(fix, v)
            if nv != v:
                props.append({'file': Path(p).name, 'id': k, 'before': v, 'after': nv})
    if '--apply' not in sys.argv:
        PROP.write_text(json.dumps(props, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(len(props), '줄 →', PROP.name); return
    props = json.loads(PROP.read_text(encoding='utf-8'))
    byfile = {}
    for r in props:
        byfile.setdefault(r['file'], []).append(r)
    for f, rs in byfile.items():
        p = OUT / f; d = json.load(open(p, encoding='utf-8'))
        for r in rs:
            assert d['translations'][r['id']] == r['before'], r['id']
            d['translations'][r['id']] = r['after']
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(len(props), '줄 반영')


if __name__ == '__main__':
    main()
