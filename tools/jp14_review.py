# -*- coding: utf-8 -*-
"""직역투 14가지 줄별 검수 기록 도구 (2026-11-09 사용자 지시: 줄마다 판정을 남기고, 빈 칸이 있으면 보고 금지).

사용
  python -X utf8 tools/jp14_review.py make S037-0000 25   → work/review/jp14/batch-<첫id>.json 뼈대 + 화면 출력
  python -X utf8 tools/jp14_review.py check <batch 파일>   → 줄마다 14칸이 모두 채워졌는지 검사(빈 칸 있으면 실패)
  python -X utf8 tools/jp14_review.py table <batch 파일>   → 고칠 줄만 대조표(마크다운)로 출력

판정 칸 값: "-" = 해당 없음, 그 밖의 글 = 걸린 내용(고칠 안은 "fix" 에 적는다).
14가지: 1 대체 / 2 맞장구 / 3 좀 / 4 그·이 강조 지시어 / 5 습관적 첫머리 말 / 6 のだ 직역(~는 거야·~인 것이다) /
7 だ→~다(아이·젊은이) / 8 か→~냐 / 9 어른 말투가 아이에게(주마·하게·구나) / 10 원문 부호 그대로 /
11 원문에 없는 관계어 / 12 어순 직역 / 13 ~의 남발·일본식 조어 / 14 보조 동사 덧붙이기
"""
import json, glob, re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'review', 'jp14')
ITEMS = ['1 대체', '2 맞장구', '3 좀', '4 그·이 강조', '5 첫머리 말', '6 のだ', '7 ~다', '8 ~냐',
         '9 어른 말투', '10 원문 부호', '11 관계어', '12 어순', '13 ~의·조어', '14 보조 동사']


def load_tr():
    d = {}
    for f in sorted(glob.glob(os.path.join(glob.escape(ROOT), 'work', 'translation', 'out', 'dlg-*.json'))):
        d.update(json.load(open(f, encoding='utf-8'))['translations'])
    return d


def clean(s):
    s = re.sub(r'\$A00', '{N}', s)
    s = re.sub(r'\$B00', '{가짜}', s)
    s = re.sub(r'\$[A-Z]\d\d|\$[A-Z]', '', s.replace('$R', ' ').replace('$P', '␞'))
    return s.replace('　', '').replace(' ', ' ')


def make(first, n):
    tr = load_tr()
    src = {x['id']: x['source'] for x in json.load(open(os.path.join(ROOT, 'work', 'translation', 'source-texts.json'), encoding='utf-8'))}
    uf = json.load(open(os.path.join(ROOT, 'work', 'translation', 'user-fixes.json'), encoding='utf-8'))
    touched = set(json.load(open(os.path.join(OUT, 'user-touched-ids.json'), encoding='utf-8')))
    ids = [k for k in sorted(tr) if k >= first][:n]
    rows = []
    for k in ids:
        jp = clean(src.get(k, '')).split('␞'); kp = clean(tr[k]).split('␞')
        sp = re.match(r'^(?:\$[A-Z]\d\d)*([^「]*)「', tr[k])
        note = uf['keep'].get(k) or uf['set'].get(k) or ''
        rows.append({'id': k, 'speaker': sp.group(1) if sp else '',
                     'pages': [{'J': a, 'K': b} for a, b in zip(jp, kp)],
                     'user_fixed': note, 'user_touched': k in touched,
                     'judge': {it: None for it in ITEMS}, 'fix': []})
    path = os.path.join(OUT, f'batch-{ids[0]}.json')
    json.dump(rows, open(path, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
    for r in rows:
        tag = (' [고정] ' + r['user_fixed']) if r['user_fixed'] else (' [사용자 수정 이력]' if r['user_touched'] else '')
        print(f"### {r['id']} {r['speaker']}{tag}")
        for i, p in enumerate(r['pages']):
            print(f"  J{i}: {p['J']}")
            print(f"  K{i}: {p['K']}")
    print('파일', path, '줄', len(rows), '다음 시작', [k for k in sorted(tr) if k > ids[-1]][:1])


def check(path):
    rows = json.load(open(path, encoding='utf-8'))
    bad = []
    for r in rows:
        empty = [it for it in ITEMS if not r['judge'].get(it)]
        if empty:
            bad.append((r['id'], empty))
        hits = [it for it in ITEMS if r['judge'].get(it) not in (None, '-')]
        if hits and not r['fix'] and not r.get('keep_reason'):
            bad.append((r['id'], '걸린 항목이 있는데 고칠 안(fix)이나 그대로 둘 까닭(keep_reason)이 없음'))
    print('줄', len(rows), '빈 판정', len(bad))
    for b in bad[:20]:
        print('  ', b)
    return not bad


def table(path):
    rows = json.load(open(path, encoding='utf-8'))
    n = 0
    for r in rows:
        for fx in r['fix']:
            n += 1
            print(f"| {n} | {r['id']} | {r['speaker']} | {fx.get('j','')} | {fx['from']} | {fx['to']} | {fx.get('why','')} |")
    print('고칠 곳', n, '/ 판정한 줄', len(rows))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make':
        make(sys.argv[2], int(sys.argv[3]))
    elif cmd == 'check':
        sys.exit(0 if check(sys.argv[2]) else 1)
    elif cmd == 'table':
        table(sys.argv[2])
