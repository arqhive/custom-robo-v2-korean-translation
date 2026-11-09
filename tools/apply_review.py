"""승인된 검수 수정안을 번역 결과(out/<묶음>/part-*.json)에 넣는다.

usage: python -X utf8 apply_review.py [--skip id,id,...]
work/review/out-*.json 의 after 가 있는 항목을 넣는다(질문 항목·--skip 은 뺀다).
before 가 지금 번역과 다르면 넣지 않고 알린다. 기록은 work/translation/unify-log.json 에 덧붙인다.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
RV = os.path.join(HERE, '..', 'work', 'review')


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def main():
    skip = set()
    if '--skip' in sys.argv:
        skip = set(sys.argv[sys.argv.index('--skip') + 1].split(','))
    log_p = os.path.join(TR, 'unify-log.json')
    log = load(log_p)
    n = stale = 0
    for f in sorted(os.listdir(RV)):
        m = re.fullmatch(r'out-((?:dlg|raw)-\d\d)\.json', f)
        if not m:
            continue
        b = m.group(1)
        fixes = {it['id']: it for it in load(os.path.join(RV, f)) if it.get('after') is not None and it['id'] not in skip}
        d = os.path.join(TR, 'out', b)
        for pf in sorted(os.listdir(d)):
            p = os.path.join(d, pf)
            data = load(p)
            ch = False
            for k in list(data['translations']):
                if k in fixes:
                    it = fixes[k]
                    if it['before'] != data['translations'][k]:
                        stale += 1
                        print('지금 번역과 before 다름, 건너뜀:', k)
                        continue
                    data['translations'][k] = it['after']
                    log.append({'id': k, '묶음': b, 'rule': '7단계 검수: ' + it.get('kind', ''), 'before': it['before'],
                                'after': it['after'], 'reason': it.get('reason', '')})
                    ch = True
                    n += 1
            if ch:
                with open(p, 'w', encoding='utf-8') as fo:
                    json.dump(data, fo, ensure_ascii=False, indent=1)
    with open(log_p, 'w', encoding='utf-8') as fo:
        json.dump(log, fo, ensure_ascii=False, indent=1)
    print('넣음', n, '건너뜀', stale)


if __name__ == '__main__':
    main()
