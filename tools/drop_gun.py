"""이름 뒤 「~ 군」을 떼는 수정안(2026-11-07 사용자 지시: 애들끼리 → 결국 모두).

usage: python -X utf8 drop_gun.py            → work/translation/gun-proposals.json, gun-review.md 만 씀
       python -X utf8 drop_gun.py --apply    → 수정안을 번역 파일(out/*.json)에 반영
이름 뒤 「~ 군」은 화자와 상관없이 모두 뗀다.
이름 뒤 조사: 주인공($A00)은 받침을 모르니 {은/는} 같은 조사 표기, 나머지 이름은 모두 받침이 없어 받침 없는 꼴로.
"""
import glob, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/translation/out'
PROP = ROOT / 'work/translation/gun-proposals.json'
REVIEW = ROOT / 'work/translation/gun-review.md'
# 화자 나이를 가릴 수 없는 대사가 있어 「~ 군」은 화자와 상관없이 모두 뗌(사용자 11/07)
ADULTS = set()
TARGETS = ['$A00', '츠루기', '야이바', '타이헤이', '겐타', '신이치', '유리에', '후카시', '나나세', '마모루', '타쿠마',
           '지로', '켄고', '나오키', '세이지', '주조', '미츠루']   # $A00 말고는 모두 받침 없음
# 「군」(받침 있음) 뒤 조사 → 받침 없는 이름 뒤 / 주인공 조사 표기
PART = [('이에요', '예요', '{이}에요'), ('이었', '였', '{이}었'), ('이야', '야', '{이}야'), ('이랑', '랑', '{이}랑'),
        ('이라고', '라고', '{이}라고'), ('이라', '라', '{이}라'), ('이지', '지', '{이}지'), ('이네', '네', '{이}네'),
        ('이다', '다', '{이}다'), ('이나', '나', '{이}나'), ('이고', '고', '{이}고'), ('이면', '면', '{이}면'),
        ('으로', '로', '{으}로'), ('이', '가', '{이/가}'), ('은', '는', '{은/는}'), ('을', '를', '{을/를}'),
        ('과', '와', '{과/와}'), ('아', '야', '{아/야}')]
WORD = re.compile('(' + '|'.join(re.escape(t) for t in TARGETS) + r') 군(?![가-힣])|('
                  + '|'.join(re.escape(t) for t in TARGETS) + r') 군([가-힣]+)')


def fix(m):
    if m.group(1):
        return m.group(1)
    name, tail = m.group(2), m.group(3)
    hero = name == '$A00'
    for a, b, h in PART:
        if tail.startswith(a):
            return name + (h if hero else b) + tail[len(a):]
    return name + tail


def speaker_pages(v):
    cur = None
    for page in v.split('$P'):
        m = re.match(r'(?:\$F\d\d)*([^「$　]{1,12})「', page)
        if m: cur = m.group(1)
        yield cur, page


def main():
    if '--apply' in sys.argv:
        props = json.loads(PROP.read_text(encoding='utf-8')); byfile = {}
        for r in props: byfile.setdefault(r['file'], []).append(r)
        for f, rs in byfile.items():
            p = OUT / f; d = json.load(open(p, encoding='utf-8'))
            for r in rs:
                assert d['translations'][r['id']] == r['before'], r['id']
                d['translations'][r['id']] = r['after']
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(len(props), '줄 반영'); return
    props, rows = [], []
    for p in sorted(glob.glob(glob.escape(str(OUT)) + '/*.json')):
        d = json.load(open(p, encoding='utf-8'))['translations']
        for k, v in d.items():
            pages = []
            for who, page in speaker_pages(v):
                if who not in ADULTS:
                    new = WORD.sub(fix, page)
                    for x, y in zip(page.split('$R'), new.split('$R')):
                        if x != y: rows.append((k, who, x, y))
                    page = new
                pages.append(page)
            nv = '$P'.join(pages)
            if nv != v:
                props.append({'file': Path(p).name, 'id': k, 'before': v, 'after': nv})
    PROP.write_text(json.dumps(props, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    code = re.compile(r'\$[RPW]|\$[FSCV]\d\d|\$D')
    md = ['# 「~ 군」 모두 떼기 수정안 (2026-11-07)', '',
          f'{len(props)}개 대사, 바뀌는 줄 {len(rows)}곳. 화자와 상관없이 모두 뗌.',
          '`{은/는}` 등은 주인공 이름 받침에 따라 게임이 고르는 조사.', '',
          '| id | 화자 | 지금 | 수정안 |', '|---|---|---|---|']
    for k, who, x, y in rows:
        md.append(f'| {k} | {who} | {code.sub("", x).strip("　 ")} | {code.sub("", y).strip("　 ")} |')
    REVIEW.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(len(props), '대사,', len(rows), '줄')


if __name__ == '__main__':
    main()
