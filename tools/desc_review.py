"""파츠 설명 줄인 안 대조표(work/translation/desc/review.md): 원문 / 지금 / 수정안(빌드 줄바꿈 뒤 화면 줄).

usage: python -X utf8 desc_review.py <후보.json>
「지금」은 지금 번역을 조각 그대로 넣은 모양(줄바꿈 다시 맞추기 전), 「수정안」은 후보를 넣고 빌드처럼 줄바꿈한 모양.
"""
import json, sys, copy
import check_desc_fit as F
import reflow, build_full as B


def main():
    disp = F.setup()
    before = {r['start']: r for _, r in F.evaluate(copy.deepcopy(disp))}
    cand = json.load(open(sys.argv[1], encoding='utf-8'))
    src_of = {'R%08X' % p: r['source'] for p, r in disp.items()}
    bysrc = {src_of[k]: v for k, v in cand.items()}
    for p, r in disp.items():
        if r['source'] in bysrc:
            r['translation'] = bysrc[r['source']]
    ov = B.TR / 'desc-overrides.json'              # 자리별 덮어쓰기가 원문 단위 후보보다 앞섬
    if ov.exists():
        for k, v in json.load(open(ov, encoding='utf-8')).items():
            if int(k[1:], 16) in disp:
                disp[int(k[1:], 16)]['translation'] = v
    after = F.evaluate(disp)
    out = ['# 파츠 설명 줄인 안 대조표', '',
           '- **지금**: 지금 롬처럼 조각을 원래 자리에 그대로 넣은 줄(창 120px 넘는 줄은 화면에서 잘림).',
           '- **수정안**: 줄인 번역을 넣고 빌드가 창 폭 120px에 맞춰 줄바꿈한 화면 줄.',
           '- 같은 원문을 쓰는 설명(여러 파츠 공용)은 한 번만 실음. ⚠ = 아직 안 들어감(바이트·줄 수).', '']
    seen = set(); n = 0
    for run, r in after:
        b = before[r['start']]
        key = tuple(m[1] for m in r['members'])
        if key in seen:
            continue
        seen.add(key)
        if [m[2] for m in r['members']] == [m[2] for m in b['members']]:
            continue
        n += 1
        now = reflow.lines_of([(b['members'][0][2] or b['members'][0][1])[1:]] +
                              [(t if t is not None else s) for _, s, t in b['members'][1:]])
        out.append(f"### {n}. {r['start']}{'' if r['ok'] else ' ⚠'}  (바이트 {r['bytes']}/{r['size']}, 줄 {len(r['lines'])}/{r['limit']})")
        out.append('| 원문 | 지금 | 수정안 |')
        out.append('|---|---|---|')
        rows = max(len(r['jp']), len(now), len(r['lines']))
        g = lambda a, i: (a[i].replace('|', '\\|') if i < len(a) else '')
        for i in range(rows):
            out.append(f"| {g(r['jp'], i)} | {g(now, i)} | {g(r['lines'], i)} |")
        out.append('')
    open(B.ROOT / 'work/translation/desc/review.md', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('설명', n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
