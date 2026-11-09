"""검수 수정안 형식 검사.

usage: python -X utf8 check_review.py <묶음 dlg-NN|raw-NN> [...]
work/review/out-<묶음>.json 의 각 항목: id가 묶음에 있는지, before가 지금 번역과 같은지,
after의 제어 코드가 원문과 같은지(check_translation 의 검사 그대로), 질문 항목 형식.
"""
import json, os, sys
from check_translation import check_one, load, TR, G, KEEP

HERE = os.path.dirname(os.path.abspath(__file__))
RV = os.path.join(HERE, '..', 'work', 'review')


def main():
    gl = load(os.path.join(G, 'glossary-ko.json'))
    for name in sys.argv[1:]:
        src = {x['id']: x['source'] for x in load(os.path.join(TR, 'batches', name + '.json'))}
        cur = load(os.path.join(TR, 'out', name + '.json'))['translations']
        items = load(os.path.join(RV, f'out-{name}.json'))
        bad = q = 0
        seen = set()
        for it in items:
            k = it.get('id')
            p = []
            if k not in src:
                p.append('묶음에 없는 id')
            elif k in seen:
                p.append('같은 id 두 번')
            else:
                if it.get('before') != cur[k]:
                    p.append('before가 지금 번역과 다름')
                if it.get('after') is None:
                    q += 1
                    if not it.get('question'):
                        p.append('질문 없음')
                elif k not in KEEP:
                    p += check_one(src[k], it['after'], gl)
                    if it['after'] == cur[k]:
                        p.append('바뀐 것 없음')
            seen.add(k)
            if p:
                bad += 1
                print(k, '|', '; '.join(p))
        print(f'{name}: 수정안 {len(items) - q} / 질문 {q} / 문제 {bad}')


if __name__ == '__main__':
    main()
