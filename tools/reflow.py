"""파츠 설명 묶음 줄바꿈 다시 맞추기(1편 build_full.reflow_block 을 옮겨 옴, 2026-11-07).

설명 묶음 = 조각 목록. 첫 조각은 접두 없음, 「Z」로 시작하는 조각은 새 줄, 다른 접두(N M I H K L)는 같은 줄에 이어짐(색 바꿈).
일본어 줄바꿈 자리를 그대로 쓰면 한국어가 창 밖으로 나가므로, 폭 W 를 넘는 낱말을 다음 줄로 넘긴다.
다음 줄이 같은 글을 잇고 있으면(들여쓰기 같음) 그 줄 앞에 붙이고, 아니면 새 Z 줄을 만든다. 색 구간은 지킨다.
"""
import re
from join_raw import attaches
from check_raw_width import width as raw_width

PARTICLE_START = re.compile(r'(을|를|의|와|과|은|는|에|로|으로)(?= |$)')


def icon_width(t, icon=None):
    """줄 폭. icon 을 주면 버튼 아이콘(#a 등)을 그 폭으로 셈(튜토리얼 창은 아이콘이 글자보다 넓음)."""
    w = raw_width(t)
    if icon:
        w += len(re.findall(r'#[a-zA-Z]', t)) * (icon - raw_width('□'))
    return w


def reflow_block(segs, W, icon=None, hang='', flat=False):
    segs = list(segs)
    for i in range(1, len(segs)):   # Z 줄이 조사로 시작하면 윗줄 끝으로 올림
        t = segs[i]
        if t[:1] != 'Z':
            continue
        ind = re.match(r'[ 　]*', t[1:]).group(); body = t[1 + len(ind):]
        m = PARTICLE_START.match(body)
        j = i - 1
        while j > 0 and re.fullmatch(r'[ZMNLIHK][ 　]*', segs[j]):
            j -= 1
        if m and re.search(r'[가-힣]$', segs[j].rstrip()):
            segs[j] = segs[j].rstrip() + m.group(1); segs[i] = 'Z' + ind + body[m.end():].lstrip(' ')
    for i in range(2, len(segs)):   # 빈 Z 줄 뒤(일본어가 조사로 줄을 시작)도 같게
        t = segs[i]
        if t[:1] not in 'NM' or not re.fullmatch(r'Z[ 　]*', segs[i - 1]):
            continue
        m = PARTICLE_START.match(t[1:])
        if m and re.search(r'[가-힣]$', segs[i - 2].rstrip()):
            segs[i - 2] = segs[i - 2].rstrip() + m.group(1); segs[i] = t[0] + t[1 + m.end():].lstrip(' ')
    lines = [[('N', segs[0])]]
    for t in segs[1:]:
        if t[:1] == 'Z':
            lines.append([('N', t[1:])])
        else:
            lines[-1].append((t[0], t[1:]))

    def text(l): return ''.join(x for _, x in l)
    def indent(l): return re.match(r'[ 　]*', l[0][1]).group()
    out = []; i = 0
    while i < len(lines):
        l = lines[i]
        if icon_width(text(l), icon) <= W:
            out.append(l); i += 1; continue
        ind = indent(l); flat = [(k, st, ch) for k, (st, x) in enumerate(l) for ch in x]
        cut = None; acc = ''
        for j, (k, st, ch) in enumerate(flat):
            acc += ch
            if ch == ' ' and j >= len(ind) and acc.strip(' 　') and icon_width(acc.rstrip(), icon) <= W:
                cut = j
        if cut is None:                 # 낱말 하나가 W 보다 넓음: 그대로 둠(보고에 넘침으로 남음)
            out.append(l); i += 1; continue
        head = []; tail = []
        for j, (k, st, ch) in enumerate(flat):
            if j == cut:
                continue
            tgt = head if j < cut else tail
            if tgt and tgt[-1][0] == k:
                tgt[-1][2] += ch
            else:
                tgt.append([k, st, ch])
        out.append([(st, x) for _, st, x in head])
        tail = [(st, x) for _, st, x in tail]
        if not tail:
            i += 1; continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        ntext = text(nxt) if nxt is not None else ''
        header = re.match(r'[ 　]*[^ 　]{1,4}[:：]', ntext)
        bullet = re.match(r'[ 　]*[・·]', ntext)      # 다음 줄이 새 항목(・)이면 이어 붙이지 않음
        label = nxt is not None and any(st == 'K' for st, x in nxt[:2]) and not ''.join(x for _, x in nxt[:1]).strip()   # 「방어력：」 항목 이름 줄엔 이어 붙이지 않음
        if nxt is not None and ntext.strip(' 　') and not header and not bullet and not label and (indent(nxt) or not indent(l)):
            nind = indent(nxt); rest = nxt[0][1][len(nind):]
            lead = [('N', nind + tail[0][1])] if tail[0][0] == 'N' else [('N', nind), tail[0]]
            nxt_rest = nxt[1:]
            if not rest and nxt_rest and nxt_rest[0][1][:1] not in (' ', '　') and not attaches(nxt_rest[0][1], ''.join(x for _, x in tail)):
                nxt_rest = [(nxt_rest[0][0], ' ' + nxt_rest[0][1])] + nxt_rest[1:]
            tail_text = ''.join(x for _, x in tail)   # 앞말을 같이 넘겨야 「4발로 되고」처럼 띄어 씀
            lines[i + 1] = lead + tail[1:] + ([('N', ('' if attaches(rest, tail_text) else ' ') + rest)] if rest else []) + nxt_rest
        else:
            # 새 줄: 글머리(・) 줄에서 넘친 꼬리는 일본어처럼 한 칸 들여씀
            nind = '' if flat else ind if ind else (hang or (' ' if re.match(r'[・·]', text(l)) else ''))   # hang: 항목 이름 뒤 글 시작에 맞춘 들여쓰기(11/08)
            lead = [('N', nind + tail[0][1])] if tail[0][0] == 'N' else [('N', nind), tail[0]]
            lines.insert(i + 1, lead + tail[1:])
        i += 1
    res = []; last = 'N'
    for n, l in enumerate(out):
        for k, (st, x) in enumerate(l):
            if k == 0 and (st != 'N' or (n and last != 'N')):
                # Z(줄바꿈)는 앞 색을 이어 가므로, 앞 줄이 색 구간으로 끝났으면 N 으로 되돌림(11/08 「대회.」 뒤 노란색 번짐)
                res += ['' if n == 0 else 'Z', st + x]
            else:
                res.append((x if n == 0 else 'Z' + x) if k == 0 else st + x)
            last = st
    return res


def reflow_dense(segs, W, merge=True):
    """파츠 설명 빼곡히(11/07 사용자): 항목(・ 줄, 「지상:」 같은 머리 줄)마다 일본어 줄 자리를 버리고 이어 붙인 뒤
    낱말 중간에서도 끊어 한 줄을 W 까지 꽉 채움(keep-all 아님). 이어지는 줄은 한 칸 들여씀. 색 구간은 지킴."""
    lines = [[('N', segs[0])]]
    for t in segs[1:]:
        if t[:1] == 'Z':
            lines.append([('N', t[1:])])
        elif t[0] == 'N' and re.match(r'[ 　]*[^ 　:：・·]{1,4}[:：]', t[1:]) and ''.join(x for _, x in lines[-1]).strip(' 　・·'):
            lines.append([('N', ' ' + t[1:].lstrip(' 　'))])   # 줄 중간 「공중:」 머리는 새 줄(11/07)
        else:
            lines[-1].append((t[0], t[1:]))

    def text(l): return ''.join(x for _, x in l)
    items = []
    for l in lines:
        tx = text(l)
        if not merge or not items or re.match(r'[ 　]*[・·]', tx) or re.match(r'[ 　]*[^ 　]{1,4}[:：]', tx) or not tx.strip(' 　'):
            items.append([list(p) for p in l]); continue
        prev = items[-1]
        for p in reversed(prev):   # 앞 항목 끝 공백 정리
            if p[1].strip(' '):
                p[1] = p[1].rstrip(' '); break
            p[1] = ''
        body = [list(p) for p in l]
        body[0][1] = body[0][1].lstrip(' 　')
        sep = '' if attaches(text(body), text(prev)) else ' '
        if sep:
            if body[0][0] == 'N':
                body[0][1] = sep + body[0][1]
            else:
                prev.append(['N', sep])
        prev += body
    out = []
    for it in items:
        flat = [(st, ch) for st, x in it for ch in re.findall(r'#[a-zA-Z]|.', x)]   # #a 같은 아이콘 코드는 쪼개지 않음
        s = ''.join(c for _, c in flat)
        cont = ' ' if re.match(r'[ 　]*[・·]', s) else re.match(r'[ 　]*', s).group()
        lastreal = max((i for i, (_, c) in enumerate(flat) if c.strip(' 　')), default=-1)
        # 끝 마침표가 칸을 넘으면 매달지 않고 뺌(11/08 사용자: 테두리에 닿는 점은 삭제)

        def wrap(keepall):
            lines = [[]]; curtx = ''
            for fi, (st, ch) in enumerate(flat):
                if curtx.strip(' 　') and icon_width(curtx + ch) > W:
                    if fi == lastreal and ch in '.。':
                        continue                     # 넘치는 끝 마침표는 뺌
                    if keepall and ch != ' ':
                        sp = max((i for i, (_, c) in enumerate(lines[-1]) if c == ' ' and i > len(cont)), default=-1)
                        if sp <= 0:
                            return None              # 한 낱말이 한 줄보다 김
                        moved = lines[-1][sp + 1:]; lines[-1] = lines[-1][:sp]
                        lines.append([('N', c) for c in cont] + moved); curtx = ''.join(c for _, c in lines[-1])
                    else:
                        lines.append([('N', c) for c in cont]); curtx = cont
                        if ch == ' ':
                            continue
                    if icon_width(curtx + ch) > W and not (fi == lastreal and ch in '.。'):
                        return None
                    if fi == lastreal and ch in '.。' and icon_width(curtx + ch) > W:
                        continue
                lines[-1].append((st, ch)); curtx += ch
            return lines
        dense = wrap(False)
        ka = wrap(True)
        # 낱말 단위로 바꿔도 줄 수가 안 늘면 낱말째 내림(11/08 사용자)
        lines = ka if ka is not None and len(ka) <= len(dense) else dense
        for ln in lines:
            cur = []
            for st, ch in ln:
                if cur and cur[-1][0] == st:
                    cur[-1][1] += ch
                else:
                    cur.append([st, ch])
            out.append(cur)
    res = []; last = 'N'
    for n, l in enumerate(out):
        l = [(st, x) for st, x in l if x or st != 'N'] or [('N', '')]
        for k, (st, x) in enumerate(l):
            if k == 0 and (st != 'N' or (n and last != 'N')):
                # Z(줄바꿈)는 앞 색을 이어 가므로, 앞 줄이 색 구간으로 끝났으면 N 으로 되돌림(11/08 노란색 번짐)
                res += ['' if n == 0 else 'Z', st + x]
            else:
                res.append((x if n == 0 else 'Z' + x) if k == 0 else st + x)
            last = st
    return res


def edit_to_segs(text):
    """설명 편집기 글(줄 = 화면 항목·줄, [ ] = 노랑, {X:…} = 다른 색) → 한 조각 글(§ 표시)."""
    out = []
    for n, line in enumerate(text.split('\n')):
        if not line.strip():
            continue
        if n and out:
            out.append('§Z')
        pos = 0
        for m in re.finditer(r'\[([^\]]*)\]|\{([A-Z]):([^}]*)\}', line):
            if m.start() > pos:
                out.append('§N' + line[pos:m.start()])
            out.append('§M' + m.group(1) if m.group(1) is not None else '§' + m.group(2) + m.group(3))
            pos = m.end()
        if pos < len(line):
            out.append('§N' + line[pos:])
    s = ''.join(out)
    s = s[1:] if s.startswith('§') else s
    return re.sub(r'§Z§N', '§Z', s)


def edited_block(text, W):
    """편집기 글을 그대로(입력 줄 = 화면 줄 시작) 빼곡히 줄바꿈한 조각 목록."""
    parts = split_marks([edit_to_segs(text)])
    return reflow_dense([parts[0][1:]] + parts[1:], W, merge=False)


COLOR_MARK = '§'   # 번역 안 「§M」: 그 자리부터 M(노란 강조) 등 새 색 조각으로 나눔(조각 경계와 다른 데서 색을 바꿀 때, 11/07)


def split_marks(parts):
    """조각 목록에서 「§X」(X = N M L I H K) 표시를 새 조각으로 나눔."""
    out = []
    for t in parts:
        bits = t.split(COLOR_MARK)
        out.append(bits[0])
        out += [b for b in bits[1:] if b]
    return out


def drop_periods(parts):
    """파츠 설명은 원문처럼 문장 끝 마침표를 뺌(창이 좁아서, 사용자 11/07). 말줄임표는 그대로."""
    return [re.sub(r'(?<![.…])[.。](\s*)$', r'\1', t) for t in parts]


def lines_of(segs):
    """조각 목록 → 화면 줄 목록."""
    out = [segs[0]]
    for t in segs[1:]:
        if t[:1] == 'Z':
            out.append(t[1:])
        else:
            out[-1] += t[1:]
    return out
