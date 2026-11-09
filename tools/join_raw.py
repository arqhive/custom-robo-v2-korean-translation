"""화면 문자열 조각을 롬 순서대로 이어 붙여 묶음 경계를 넘는 어긋남을 찾는다.

같은 원문은 한 번역(raw-NN 결과를 원문 단위로 모음)이므로, 롬의 모든 자리에서 이어 붙인 모양을 본다.
묶음 = 붙어 있는 표시 문자열(앞 문자열 끝 NUL 뒤 4바이트 안에서 시작)이고 둘째부터 조각 접두(Z N M I H K L)로 시작하는 것.
Z는 줄바꿈, 나머지는 같은 줄로 이어 붙인다(접두 글자는 뺀다). 빌드도 이 규칙(join_parts)을 쓴다:
  - 같은 줄에 붙일 때 앞이 문장 부호(. ! ?)로 끝나고 뒤가 공백·부호가 아니면 띄어쓰기 하나를 넣는다.
  - 앞이 「.」로 끝나고 뒤 조각이 「.」로 시작하면(공유 조각 「N。」) 뒤의 「.」를 버린다.
  - 뒤 조각이 쉼표로 시작하면(공유 조각 「N、」) 앞 공백을 지우고, 앞이 쉼표로 끝나면 뒤 쉼표를 버린다.
  - 한글끼리 이어지면 띄어 쓰되, 뒤가 조사·어미로 시작하면 붙인다(1편 attaches 규칙).
출력: work/translation/out/raw-joined.txt (묶음별 원문·번역), 어긋남 목록은 화면에 출력.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
PREFIX = re.compile(r'^[ZNMIHKL](?=[^A-Za-z]|$)')  # 숫자는 와도 된다(M1년): 게임은 첫 글자를 늘 접두로 읽음
CHECKS = [
    (re.compile(r'(?<!\.)\.\s*\.(?!\.)'), '마침표 겹침'),
    (re.compile(r'[,，]\s*\.|\.\s*[,，]'), '쉼표·마침표 겹침'),
    (re.compile(r'[가-힣] {2,}[가-힣]'), '띄어쓰기 두 칸'),
    (re.compile(r'[가-힣][.!?](?=[가-힣])'), '부호 뒤 띄어쓰기 없음'),
    (re.compile(r' [.,!?]'), '부호 앞 띄어쓰기'),
    (re.compile(r'(므로|지만|면서)\s*(므로|지만|면서)'), '어미 겹침'),
]


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


# 1편 build_full.py 의 조각 띄어쓰기 규칙: 한글끼리 이어질 때 띄어 쓰되 조사·어미로 시작하면 붙인다
PARTICLES = {'을', '를', '이', '가', '은', '는', '의', '에', '와', '과', '도', '만', '로', '으로', '에서', '에게', '까지',
             '부터', '처럼', '보다', '이다', '다', '형', '용', '이고', '이며', '이라', '이므로', '이나', '나', '라', '란',
             '라고', '이라고', '이란', '엔', '에는', '에도', '으로는', '로는', '과는', '와는', '보다는', '만큼', '뿐',
             '이야', '야', '요', '죠', '지', '고', '며', '면', '므로', '으므로', '니까', '인', '임', '됨', '함', '할',
             '한', '된', '될', '하는', '되는'}
ENDINGS = ('하', '해', '했', '되', '돼', '됐', '으로', '에서', '에게', '까지', '부터', '처럼', '이라', '이다', '라고',
           '도록', '지만', '면서', '어서', '아서')  # 끝 다섯은 2편에서 더함(날아가 도록)
JIDA = {'지고', '지며', '지면', '지니', '진다', '졌다', '져서', '져', '지는', '진', '졌고', '져도'}
CONNECTIVE = set('만고며서면데니게어아여도는을를은이가의에와과로')


def attaches(body, prev=''):
    m = re.match(r'[가-힣]+', body)
    if not m:
        return not re.match(r'[0-9A-Za-z０-９Ａ-Ｚａ-ｚ(（『「#]', body)
    w, last = m.group(), prev.rstrip()[-1:]
    if w == '다' and body[1:2] == ' ':          # 낱말 「다」(모두): 「능력도 다 강해졌다」
        return False
    # 「높아」+「졌다」「커」+「지고」: 아/어 꼴 뒤 보조 용언 지다는 붙임(2편 파츠 설명 11/07)
    if w in JIDA and last and not prev.endswith(' ') and '가' <= last <= '힣' and (ord(last) - 0xAC00) % 28 == 0             and ((ord(last) - 0xAC00) // 28) % 21 in (0, 1, 4, 5, 9, 14):   # ㅏ ㅐ ㅓ ㅔ ㅘ ㅝ
        return True
    if w in ('한', '할', '된', '될', '함', '됨', '하는', '되는') and (not prev or prev.endswith(' ') or last in CONNECTIVE):
        return False
    pw = re.findall(r'[가-힣]+', prev)[-1:] or ['']
    # 「강하게 돼」「4발로 되고」「빠르게 했다」: 부사·조사 뒤 하다/되다는 띄움(2편 11/07 더함: 로·히)
    if w.startswith(('하', '해', '했', '한', '되', '돼', '됐', '된')) and (pw[0] in ('못', '안') or pw[0].endswith(('야', '게', '지', '고', '록', '로', '히', '을', '를', '은', '는', '이', '가', '도', '에', '와', '과'))):
        return False
    return w in PARTICLES or w.startswith(ENDINGS + ('한다', '된다', '했다', '됐다', '합니다', '됩니다'))


def join_parts(parts):
    """조각 목록을 화면 글로 잇는다(빌드와 같은 규칙)."""
    out = ''
    for i, s in enumerate(parts):
        if i and PREFIX.match(s):
            body = s[1:]
            if s[0] == 'Z':
                out += '\n' + body
                continue
            if out.endswith('.') and body.startswith('.') and not body.startswith('..'):
                body = body[1:]
            if body.startswith(','):  # 공유 조각 「N、」: 앞 조각이 쉼표로 끝나면 버리고, 앞 공백은 지운다
                out = out.rstrip(' ')
                if out.endswith(','):
                    body = body[1:]
            last = out[-1:]
            if re.search(r'[.!?]$', out) and body[:1] and not re.match(r'[\s.,!?…」）]', body):
                body = ' ' + body
            elif (last and not last.isspace() and body[:1] and '가' <= body[0] <= '힣'
                  and not re.search(r'#[a-zA-Z]$', out)
                  and ('가' <= last <= '힣' or last.isalnum() or last in ',)」』:：')
                  and not attaches(body, out)):
                body = ' ' + body
            out += body
        else:
            out += s
    return out


def main():
    rows = load(os.path.join(TR, 'raw-text-all.json'))
    src_of = {r['id']: r['source'] for r in rows}
    ko = {}
    for f in sorted(os.listdir(os.path.join(TR, 'out'))):
        if re.fullmatch(r'raw-\d\d\.json', f):
            for k, v in load(os.path.join(TR, 'out', f))['translations'].items():
                ko[src_of[k]] = v
    disp = sorted((r for r in rows if r.get('class') == 'display'), key=lambda r: r['rom_offset'])
    blocks, cur, end = [], [], -1
    for r in disp:
        cont = cur and r['area'] == cur[-1]['area'] and 0 <= r['rom_offset'] - end < 4 and PREFIX.match(r['source'])
        if not cont:
            if cur:
                blocks.append(cur)
            cur = []
        cur.append(r)
        end = r['rom_offset'] + r['bytes'] + 1
    if cur:
        blocks.append(cur)

    join = join_parts
    bad, lines = 0, []
    for b in blocks:
        if len(b) < 2:
            continue
        jp = join([r['source'] for r in b])
        kr = join([ko.get(r['source'], r['source']) for r in b])
        lines.append(f"## {b[0]['id']} ({b[0]['area']}, 조각 {len(b)})\n{jp}\n--\n{kr}\n")
        probs = [name for rx, name in CHECKS if rx.search(kr)]
        if probs:
            bad += 1
            print(b[0]['id'], '|', ', '.join(probs), '|', kr.replace('\n', '⏎')[:150])
    with open(os.path.join(TR, 'out', 'raw-joined.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('묶음', sum(1 for b in blocks if len(b) > 1), '어긋남', bad)


if __name__ == '__main__':
    main()
