"""화면 문자열 묶음(조각 이어 붙인 글)의 줄 폭 검사: 한국어 줄이 같은 묶음 원문의 가장 넓은 줄보다 넓으면 넘침 후보.

usage: python -X utf8 check_raw_width.py [찾을 말 ...]   (찾을 말을 주면 그 말이 든 묶음만 자세히)
줄 폭 = 반각 공백 7, 한글 12, 그 밖은 원래 글꼴 폭 표(check_dialogue.ADV). 접두 글자(ZNMIHKL)는 빼고 잼.
"""
import json, os, re, sys
import join_raw as J
from check_dialogue import ADV, literal


def width(t):
    t = re.sub(r'%[-+ #0]*\d*[sd]', '12345', t)
    t = re.sub(r'#[a-zA-Z]', '□', t)
    return sum(7 if c == ' ' else 12 if '가' <= c <= '힣' else ADV.get(literal(c), 12) for c in t)


def blocks():
    rows = J.load(os.path.join(J.TR, 'raw-text-all.json'))
    src_of = {r['id']: r['source'] for r in rows}
    ko = {}
    for f in sorted(os.listdir(os.path.join(J.TR, 'out'))):
        if re.fullmatch(r'raw-\d\d\.json', f):
            for k, v in J.load(os.path.join(J.TR, 'out', f))['translations'].items():
                ko[src_of[k]] = v
    disp = sorted((r for r in rows if r.get('class') == 'display'), key=lambda r: r['rom_offset'])
    out, cur, end = [], [], -1
    for r in disp:
        cont = cur and r['area'] == cur[-1]['area'] and 0 <= r['rom_offset'] - end < 4 and J.PREFIX.match(r['source'])
        if not cont:
            if cur: out.append(cur)
            cur = []
        cur.append(r); end = r['rom_offset'] + r['bytes'] + 1
    if cur: out.append(cur)
    for b in out:
        jp = J.join_parts([r['source'] for r in b])
        kr = J.join_parts([ko.get(r['source'], r['source']) for r in b])
        yield b, jp, kr


def main():
    want = sys.argv[1:]
    over = 0
    for b, jp, kr in blocks():
        if want and not any(w in kr or w in jp for w in want):
            continue
        jw = max(width(l) for l in jp.split('\n'))
        bad = [l for l in kr.split('\n') if width(l) > jw]
        if want:
            print('##', b[0]['id'], b[0]['area'], '원문 최대', jw)
            for l in jp.split('\n'): print('  JP', width(l), l)
            for l in kr.split('\n'): print('  KO', width(l), l, '  <== 넘침' if width(l) > jw else '')
        elif bad:
            over += 1
            print(b[0]['id'], b[0]['area'], jw, '|', ' / '.join(f'{width(l)} {l}' for l in bad)[:160])
    if not want:
        print('넘침 묶음', over)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
