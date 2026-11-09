"""용어집 후보를 종류별로 뽑는다.

입력: work/translation/source-texts.json(대사), raw-text-all.json(표시 문자열), v1-reuse.json
출력: work/glossary/candidates.json
  speakers: 대사 화자 이름(「 앞) → 횟수
  parts:    파츠 이름(ガン·ボム·ポッド·レッグ 끝, #코드 뗀 것)
  stages:   배틀 스테이지 이름(seg8 표)
  places:   시나리오 장소·장 제목(seg4·seg11)
  others:   그 밖의 이름꼴(배틀 설정·로보 표에 나오는 것: 로보·캐릭터 이름)
각 항목에 1편 번역(v1)과 대사 안 등장 횟수(in_dialogue)를 붙인다.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
OUT = os.path.join(HERE, '..', 'work', 'glossary')

SPEAKER = re.compile(r'(?:^|\$P|\$F\d\d|\$R)([^「$　 ]{1,14})(?:\$R)?「')
PART = re.compile(r'(ガン|ボム|ポッド|レッグ)$')
JP = re.compile(r'[ぁ-ゟァ-ヺ一-鿿]')


def load(n):
    with open(os.path.join(TR, n), encoding='utf-8') as f:
        return json.load(f)


def body(s):
    if len(s) > 1 and s[0] in 'ZNMIHKL':
        s = s[1:]
    s = re.sub(r'^#I', '', s)
    return re.sub(r'#[A-Z]$', '', s)


def main():
    dlg = [x['source'] for x in load('source-texts.json') if x['kind'] == 'dialogue']
    alltext = '\n'.join(dlg)
    reuse = load('v1-reuse.json')
    v1 = {k: v for k, v in reuse['names'].items() if v}
    sp = collections.Counter()
    for s in dlg:
        for m in SPEAKER.finditer(s):
            sp[m.group(1)] += 1

    cats = {'parts': {}, 'stages': {}, 'places': {}, 'others': {}}
    names = set(reuse['names'])
    for x in load('raw-text-all.json'):
        if x.get('class') != 'display':
            continue
        raw = x['source']
        b = body(raw)
        if raw[:1] in 'ZNMIHKL' and len(raw) > 1:
            if raw[1:] not in names and raw not in names:
                continue
        elif raw not in names:
            continue
        if not JP.search(b):
            continue
        a = x['area']
        if PART.search(b):
            c = 'parts'
        elif a == 'seg8':
            c = 'stages'
        elif a in ('seg4', 'seg11') and len(b) >= 4:
            c = 'places'
        elif a in ('battle_setup', 'demo_setup', 'robo_moves'):
            c = 'others'
        else:
            continue
        e = cats[c].setdefault(b, {'areas': set()})
        e['areas'].add(a)
    out = {'speakers': {k: {'count': v, 'v1': v1.get(k)} for k, v in sp.most_common()}}
    for c, d in cats.items():
        out[c] = {k: {'areas': sorted(e['areas']), 'v1': v1.get(k),
                      'in_dialogue': alltext.count(k)} for k, e in sorted(d.items())}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'candidates.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for c, d in out.items():
        print(c, len(d), '1편 번역 있음', sum(1 for e in d.values() if e['v1']))


if __name__ == '__main__':
    main()
