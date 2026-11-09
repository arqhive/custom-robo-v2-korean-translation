"""파츠 설명(「N・」로 시작하는 묶음) 줄바꿈 다시 맞춘 결과 보기.

usage: python -X utf8 check_reflow.py [찾을 말 ...]   (없으면 줄 수가 원문보다 많아진 묶음만)
폭 W = 120(설명창) 과 그 묶음 원문 가장 넓은 줄 중 큰 값, 줄 수 한계 = 원문 줄 수.
"""
import sys
import check_raw_width as C
import reflow
DESC_W = 120   # 설명창 실제 폭(스샷: 126·128px 줄이 120px 언저리에서 잘림)
from build_full import adjust_parts


def desc_blocks():
    """(묶음 행들, 일본어 조각, 한국어 조각(띄어쓰기 반영)) — 첫 조각 접두 N 은 뺌."""
    for b, jp, kr in C.blocks():
        if not b[0]['source'].startswith('N・'):
            continue
        yield b


def run(b, ko):
    jp = [r['source'] for r in b]
    parts = adjust_parts([ko.get(r['source'], r['source']) for r in b])
    first = parts[0][:1]
    segs = [parts[0][1:]] + parts[1:]
    jl = reflow.lines_of([jp[0][1:]] + jp[1:])
    W = max(DESC_W, max(C.width(l) for l in jl))
    new = reflow.reflow_block(segs, W)
    return W, jl, reflow.lines_of(new), first + new[0], new


def main():
    import json, os, re, join_raw as J
    rows = J.load(os.path.join(J.TR, 'raw-text-all.json'))
    src_of = {r['id']: r['source'] for r in rows}
    ko = {}
    for f in sorted(os.listdir(os.path.join(J.TR, 'out'))):
        if re.fullmatch(r'raw-\d\d\.json', f):
            for k, v in J.load(os.path.join(J.TR, 'out', f))['translations'].items():
                ko[src_of[k]] = v
    want = sys.argv[1:]; n = more = wide = 0
    for b in desc_blocks():
        W, jl, kl, _, _ = run(b, ko)
        n += 1
        isover = len(kl) > len(jl); iswide = any(C.width(l) > W for l in kl)
        more += isover; wide += iswide
        if (want and any(w in '\n'.join(kl) for w in want)) or (not want and (isover or iswide)):
            print('##', b[0]['id'], f'W={W} 줄 {len(kl)}/{len(jl)}')
            for l in kl: print('  ', C.width(l), l)
    print('설명 묶음', n, '줄 수 늘어남', more, '폭 넘침(끊을 데 없음)', wide)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
