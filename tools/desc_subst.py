"""파츠 설명 조각을 자리별로 고치는 덮어쓰기(desc-overrides.json)에 바꿀 말을 더함.

usage: python -X utf8 desc_subst.py <후보.json> <규칙.json>
규칙: [[설명 id 또는 "*", 바꿀 말(정규식), 새 말], ...] — 설명 안 조각마다(지금 번역 기준) re.sub. "*" 는 모든 설명.
"""
import json, re, sys
import check_desc_fit as F, build_full as B


def main():
    disp = F.setup()
    cand = json.load(open(sys.argv[1], encoding='utf-8'))
    rules = json.load(open(sys.argv[2], encoding='utf-8'))
    src_of = {'R%08X' % p: r['source'] for p, r in disp.items()}
    bysrc = {src_of[k]: v for k, v in cand.items()}
    for p, r in disp.items():
        if r['source'] in bysrc:
            r['translation'] = bysrc[r['source']]
    ovp = B.TR / 'desc-overrides.json'
    ov = json.load(open(ovp, encoding='utf-8')) if ovp.exists() else {}
    for k, v in ov.items():
        disp[int(k[1:], 16)]['translation'] = v
    hits = {i: 0 for i in range(len(rules))}
    for run, r in F.evaluate(disp):
        for mid, s, t in r['members']:
            if t is None:
                continue
            new = t
            for i, (d, a, b) in enumerate(rules):
                if d in ('*', r['start']) and re.search(a, new):
                    new = re.sub(a, b, new); hits[i] += 1
            if new != t:
                ov[mid] = new
    json.dump(ov, open(ovp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for i, (d, a, b) in enumerate(rules):
        print(hits[i], d, a, '->', b)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
