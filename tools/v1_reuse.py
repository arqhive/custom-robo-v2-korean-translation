"""1편(V1) 번역을 2편 원문에 대응시킨다.

출력 work/translation/v1-reuse.json
  dialogue: 2편 대사 원문과 똑같은 1편 대사 → 1편 번역
  raw:      2편 표시 문자열과 똑같은 1편 문자열(접두 포함) → 1편 번역
  names:    2편 표시 문자열 중 이름·용어꼴(짧고 문장부호 없음)과 1편 번역 유무
"""
import json, os, re, sys

V1 = 'G:/KoreanTranslation/GPT초벌작/[N64]커스텀로보/work/translation'
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, '..', 'work', 'translation')


def v1_files(pre, suf):
    # 경로에 [N64] 가 있어 glob 은 못 쓴다(대괄호를 패턴으로 읽음)
    return [os.path.join(V1, f) for f in sorted(os.listdir(V1))
            if f.startswith(pre) and f.endswith(suf)]


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def v1_maps():
    # 대사: id → 번역 (build_full.load_dialogue 와 같은 파일)
    dko = {}
    for f in [os.path.join(V1, 'opening-ko.json')] + v1_files('scenario-', '-ko.json'):
        dko.update(load(f))
    dsrc = {x['id']: x['source'] for x in load(V1 + '/source-texts.json')}
    dialogue = {}
    for i, t in dko.items():
        if i in dsrc:
            dialogue.setdefault(dsrc[i], t)
    # 오버레이 문자열: raw-*-ko.json 전부 + 문맥 덮어쓰기
    rko = {}
    for f in v1_files('raw-', '-ko.json'):
        rko.update(load(f))
    rko.update(load(V1 + '/context-raw-ko.json'))
    rsrc = {x['id']: x['source'] for x in load(V1 + '/raw-text-full.json')}
    raw = {}
    for i, t in rko.items():
        if i in rsrc and t:
            raw.setdefault(rsrc[i], t)
    terms = load(V1 + '/terms-ko.json')
    return dialogue, raw, terms


NAMEISH = re.compile(r'^[^\s、。！？!?「」$]{1,16}$')


def main():
    dialogue, raw, terms = v1_maps()
    d2 = [x for x in load(V2 + '/source-texts.json') if x['kind'] == 'dialogue']
    r2 = [x for x in load(V2 + '/raw-text-all.json') if x.get('class') == 'display']
    out = {'dialogue': {}, 'raw': {}, 'names': {}}
    for x in d2:
        if x['source'] in dialogue:
            out['dialogue'][x['id']] = dialogue[x['source']]
    seen = set()
    for x in r2:
        s = x['source']
        if s in seen:
            continue
        seen.add(s)
        if s in raw:
            out['raw'][s] = raw[s]
        body = s.lstrip('ZNMIHKL') if len(s) > 1 and s[0] in 'ZNMIHKL' else s
        if NAMEISH.match(body) and re.search(r'[ぁ-ゟァ-ヺ一-鿿]', body):
            ko = terms.get(body) or raw.get(s) or raw.get(body)
            out['names'][body] = ko
    with open(V2 + '/v1-reuse.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    nd = len({x['source'] for x in d2})
    print('대사 고유', nd, '중 1편과 같음', len({x['source'] for x in d2 if x['source'] in dialogue}))
    print('표시 문자열 고유', len(seen), '중 1편과 같음', len(out['raw']))
    n = out['names']
    print('이름·용어꼴', len(n), '중 1편 번역 있음', sum(1 for v in n.values() if v))


if __name__ == '__main__':
    main()
