"""번역 결과(out/<묶음>/part-*.json)에 표기 통일 규칙을 적용하고 바뀐 줄을 기록한다.

usage: python -X utf8 apply_unify.py [--dry]
기록: work/translation/unify-log.json [{id, 묶음, rule, before, after}] (덧붙임)
규칙은 RULES 목록. 원문 조건(src)이 있으면 원문에 그 말이 있을 때만 바꾼다.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')

RULES = [
    # (이름, 정규식, 바꿀 말, 원문 조건)
    ('ちゃん 붙여 쓰기', re.compile(r'([가-힣]) 짱(?=[^가-힣]|$|[이은을과도의한])'), r'\1짱', 'ちゃん'),
    ('やみコマンダー=어둠의 커맨더', re.compile(r'어둠 커맨더'), '어둠의 커맨더', None),
    ('Ｖコマンダー=V 커맨더', re.compile(r'V커맨더'), 'V 커맨더', None),
    ('宿舎=숙소', re.compile(r'숙사'), '숙소', '宿舎'),
    ('ノルマ=목표', re.compile(r'할당량'), '목표', 'ノルマ'),
]


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def main():
    dry = '--dry' in sys.argv
    src = {}
    for f in os.listdir(os.path.join(TR, 'batches')):
        if re.fullmatch(r'(dlg|raw)-\d\d\.json', f):
            for x in load(os.path.join(TR, 'batches', f)):
                src[x['id']] = x['source']
    log = []
    out_dir = os.path.join(TR, 'out')
    for b in sorted(os.listdir(out_dir)):
        d = os.path.join(out_dir, b)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            data = load(p)
            changed = False
            for k, v in data['translations'].items():
                new = v
                for name, rx, rep, cond in RULES:
                    if cond and cond not in src.get(k, ''):
                        continue
                    t = rx.sub(rep, new)
                    if t != new:
                        log.append({'id': k, '묶음': b, 'rule': name, 'before': new, 'after': t})
                        new = t
                if new != v:
                    data['translations'][k] = new
                    changed = True
            if changed and not dry:
                with open(p, 'w', encoding='utf-8') as fo:
                    json.dump(data, fo, ensure_ascii=False, indent=1)
    lp = os.path.join(TR, 'unify-log.json')
    old = load(lp) if os.path.exists(lp) else []
    if not dry:
        with open(lp, 'w', encoding='utf-8') as fo:
            json.dump(old + log, fo, ensure_ascii=False, indent=1)
    from collections import Counter
    print(('(미리보기) ' if dry else '') + '바뀐 곳', len(log), dict(Counter(x['rule'] for x in log)))


if __name__ == '__main__':
    main()
