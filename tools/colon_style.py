"""파츠 설명의 「지상엔 ~, 공중엔 ~」을 「지상: ~ / 공중: ~」(공중은 새 줄)로 바꾸는 자리별 덮어쓰기(사용자 11/07).

usage: python -X utf8 colon_style.py <후보.json>
설명 안에 「지상엔」과 「공중엔」이 함께 있으면: 「지상엔 」→「지상: 」, 「공중엔」 앞 쉼표를 빼고 줄 첫머리가 아니면 §Z 로 새 줄.
"""
import json, re, sys
import check_desc_fit as F, build_full as B


def main():
    disp = F.setup()
    cand = json.load(open(sys.argv[1], encoding='utf-8'))
    src_of = {'R%08X' % p: r['source'] for p, r in disp.items()}
    bysrc = {src_of[k]: v for k, v in cand.items()}
    for p, r in disp.items():
        if r['source'] in bysrc:
            r['translation'] = bysrc[r['source']]
    ovp = B.TR / 'desc-overrides.json'
    ov = json.load(open(ovp, encoding='utf-8'))
    for k, v in ov.items():
        disp[int(k[1:], 16)]['translation'] = v
    n = 0
    for run, r in F.evaluate(disp):
        m = [(i, s, t) for i, s, t in r['members']]
        text = ''.join(t or '' for _, _, t in m)
        if '지상엔' not in text or '공중엔' not in text:
            continue
        n += 1
        prev = None
        for k, (mid, s, t) in enumerate(m):
            if t is None:
                prev = (mid, s, t); continue
            new = t.replace('지상엔 ', '지상: ').replace('지상엔', '지상:')
            if '공중엔' in new:
                head = new[:1]; body = new[1:]
                if re.match(r'\s*공중엔', body) and head == 'Z':      # 이미 줄 첫머리
                    body = re.sub(r'공중엔\s*', '공중: ', body, count=1)
                else:
                    body = re.sub(r',?\s*공중엔\s*', '§Z 공중: ', body, count=1)
                new = head + body
                if new[1:].startswith('§Z'):                          # 조각 첫머리에서 바로 새 줄이면 접두로
                    new = 'Z' + new[3:] if head == 'N' else new
            if new != t:
                ov[mid] = new
            prev = (mid, s, new)
        # 「공중:」 뒤가 비면(다음 내용이 Z 조각) 「공중:」을 다음 Z 조각 앞으로 옮김
        for k, (mid, s, t) in enumerate(m):
            nt = ov.get(mid, t)
            if nt is None:
                continue
            mm = re.search(r'(§Z\s*|^Z\s*)공중:\s*$', nt)
            if not mm:
                continue
            for j in range(k + 1, len(m)):
                nid, ns, ntt = m[j]
                cur = ov.get(nid, ntt)
                if cur and cur[:1] == 'Z' and cur[1:].strip():
                    ov[nid] = 'Z 공중: ' + cur[1:].lstrip(' ')
                    rest = nt[:mm.start()]
                    ov[mid] = rest if rest not in ('', 'Z') else ('Z' if nt[:1] == 'Z' else 'N')
                    break
        # 겹친 띄어쓰기
        for k, (mid, s, t) in enumerate(m):
            if mid in ov and ov[mid]:
                ov[mid] = re.sub(r'공중:\s+', '공중: ', ov[mid])
        # 쉼표만 남은 조각(「N,」)이 공중 줄 바로 앞이면 뺌
        for k, (mid, s, t) in enumerate(m):
            nt = ov.get(mid, t)
            if nt in ('N,', 'N, ') and k + 1 < len(m) and '공중' in (ov.get(m[k + 1][0], m[k + 1][2]) or ''):
                ov[mid] = 'N'
    json.dump(ov, open(ovp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('설명', n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
