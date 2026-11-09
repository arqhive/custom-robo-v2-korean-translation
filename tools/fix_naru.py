"""파츠 설명의 「~くなる/なっている」 직역(「높게 됐다」「크게 되고」)을 자리별로 「높아졌다」「커지고」로 바꾸는 덮어쓰기 만들기.

usage: python -X utf8 fix_naru.py <후보.json>   → work/translation/desc-overrides.json 에 더해 씀(이미 있는 키는 둠)
- 같은 줄(N)의 なり/なって/なっている: 앞 조각 「~게」를 「~아/어」 꼴로, なる 조각은 「지고」「졌다」(앞말에 붙음).
- 새 줄(Z)의 なっている 앞이 형용사 「~게」면: 형용사를 なる 줄로 옮겨 「~졌다」로(줄 구조는 원문 그대로).
"""
import json, sys, re
import check_desc_fit as F, build_full as B

STEM = {'크게': '커', '굵게': '굵어', '높게': '높아', '빠르게': '빨라', '길게': '길어', '짧게': '짧아', '강하게': '강해', '넓게': '넓어'}
NARU_N = {'Nなり、': 'N지고', 'Nなり': 'N지고', 'Nなって': 'N졌다', 'Nなっている': 'N졌다'}
NARU_Z = {'Z なっている'}


def main():
    disp = F.setup()
    cand = json.load(open(sys.argv[1], encoding='utf-8'))
    src_of = {'R%08X' % p: r['source'] for p, r in disp.items()}
    bysrc = {src_of[k]: v for k, v in cand.items()}
    for p, r in disp.items():
        if r['source'] in bysrc:
            r['translation'] = bysrc[r['source']]
    ovp = B.TR / 'desc-overrides.json'
    ov = json.load(open(ovp, encoding='utf-8')) if ovp.exists() else {}
    n = 0
    for run, r in F.evaluate(disp):
        m = r['members']
        for i, (mid, s, t) in enumerate(m):
            if s not in NARU_N and s not in NARU_Z:
                continue
            j = i - 1
            while j >= 0 and m[j][2] is None:
                j -= 1
            if j < 0:
                continue
            pid, ps, pt = m[j]
            g = re.search(r'(\S+게)\s*$', pt or '')
            if not g or g.group(1) not in STEM:
                continue
            stem = STEM[g.group(1)]
            if s in NARU_N:
                ov.setdefault(pid, pt[:g.start(1)] + stem); ov.setdefault(mid, NARU_N[s])
            else:
                ov.setdefault(pid, pt[:g.start(1)].rstrip()); ov.setdefault(mid, 'Z ' + stem + '졌다')
            n += 1
    json.dump(ov, open(ovp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('고친 자리', n, '덮어쓰기', len(ov))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
