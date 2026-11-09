"""인물별 말투 조사.

2편 일본어: 화자별 1인칭·문말 표지 횟수와 예문.
1편 한국어: 같은 화자의 한국어 어미 체계(합쇼·해요·반말) 횟수와 예문.
출력: work/glossary/tone-survey.json
"""
import collections, json, os, re
from v1_reuse import V1, load, v1_files
from glossary_candidates import SPEAKER

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
OUT = os.path.join(HERE, '..', 'work', 'glossary')

FIRST = ['オレ', 'おれ', '俺', 'ボク', 'ぼく', '僕', 'わたし', 'ワタシ', '私', 'あたし', 'アタシ',
         'わし', 'ワシ', 'おいら', 'オイラ', 'わたくし', 'ワタクシ', 'ワガハイ', '我', 'ミー', 'あっし', 'うち']
ENDS = {'です・ます': r'(です|ます|でした|ました|ません|ましょう)[。！？…\s」$]',
        'だ・だろ': r'(だ|だろ|だぜ|だよ|だな)[。！？…\s」$]',
        'でしゅ': r'(でしゅ|ましゅ)', 'じゃ': r'じゃ[。！？…\s」$]',
        'わ・のよ': r'(わよ|のよ|かしら|わね|だわ)', 'ぜ・ぞ': r'(ぜ|ぞ)[。！？…\s」$]',
        'ござる': r'ござ', 'ッス': r'(ッス|っす)', 'ニャ・語尾': r'(ニャ|にゃ|ナリ|ザマス|アル)'}
CODE = re.compile(r'\$[A-Z][0-9A-Za-z]{0,2}|#.')


def split(src):
    """원문을 (화자, 말) 조각으로 나눈다. 화자 표시가 없는 조각은 앞 화자를 잇는다."""
    out, cur, last = [], None, 0
    for m in SPEAKER.finditer(src):
        if cur is not None:
            out.append((cur, src[last:m.start()]))
        cur, last = m.group(1), m.end()
    if cur is not None:
        out.append((cur, src[last:]))
    return out


def ko_kind(t):
    t = CODE.sub(' ', t)
    c = collections.Counter()
    for s in re.split(r'(?<=[.!?])\s', t):
        s = s.strip(' 」』…~!?.')
        if not s:
            continue
        if re.search(r'(니다|니까|십시오|습니까)$', s):
            c['합쇼'] += 1
        elif re.search(r'요$', s):
            c['해요'] += 1
        elif re.search(r'(다|어|아|야|지|냐|니|자|라|해|걸|게|군|네|래|까|나)$', s):
            c['반말'] += 1
    return c


def main():
    v2 = [x for x in load(os.path.join(TR, 'source-texts.json')) if x['kind'] == 'dialogue']
    jp = collections.defaultdict(lambda: {'n': 0, 'first': collections.Counter(),
                                          'ends': collections.Counter(), 'ex': []})
    for x in v2:
        for sp, t in split(x['source']):
            e = jp[sp]
            e['n'] += 1
            for w in FIRST:
                e['first'][w] += t.count(w)
            for k, r in ENDS.items():
                e['ends'][k] += len(re.findall(r, t))
            if len(e['ex']) < 6 and len(t) > 12:
                e['ex'].append(CODE.sub('', t)[:70])
    ko = {}
    for f in [os.path.join(V1, 'opening-ko.json')] + v1_files('scenario-', '-ko.json'):
        ko.update(load(f))
    src = {x['id']: x['source'] for x in load(V1 + '/source-texts.json')}
    kr = collections.defaultdict(lambda: {'kind': collections.Counter(), 'ex': []})
    for i, t in ko.items():
        if i not in src or not t:
            continue
        a, b = split(src[i]), split(t)
        if len(a) != len(b):
            continue
        for (sp, _), (_, kt) in zip(a, b):
            e = kr[sp]
            e['kind'] += ko_kind(kt)
            if len(e['ex']) < 4 and len(kt) > 15:
                e['ex'].append(CODE.sub('', kt)[:70])
    out = {}
    for sp, e in sorted(jp.items(), key=lambda kv: -kv[1]['n']):
        if e['n'] < 5:
            continue
        out[sp] = {'lines': e['n'],
                   'first': {k: v for k, v in e['first'].most_common() if v},
                   'ends': {k: v for k, v in e['ends'].most_common() if v},
                   'ex': e['ex']}
        if sp in kr:
            out[sp]['v1_ko'] = dict(kr[sp]['kind'].most_common())
            out[sp]['v1_ex'] = kr[sp]['ex']
    with open(os.path.join(OUT, 'tone-survey.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(len(out), '명')


if __name__ == '__main__':
    main()
