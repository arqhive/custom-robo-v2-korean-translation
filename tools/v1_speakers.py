"""1편 대사에서 화자 이름 번역을 모은다(같은 id의 원문·번역 화자를 순서대로 짝짓기).

출력: work/glossary/v1-speakers.json  {원문 이름: {번역: 횟수}}
"""
import collections, json, os, re
from v1_reuse import V1, load, v1_files
from glossary_candidates import SPEAKER

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'work', 'glossary')


def main():
    ko = {}
    for f in [os.path.join(V1, 'opening-ko.json')] + v1_files('scenario-', '-ko.json'):
        ko.update(load(f))
    src = {x['id']: x['source'] for x in load(V1 + '/source-texts.json')}
    m = collections.defaultdict(collections.Counter)
    for i, t in ko.items():
        if i not in src or not t:
            continue
        a = [x.group(1) for x in SPEAKER.finditer(src[i])]
        b = [x.group(1) for x in SPEAKER.finditer(t)]
        if len(a) == len(b):
            for x, y in zip(a, b):
                m[x][y] += 1
    out = {k: dict(v.most_common()) for k, v in sorted(m.items(), key=lambda kv: -sum(kv[1].values()))}
    with open(os.path.join(OUT, 'v1-speakers.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(k, v)


if __name__ == '__main__':
    main()
