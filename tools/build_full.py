"""8단계 전체 한글 빌드 (커스텀 로보 V2). 1편 GPT초벌작/[N64]커스텀로보/tools/build_full.py 를 2편에 맞게 옮김.

usage: python -X utf8 build_full.py [출력 이름] (KO_OFF=scen,raw,keydict,name,images,particles 로 부분 끄기, 시험용)

넣는 것
  대사      스크립트 80개(표 ROM 0x87CA0, 기준 0x44B8B0). 들어가면 제자리, 길면 풀 끝에 붙이고 opcode 0x10 참조를 고침.
            0x13/0x14(용어 키·튜토리얼) 키 문자열은 표 제목 번역과 바이트까지 같게.
  화면 문자열 세그먼트 데이터의 표시 문자열. 포인터(데이터 낱말·lui/lo)로 닿는 묶음 단위로, 제자리에 안 들어가면
            RAM 묶음(0x802E4400~)으로 옮기고 포인터를 고침. 조각 이어 붙이기는 join_raw 규칙을 조각마다 반영.
  글꼴      고정 코드(완성형 2,350 + 자모 51, name_input.idx2code). 글리프는 ROM 뒤, 캐시 훅(font_cache).
  이름 비교 strcmp(0x8005F130) 훅: 한글 이름을 원래 일본어로 바꿔 비교(key_dict).
  이름 입력 오버레이 10 자모 격자·조합 루틴(name_input), 가짜 이름 한글 표(fake_name).
  그림      work/graphics/final 23장(그림 통합 폴더에서 복사, 10/30).
ROM 은 16MB 그대로. 스크립트는 원래 자리(0x44B8B0~0x55FFC0)에 차례로 다시 채우고, 글꼴은 1비트로 둔다(font_pack).
"""
from pathlib import Path
import collections, hashlib, json, os, re, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from survey_rom import ROOT, decode
from codec import encode
from build_opening_probe import crc6102
from segments import segments, seg_of_rom, code_refs
from check_dialogue import width as dlg_width, LINE_W, MAX_LINES, ADV_FIX, THIN
from check_dialogue import width as _dlg_width


def dlg_width(s):
    # 번역의   은 줄을 바꾸지 않는 띄어쓰기: 폭은 보통 공백, 롬에는 보통 공백으로 들어감(11/08 「해 두자」)
    return _dlg_width(s.replace(' ', ' '))
from check_raw_width import width as dlg_raw_width
import font_cache, font_pack, name_input, fake_name, key_dict, join_raw, particles, reflow
import make_batches
import check_translation as CT

SRC = ROOT / 'Custom Robo V2 (Japan).z64'
TR = ROOT / 'work/translation'
BLOB_VA = 0x802E4400
# 「」: 가나식 둥근 모서리가 한글 옆에서 깨져 보여 직각으로 다시 그림(1편과 같은 점, 12×12 (y, x))
BRACKETS = {'「': [(0, 2), (0, 3), (0, 4)] + [(y, 2) for y in range(1, 11)],
            '」': [(y, 3) for y in range(0, 10)] + [(10, 1), (10, 2), (10, 3)],
            THIN: []}   # 빈 글자
BLANK_GLYPH = 0                 # 원래 글꼴 0번 = 전각 공백: 조사 {이}{으} 가 빠질 때 그리는 빈 글자(폭 0)
BLOB_LIMIT = 0x8033F800
SCRIPT_BASE = 0x44B8B0
SCRIPT_END = 0x55FFC0              # 원래 스크립트 자리 끝
SCRIPT_DECODED_MAX = 0x28000        # 해제 버퍼 0x80180C60
SCRIPT_PACKED_MAX = 0x25800         # 압축 DMA 버퍼 0x80000400
FONT = Path('C:/Users/hgyst/AppData/Local/Microsoft/Windows/Fonts/Galmuri11.ttf')
PREFIX = set(b'ZNMIHKL')
TWO_BYTE_NAMES = (0xAA254, 0xAA570)  # 격투편 스테이지 이름표(激闘編~ＥＤ激闘編), 2바이트씩만 읽음
RESULT_SCREEN = (0xB17F0, 0xB1A80)   # 격투편 결과 화면 서식: 원판처럼 「.」「:」를 반각(1바이트)으로 둠(전각이면 칸이 밀림, 11/09)
ASCII_RAW = {'': b'.', '': b':'}   # enc_seg 에서 1바이트로 내보낼 표시 글자
CREDITS = (0xB1060, 0xB1440)        # 스태프 크레디트(직함·이름이 NUL 로 이어지고 빈 문자열이 단락)
GFX = ROOT / 'work/graphics/final'
REPORT = {}
OFF = set(filter(None, os.environ.get('KO_OFF', '').split(',')))
CONTROL = re.compile(r'\$(?:[A-Z]\d{2}|[A-Z])|#[a-zA-Z]')


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def literal(c):
    if c == '~': return '〜'
    if c == '·': return '・'
    if c == ' ': return '\u3000'
    if c == "'": return '’'
    if c == '"': return '”'
    if c == '-': return '−'           # 전각 －(U+FF0D)는 EUC-JP 에 없음
    if 0x21 <= ord(c) <= 0x7e: return chr(ord(c) + 0xfee0)
    return c


# ---------------------------------------------------------------- 번역 읽기
def load_dialogue():
    rows = make_batches.dialogue_rows()
    tr = {}
    for f in sorted(os.listdir(TR / 'out')):
        if re.fullmatch(r'dlg-\d\d\.json', f):
            # 이름 뒤 조사 {을/를} 등은 그릴 때 고름(particles, 1편과 같음)
            tr.update({k: particles.to_chars(v) for k, v in load(TR / 'out' / f)['translations'].items()})
    byid = {r['id']: r for r in rows}
    bysource = {}
    for k, v in tr.items():
        s = byid[k]['source']
        # 쪽 수는 원문과 같고, 쪽마다 줄바꿈은 원문보다 적어도 됨(짧게 다듬은 대사, 11/07)
        rv, rs = CT.r_per_page(v), CT.r_per_page(s)
        # 주인공 이름($A00)은 한국어에서 빼도 됨(「○○의 아줌마」→「아줌마」, 11/08 사용자). 나머지 코드는 원문과 같아야 함
        cv, cs = CT.codes_wo_r(v), CT.codes_wo_r(s)
        assert [c for c in cv if c != '$A00'] == [c for c in cs if c != '$A00'] and cv.count('$A00') <= cs.count('$A00')             and len(rv) == len(rs) and all(x <= y for x, y in zip(rv, rs)), k
        assert not re.search('[ぁ-ゟァ-ヺ一-鿿{}]', v), k
        assert bysource.get(s, v) == v, ('같은 원문 다른 번역', k)
        bysource[s] = v
    missing = [r['id'] for r in rows if r['source'] not in bysource]
    assert not missing, missing[:5]
    return rows, bysource


# 분류 규칙(classify_text INTERNAL 의 〓·^#)에 걸려 내부용으로 빠졌지만 화면에 나오는 원문(커스터마이즈 기체 이름 등)
FORCE_DISPLAY = {'レイ〓', '#Iレイ〓ダーク'}
# 「#」으로 시작해 내부용으로 빠졌던 버튼 안내·튜토리얼 조각·색 붙은 파츠 이름(11/07 사용자 「미번역」)
FORCE_DISPLAY |= set(json.loads((ROOT / 'work/translation/force-display-sources.json').read_text(encoding='utf-8')))
# 같은 원문이 내부 이름으로도 쓰여서(기체 동작 등) 이 자리만 화면 문자열로 다룸: 건 능력치 표의 「スピード」
FORCE_DISPLAY_IDS = {'R00127274', 'R001272E4', 'R000B0F7C'}   # + 모드 개방 안내창(ＶＳ 가 들어 내부용으로 분류됐음)
FORCE_DISPLAY_IDS |= {'R000593CC', 'R00059400'}   # 도움말 용어 목록의 「ポリス隊」「マモル」(내부용으로 분류돼 미번역, 11/08 사용자)
FORCE_DISPLAY_IDS |= {'R000591A4'}   # 격투편 일시정지 메뉴 「ジャンプ」(11/09 사용자 「미번역」)
# 커스터마이즈 확인창 「フェニックスガン」(내부용으로 분류돼 미번역, 11/09 사용자). 기체 동작 표(robo_moves) 사본은 그대로 둠
FORCE_DISPLAY_IDS |= {'R0004EAE8', 'R000CAFD8', 'R000FEF64', 'R0011C5C0', 'R0012A288'}
# 글자가 아니라 숫자 표의 값(우연히 가나 코드와 같음): 번역하면 표가 깨짐.
# R000FD68A 「ツ」= seg7 위치값 표 …9FB0,A5C4,ADF8… 의 0xA5C4. 「츠」로 바꾸면 다크 스타 배틀 진입 때 RAM 0x80000E80~0x8003AE80 이 0 으로 지워져 멈춤(11/09 사용자, 시험판으로 좁힘)
NOT_TEXT_IDS = {'R000FD68A'}
KEEP_BREAKS_IDS = {'S047-0145'}   # 줄바꿈을 번역문 그대로 둠(다시 채우지 않음): 「이름은」부터 새 줄(11/09 사용자)


def load_raw():
    rows = load(TR / 'raw-text-all.json')
    src_of = {r['id']: r['source'] for r in rows}
    ko = {}
    for f in sorted(os.listdir(TR / 'out')):
        if re.fullmatch(r'raw-\d\d\.json', f):
            for k, v in load(TR / 'out' / f)['translations'].items():
                ko[src_of[k]] = particles.to_chars(v)   # 화면 문자열에도 {을/를} 조사 자동(11/08)
    from check_translation import KEEP
    keep_src = {src_of[k] for k in KEEP}
    disp = {}
    for r in rows:
        if r.get('class') != 'display' and r['source'] not in FORCE_DISPLAY and r['id'] not in FORCE_DISPLAY_IDS:
            continue
        if r['id'] in NOT_TEXT_IDS:
            continue
        t = ko.get(r['source'])
        if r['source'] in keep_src or t == r['source']:
            t = None
        disp[r['rom_offset']] = dict(r, translation=t)
    # 스테이지 설명(seg6, 원문은 공백 4~6칸 들여쓰기): 왼쪽에 붙임(11/08 사용자: 공백만으론 가운데가 안 맞아서)
    for r in disp.values():
        m = re.match(r'^(Z)?( {2,})(\S.*)$', r['source'])   # 앞 공백 2칸 스테이지도(11/08 데드라인)
        if m and r['area'] == 'seg6' and r['translation']:
            t = r['translation']; z = 'Z' if t[:1] == 'Z' and m.group(1) else ''
            r['translation'] = z + t[len(z):].strip(' ')
    # 파츠 설명은 자리마다 따로 들어가므로 같은 원문이라도 자리별 번역을 덮어쓸 수 있음(11/07)
    ov = TR / 'desc-overrides.json'
    if ov.exists():
        for k, v in load(ov).items():
            p = int(k[1:], 16)
            if p in disp:
                disp[p]['translation'] = v
    # 서로 다른 일본어가 같은 한글이 되면 이름 비교(키 사전)가 한쪽으로만 되돌려 멈춤이 남(11/08 배틀 스퀘어 입장:
    # バトルスクエア·バトルスクウェア 둘 다 「배틀 스퀘어」). 가장 많이 쓰는 원문은 그대로 두고, 나머지에 끝 공백을 붙여 구별.
    groups = collections.defaultdict(lambda: collections.Counter())
    for r in disp.values():
        if r['translation'] is not None and r['source'][:1] not in 'ZNMIHKL':
            groups[r['translation']][r['source']] += 1
    for t, cnt in groups.items():
        if len(cnt) < 2:
            continue
        order = [s for s, _ in cnt.most_common()]
        for k, s in enumerate(order[1:], 1):
            for r in disp.values():
                if r['source'] == s and r['translation'] == t:
                    r['translation'] = t + ' ' * k   # 끝 공백으로 구별(빈 글자 THIN 은 능력치 칸 글꼴에서 「루」로 보임, 11/08)
        REPORT.setdefault('key_dict_split', []).append({'ko': t, 'keep': order[0], 'thin': order[1:]})
    # 격투편 스테이지 이름표: 글자를 2바이트씩만 읽음(글꼴 bsearch 0x8002AD10). 반각 공백·!·영숫자(1바이트)가 있으면
    # 표에 없는 코드를 찾다 멈춤(11/09 격투편 진입 멈춤, 「겐타의 배틀 포트」). 원판처럼 전각으로 바꿈.
    two = {r['source'] for r in disp.values() if TWO_BYTE_NAMES[0] <= r['rom_offset'] < TWO_BYTE_NAMES[1]}
    for r in disp.values():
        if r['source'] in two and r['translation']:
            r['translation'] = ''.join('　' if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c
                                       for c in r['translation'])
    for r in disp.values():
        if RESULT_SCREEN[0] <= r['rom_offset'] < RESULT_SCREEN[1] and r['translation']:
            r['translation'] = r['translation'].replace('.', '').replace(':', '')
    return disp


# ---------------------------------------------------------------- 글자
GLYPHS = {}


def _two(c):
    c = literal(c)
    b = GLYPHS[c] if c in GLYPHS else c.encode('euc_jp')
    assert len(b) == 2, repr(c)
    return b


def enc_dialogue(s):
    out, pos = [], 0
    for x in re.finditer(r'\$[A-Z]\d\d|\$[A-Z]|#[a-zA-Z]', s):
        out += [_two(c) for c in s[pos:x.start()]]
        out.append(x.group().encode('ascii'))
        pos = x.end()
    out += [_two(c) for c in s[pos:]]
    return b''.join(out)


def is_prefixed(raw):
    """원본 바이트가 접두 글자(ZNMIHKL)로 시작하는지. 다음 바이트가 ASCII 영문자면 그냥 낱말.
    (chr() 로 보면 EUC 첫 바이트 0xC0~ 가 라틴 글자로 잡혀 「Z電源」 같은 접두를 놓침)"""
    return bool(raw) and raw[0] in PREFIX and not (len(raw) > 1 and (0x41 <= raw[1] <= 0x5a or 0x61 <= raw[1] <= 0x7a))


def enc_seg(t, prefixed):
    """화면 문자열: 접두 글자·ASCII 공백·줄바꿈·%서식·#코드는 1바이트, 나머지 2바이트."""
    out, i = [], 0
    if prefixed and t[:1] in 'ZNMIHKL':
        out.append(t[0].encode()); i = 1
    while i < len(t):
        f = re.match(r'%[-+ #0]*\d*(?:\.\d+)?[sdxXuif]|#[a-zA-Z]', t[i:])
        if f:
            out.append(f.group().encode()); i += len(f.group()); continue
        if t[i] in ' \n':
            out.append(t[i].encode()); i += 1; continue
        if t[i] == '=':
            out.append(b'='); i += 1; continue
        if t[i] in ASCII_RAW:
            out.append(ASCII_RAW[t[i]]); i += 1; continue
        out.append(_two({'、': ',', '。': '.'}.get(t[i], t[i]))); i += 1
    return b''.join(out)


def glyph_bitmap(font, c):
    im = Image.new('1', (12, 12)); ImageDraw.Draw(im).text((0, -1), c, font=font, fill=1)
    full = Image.new('1', (14, 16)); ImageDraw.Draw(full).text((0, 1), c, font=font, fill=1)
    a = np.array(full)
    assert not a[:1].any() and not a[13:].any() and not a[:, 12:].any(), c
    return np.packbits(np.array(im, dtype=np.uint8).reshape(-1)).tobytes()


# ---------------------------------------------------------------- 대사 줄바꿈 (1편과 같은 규칙, 204px)
def _split_fit(text):
    cuts = [i for i, c in enumerate(text) if c in ' 　' and i > 0]
    for i in reversed(cuts):
        if dlg_width(text[:i].rstrip()) <= LINE_W and text[:i].strip(' 　'):
            return text[:i].rstrip(), text[i:].lstrip(' 　')
    i = len(text)
    while dlg_width(text[:i]) > LINE_W:
        i -= 1
    return text[:i], text[i:]


LINE3_W = 190   # 쪽의 셋째 줄: 오른쪽 아래 A 버튼 그림과 닿지 않게(1편과 같음, 11/07)


def korean_wrap(text):
    """한국식 줄바꿈(11/07 사용자): 일본판 줄 자리를 버리고 쪽마다 한 줄을 꽉 채워 내려 씀.
    쪽($P)은 그대로, 화자 이름 줄(다음 줄이 「 로 시작)과 $D 줄 뒤는 줄을 바꾼 채 둠.
    줄 중간 $W 는 낱말에 붙은 채 옮김. 세 줄을 넘으면 새 쪽으로 넘기고, 셋째 줄은 LINE3_W.
    한 낱말이 한 줄보다 길면 None(예전 방식으로)."""
    out = []
    for page in text.split('$P'):
        ls = page.split('$R')
        cont = '　' if any(l.startswith('　') for l in ls[1:]) or '「' in ls[0] else ''
        groups, cur = [], []
        for i, l in enumerate(ls):
            cur.append(l)
            if i + 1 < len(ls) and (ls[i + 1].startswith('「') or '$D' in l):
                groups.append(cur); cur = []
        groups.append(cur)
        pages, lines = [], []
        for g in groups:
            lead = re.match(r'^[　]*', g[0]).group(0)
            words = [w for w in (g[0][len(lead):] + ' ' + ' '.join(p.lstrip(' 　') for p in g[1:])).split(' ') if w]
            merged = []; i = 0   # 작은따옴표 안('커스텀 로보')은 한 덩어리로: 따옴표 안에서는 줄을 바꾸지 않음(11/08 사용자)
            while i < len(words):
                w = words[i]; j = i
                if w.count("'") % 2 == 1:
                    k = next((k for k in range(i + 1, min(i + 4, len(words))) if words[k].count("'") % 2 == 1), None)
                    if k is not None and dlg_width(' '.join(words[i:k + 1])) <= LINE_W:   # 한 줄보다 길면 따옴표 안에서도 줄을 바꿈
                        w = ' '.join(words[i:k + 1]); j = k
                merged.append(w); i = j + 1
            words = merged
            merged = []   # 「못 해」「안 돼」: 못·안은 뒤 낱말과 한 덩어리로 줄을 내림(11/08 사용자)
            for w in words:
                if merged and merged[-1] in ('못', '안'):
                    merged[-1] += ' ' + w
                elif merged and re.match(r'(거|것|수$)', re.sub(r'^\$[A-Z]\d\d', '', w)) and re.search(r'[가-힣]$', merged[-1]) and ' ' not in merged[-1]:
                    merged[-1] += ' ' + w   # 「될 거다」「할 수」: 의존 명사는 앞 낱말과 함께 내림(11/08 사용자)
                else:
                    merged.append(w)
            words = merged
            line = None
            for w in words:
                lim = LINE3_W if len(lines) == MAX_LINES - 1 else LINE_W
                if line is not None:
                    cand = line + ' ' + w
                    if dlg_width(cand) <= lim:
                        line = cand; continue
                    lines.append(line)
                    if len(lines) == MAX_LINES:
                        pages.append(lines); lines = []
                    lim = LINE3_W if len(lines) == MAX_LINES - 1 else LINE_W
                    line = cont + w
                else:
                    line = lead + w
                if dlg_width(line) > lim:
                    return None
            if line is not None:
                lines.append(line)
                if len(lines) > MAX_LINES:
                    return None
            if len(lines) == MAX_LINES and g is not groups[-1]:
                pages.append(lines); lines = []
        if lines:
            pages.append(lines)
        for i, pg in enumerate(pages):
            if i and not pg[0].startswith(('「', '　')):
                pg[0] = cont + pg[0] if cont else pg[0]
            if i < len(pages) - 1 and not re.search(r'\$W$', pg[-1]):
                pg[-1] += '$W'
        out.append('$P'.join('$R'.join(pg) for pg in pages))
    return '$P'.join(out)


def _refill_up(ls):
    """셋째 줄이 넘칠 때 윗줄 남는 칸으로 낱말을 끌어올림(둘째 줄부터, 안 되면 첫째 줄부터). 못 하면 None."""
    # 줄 중간 $W(버튼 대기)는 낱말에 붙은 채로 옮김: 「있어.$W 그러니까」처럼 한 줄 안에서 기다렸다 이어짐(11/07)
    last = len(ls) - 1
    l3 = ls[last]
    m = re.search(r'(\$W|\$V\d\d　?\$W|\$D)*$', l3)
    tail_code = l3[m.start():]
    cont = '　' if any(l.startswith('　') for l in ls[1:]) or '「' in ls[0] else ''
    over = [i for i, l in enumerate(ls) if dlg_width(l) > (LINE3_W if i == MAX_LINES - 1 else LINE_W)]
    if not over:
        return None
    for s in range(min(over), -1, -1):   # 넘치는 줄부터 시작해, 안 되면 한 줄씩 위로
        if any('$D' in ls[k] for k in range(s, last)):
            continue
        if any(ls[k + 1].startswith('「') for k in range(s, last)):   # 화자 이름 줄은 합치지 않음
            continue
        part = ls[s:last] + [l3[:m.start()]]
        first = part[0]
        lead = re.match(r'^[　]*', first).group(0)
        words = (first[len(lead):] + ' ' + ' '.join(p.lstrip(' 　') for p in part[1:])).split(' ')
        words = [w for w in words if w]
        n = MAX_LINES - s; res = []; cur = lead
        lim_at = lambda i: LINE3_W if s + i == MAX_LINES - 1 else LINE_W
        ok = True
        for w in words:
            pre = (cont if res else lead)
            cand = cur + w if cur == pre else cur + ' ' + w
            if dlg_width(cand) <= lim_at(len(res)):
                cur = cand; continue
            res.append(cur); cur = cont + w
            if len(res) >= n or dlg_width(cur) > lim_at(len(res)):
                ok = False; break
        if ok:
            res.append(cur)
            if len(res) <= n and all(r.strip(' 　') for r in res):
                res[-1] += tail_code
                return ls[:s] + res
    return None


def fix_third_lines(text):
    """셋째 줄이 LINE3_W 를 넘으면 윗줄 남는 칸을 먼저 쓰고, 그래도 안 되면 넘는 낱말을 다음 쪽(새 쪽)으로 넘김."""
    out = []
    for page in text.split('$P'):
        ls = page.split('$R')
        if len(ls) == MAX_LINES and dlg_width(ls[2]) > LINE3_W:
            r = _refill_up(ls)
            if r is not None:
                ls = r
        while len(ls) == MAX_LINES and dlg_width(ls[2]) > LINE3_W:
            l3 = ls[2]; tail_code = ''
            m = re.search(r'(\$W|\$V\d\d　?\$W|\$D)*$', l3)
            body = l3[:m.start()] if m else l3
            tail_code = l3[m.start():] if m else ''
            cuts = [i for i, c in enumerate(body) if c in ' 　' and i > 0 and dlg_width(body[:i].rstrip()) <= LINE3_W and body[:i].strip(' 　')]
            if not cuts:
                break
            i = cuts[-1]
            head, tail = body[:i].rstrip(), body[i:].lstrip(' 　')
            out.append('$R'.join(ls[:2] + [head + '$W']))
            ls = ['　' + tail + tail_code]
        out.append('$R'.join(ls))
    return '$P'.join(out)


def wrap_dialogue(text):
    kw = korean_wrap(text)
    if kw is not None and all(len(p.split('$R')) <= MAX_LINES and
                              all(dlg_width(l) <= (LINE3_W if j == MAX_LINES - 1 else LINE_W) for j, l in enumerate(p.split('$R')))
                              for p in kw.split('$P')):
        return kw, kw != text
    REPORT.setdefault('korean_wrap_fallback', []).append(text[:40])
    pages = text.split('$P'); out = []; changed = False
    for page in pages:
        lines = page.split('$R')
        if len(lines) <= MAX_LINES and all(dlg_width(l) <= LINE_W for l in lines):
            out.append(page); continue
        changed = True
        if len(lines) <= MAX_LINES:   # 쪽이 넘치면 다음 쪽으로 밀기 전에 윗줄 남는 칸부터 씀(11/07 사용자)
            r = _refill_up(lines)
            if r is not None and all(dlg_width(l) <= LINE_W for l in r):
                out.append('$R'.join(r)); continue
        groups, cur = [], []
        for i, l in enumerate(lines):
            cur.append(l)
            if l.endswith('$W') or i == len(lines) - 1:
                groups.append(cur); cur = []
        wrapped = []
        for g in groups:
            res, carry = [], ''
            for i, l in enumerate(g):
                t = l if not carry else '　' + carry + ' ' + l.lstrip(' 　')
                carry = ''
                while dlg_width(t) > LINE_W:
                    head, tail = _split_fit(t)
                    res.append(head)
                    if i < len(g) - 1:
                        carry = tail; t = None; break
                    t = '　' + tail
                if t is not None:
                    res.append(t)
            wrapped.append(res)
        pg, cur = [], []
        for res in wrapped:
            if len(cur) + len(res) <= MAX_LINES:
                cur += res; continue
            if cur:
                pg.append(cur); cur = []
            while len(res) > MAX_LINES:
                ch = res[:MAX_LINES]; res = res[MAX_LINES:]
                if not ch[-1].endswith('$W'):
                    ch[-1] += '$W'
                pg.append(ch)
                if not res[0].startswith(('「', '　')):
                    res[0] = '　' + res[0]
            cur = list(res)
        if cur:
            pg.append(cur)
        for ch in pg[:-1]:
            if not ch[-1].endswith('$W'):
                ch[-1] += '$W'
        out.append('$P'.join('$R'.join(ch) for ch in pg))
    res = '$P'.join(out)
    res2 = fix_third_lines(res)
    if res2 != res:
        res = res2; changed = True
    for p in res.split('$P'):
        ls = p.split('$R')
        assert len(ls) <= MAX_LINES, (text, res)
        for l in ls:
            if dlg_width(l) > LINE_W:
                REPORT.setdefault('overwide_lines', []).append(l)
    return res, changed


# ---------------------------------------------------------------- 대사
def build_scenarios(rom, append, rows, bysource, keys):
    files = load(ROOT / 'manifests/script-files.json')
    per = collections.defaultdict(list)
    allrows = load(TR / 'source-texts.json')
    for r in rows:
        per[r['script']].append(r)
    choices = load(TR / 'out/choices.json')['translations']   # 0x11 선택지 글(「たたかう」 등, 11/08 사용자 「미번역」)
    for r in allrows:            # 0x13/0x14 키 후보(내부 문자열 중 표 제목과 같은 것)
        if r['kind'] != 'dialogue' and (r['source'] in keys or r['id'] in choices):
            per[r['script']].append(r)
    stats = collections.Counter(); wraps = 0; built = {}
    for fid, entries in sorted(per.items()):
        f = files[fid]
        orig = (ROOT / f'work/extracted/scripts/{fid:03d}.bin').read_bytes()
        pool = f['string_pool']; data = bytearray(orig)
        words = list(struct.unpack_from('>%dI' % (pool // 4), orig, 0))
        first = min(struct.unpack_from('>%dI' % f['header_count1'], orig, 16))
        refs = collections.defaultdict(list); keyrefs = collections.defaultdict(list); choicerefs = collections.defaultdict(list)
        for i in range(first // 4, len(words) - 1):
            if words[i] >> 16 == 0x1000:
                refs[words[i + 1]].append(i + 1)
            if words[i] in (0x13000000, 0x14000000):
                keyrefs[words[i + 1]].append(i + 1)
            if words[i] >> 24 == 0x11:
                choicerefs[words[i + 1]].append(i + 1)
        code_vals = collections.Counter(words[first // 4:pool // 4])
        seen = set()
        for r in entries:
            if r['id'] in seen:
                continue
            seen.add(r['id'])
            p = r['offset']
            assert data[p:p + r['bytes']] == r['source'].encode('euc_jp'), r['id']
            if r['kind'] != 'dialogue' and r['id'] in choices:
                assert choicerefs.get(r['pool_offset']), (r['id'], 'opcode 0x11 참조 없음')
                b = enc_dialogue(choices[r['id']])      # 옛 글은 둠(다른 명령이 같은 문자열을 쓸 수 있음)
                new = len(data) - pool; data += b + b'\0'
                for i in choicerefs[r['pool_offset']]:
                    struct.pack_into('>I', data, 4 * i, new)
                stats['choices'] += 1
                continue
            if r['kind'] != 'dialogue':
                if not keyrefs.get(r['pool_offset']):
                    continue
                b = enc_seg(keys[r['source']], False)      # 키는 제자리에 두지 않음(다른 명령이 같은 문자열을 씀)
                new = len(data) - pool; data += b + b'\0'
                for i in keyrefs[r['pool_offset']]:
                    struct.pack_into('>I', data, 4 * i, new)
                stats['lookup_keys'] += 1
                continue
            if r['id'] in KEEP_BREAKS_IDS:
                text, ch = bysource[r['source']], False
            else:
                text, ch = wrap_dialogue(bysource[r['source']])
            text = text.replace(' ', ' ')
            wraps += ch
            b = enc_dialogue(text); old = r['bytes']
            if len(b) <= old:
                data[p:p + old] = b + bytes(old - len(b)); stats['in_place'] += 1
            else:
                assert refs.get(r['pool_offset']), (r['id'], 'opcode 0x10 참조 없음')
                new = len(data) - pool; data += b + b'\0'
                for i in refs[r['pool_offset']]:
                    struct.pack_into('>I', data, 4 * i, new)
                stats['relocated'] += 1; stats['refs_rewritten'] += len(refs[r['pool_offset']])
                # 옛 문자열을 0 으로(압축이 줄어듦). 고친 참조 말고 다른 낱말이 그 범위를 가리키면 그대로 둠
                po = r['pool_offset']; n_ref = len(refs[po])
                if code_vals[po] == n_ref and not any(code_vals[v] for v in range(po + 1, po + old + 1)):
                    data[p:p + old] = bytes(old); stats['old_zeroed'] += 1
        data += bytes((-len(data)) % 4)
        struct.pack_into('>I', data, 0, len(data))
        assert len(data) <= SCRIPT_DECODED_MAX, (fid, len(data))
        packed = encode(bytes(data)); assert decode(packed, 0)[0] == bytes(data)
        assert len(packed) <= SCRIPT_PACKED_MAX, (fid, len(packed))
        built[fid] = (packed, bytes(data))
        stats['scripts'] += 1
        stats['max_decoded'] = max(stats['max_decoded'], len(data))
        stats['max_packed'] = max(stats['max_packed'], len(packed))
    # 원래 스크립트 자리(SCRIPT_BASE~SCRIPT_END)를 비우고 원래 순서대로 다시 채운다. 넘치는 것만 빈 곳에.
    order = sorted(files, key=lambda e: e['rom_offset'])
    orig = {f['id']: bytes(rom[f['rom_offset']:f['rom_offset'] + f['compressed_size']]) for f in order}
    assert order[0]['rom_offset'] == SCRIPT_BASE and max(f['rom_offset'] + f['compressed_size'] for f in order) <= SCRIPT_END
    rom[SCRIPT_BASE:SCRIPT_END] = bytes(SCRIPT_END - SCRIPT_BASE)
    pos = SCRIPT_BASE
    for f in order:
        packed = built[f['id']][0] if f['id'] in built else orig[f['id']]
        if pos + len(packed) <= SCRIPT_END:
            a = pos; rom[a:a + len(packed)] = packed; pos = (a + len(packed) + 3) & ~3
        else:
            a = append(packed, f"script_{f['id']:03d}"); stats['scripts_overflow'] += 1
        struct.pack_into('>I', rom, f['table_entry'], a - SCRIPT_BASE)
    for f in order:
        want = built[f['id']][1] if f['id'] in built else decode(orig[f['id']], 0)[0]
        assert decode(rom, struct.unpack_from('>I', rom, f['table_entry'])[0] + SCRIPT_BASE)[0] == want, f['id']
    stats['script_area_used'] = pos - SCRIPT_BASE
    REPORT['scenario'] = dict(stats); REPORT['rewrapped_entries'] = wraps


# ---------------------------------------------------------------- 화면 문자열
def adjust_parts(parts):
    """join_raw.join_parts 와 같은 규칙을 조각마다 반영해 고친 조각 목록을 돌려준다(접두 유지)."""
    out = list(parts); text = ''
    for i, s in enumerate(out):
        if not (i and join_raw.PREFIX.match(s)):
            text += s; continue
        body = s[1:]
        if s[0] == 'Z':
            text += '\n' + body; continue
        if text.endswith('.') and body.startswith('.') and not body.startswith('..'):
            body = body[1:]
        if body.startswith(','):            # 공유 조각 「N、」: 앞 공백 지우고, 앞이 쉼표면 뒤 쉼표 버림
            if text.endswith(' ') and out[i - 1].endswith(' '):
                out[i - 1] = out[i - 1].rstrip(' '); text = text.rstrip(' ')
            if text.endswith(','):
                body = body[1:]
        last = text[-1:]
        if re.search(r'[.!?]$', text) and body[:1] and not re.match(r'[\s.,!?…」）]', body):
            body = ' ' + body
        elif (last and not last.isspace() and body[:1] and '가' <= body[0] <= '힣'
              and not re.search(r'#[a-zA-Z]$', text)
              and ('가' <= last <= '힣' or last.isalnum() or last in ',)」』:：')
              and not join_raw.attaches(body, text)):
            body = ' ' + body
        out[i] = s[0] + body
        text += body
    return out


# 파츠 설명(「N・」로 시작하는 단락): 창 폭에 맞춰 줄바꿈을 다시 함(1편 reflow_block, 11/07)
STAGE_R = 244         # 스테이지 설명 창 안쪽 폭(11/07 스샷 실측: 196px 줄이 왼쪽 28·오른쪽 20)
TUTORIAL_W, TUTORIAL_ICON = 242, 16   # seg1 튜토리얼·용어 창 폭, 버튼 아이콘 폭(1편과 같음)
DESC_W = 120          # 설명창 폭(스샷: 126·128px 줄이 120px 언저리에서 잘림)
DESC_LINES = (6, 4)   # 줄 수: 첫 단락(큰 칸) 6줄, 같은 파츠의 다음 단락(폭탄·포드 능력치 아래 칸) 4줄


NDOT = b'N\xa1\xa6'


def desc_runs(source, disp, covered):
    """포인터로 닿지 않는 파츠 설명 단락: 「N・」 조각에서 시작해 접두 조각이 NUL 하나 사이로 이어지는 데까지.
    파츠 데이터 안에서 이름 뒤에 붙어 있고(게임은 이름부터 접두 조각을 따라 읽음), 같은 파츠의 다음 단락도
    「N・」로 시작한다. 단락마다 [시작, 끝) 바이트 자리와 조각 (시작, 끝) 목록을 돌려줌."""
    runs = []
    for p in sorted(disp):
        if p in covered or not source.startswith(NDOT, p) or source[p - 1] != 0:
            continue
        if runs and p < runs[-1]['end']:
            continue
        mem = []; q = p
        while True:
            e = source.index(b'\0', q); mem.append((q, e)); q = e + 1
            if source[q] not in PREFIX or source.startswith(NDOT, q):
                break
        runs.append({'start': p, 'end': mem[-1][1] + 1, 'members': mem, 'next_ndot': source.startswith(NDOT, q)})
    return runs


DESC_EDIT_W = 115   # 편집기 글 설명 한 줄 폭: 116px 줄은 오른쪽 테두리에 닿음(11/08 스샷)
DESC_EDITED = TR / 'desc-edited.json'   # 설명 편집기로 고친 단락(마침표를 입력 그대로 둠, 11/07)
_EDITED = None


def desc_segments(raws, adj, idx, keep_periods=False):
    """설명 단락 하나: (새 조각 목록, 화면 줄, 폭 W, 줄 수 한계). raws = 원래 바이트, adj = 띄어쓰기 반영한 번역 조각."""
    jl = reflow.lines_of([raws[0].decode('euc_jp')[1:]] + [r.decode('euc_jp') for r in raws[1:]])
    W = max(DESC_W, max(dlg_raw_width(l) for l in jl))
    a = reflow.split_marks(adj if keep_periods else reflow.drop_periods(adj))
    new = reflow.reflow_dense([a[0][1:]] + a[1:], W)   # 설명은 빼곡히(keep-all 아님, 11/07)
    for i in range(len(new)):                      # 줄 끝 공백은 바이트만 먹음
        if i + 1 == len(new) or new[i + 1][:1] == 'Z':
            new[i] = new[i].rstrip(' ')
    kl = reflow.lines_of(new)
    while len(kl) > 1 and not kl[-1].strip():      # 끝 빈 줄은 화면에 안 보임: 줄 수에서 뺌
        kl = kl[:-1]
    return new, kl, W, max(DESC_LINES[min(idx, 1)], len(jl))


_SECOND = None


def desc_edited():
    global _EDITED
    if _EDITED is None:
        _EDITED = {int(k[1:], 16): v for k, v in load(DESC_EDITED).items()} if DESC_EDITED.exists() else {}
    return _EDITED


def second_paras():
    """롬 주소 순서로 단락(「N・」 조각부터 접두 조각이 이어지는 동안)을 세어, 바로 앞 단락 끝에 붙어 시작하는 단락 주소."""
    global _SECOND
    if _SECOND is None:
        src = {int(r['id'][1:], 16): r['source'] for r in load(TR / 'raw-text-all.json')}
        offs = sorted(src); _SECOND = set(); i = 0; prev = None
        while i < len(offs):
            if not src[offs[i]].startswith('N・'):
                i += 1; continue
            j = i + 1
            while j < len(offs) and src[offs[j]][:1] and ord(src[offs[j]][0]) in PREFIX and not src[offs[j]].startswith('N・'):
                j += 1
            if prev == i:
                _SECOND.add(offs[i])
            prev = j; i = j
    return _SECOND


def reflow_cluster(members, raws, texts, adj, newmem, targets, stats):
    """포인터 묶음 안의 설명 단락(「N・」로 시작해 접두 조각으로 이어짐)을 줄바꿈해 조각 목록을 다시 만듦.
    단락 첫 조각 자리만 원래 위치(포인터 대상일 수 있음)로 남기고 나머지는 위치 없음(None)."""
    out = []; i = 0; idx = 0; prev_run_end = None
    while i < len(members):
        if not raws[i].startswith(NDOT):
            out.append(newmem[i]); i += 1; continue
        j = i + 1
        while j < len(members) and raws[j][:1] and raws[j][0] in PREFIX and not raws[j].startswith(NDOT):
            j += 1
        idx = idx + 1 if prev_run_end == i else 0
        if members[i][0] in second_paras():   # 묶음이 갈라져도 롬에서 바로 앞 단락에 붙어 있으면 둘째(아래 4줄 칸, 11/07)
            idx = max(idx, 1)
        prev_run_end = j
        if all(t is None for t in texts[i:j]):
            out += newmem[i:j]; i = j; continue
        assert not any(members[k][0] in targets for k in range(i + 1, j)), ('설명 단락 중간에 포인터', hex(members[i][0]))
        if members[i][0] in desc_edited():   # 설명 편집기 글: 입력 줄 그대로, 폭 120px(11/07)
            t = desc_edited()[members[i][0]]
            t = re.sub(r'^(\[?)[・·]', lambda m: m.group(1), t, count=1)
            new = reflow.edited_block('・' + t if not t.startswith('[') else '[・' + t[1:], DESC_EDIT_W)
            kl = reflow.lines_of(new)
            while len(kl) > 1 and not kl[-1].strip():
                kl = kl[:-1]
            W = DESC_EDIT_W; limit = DESC_LINES[min(idx, 1)]
            if raws[j - 1] == b'Z' and new[-1] != 'Z':   # 원본 단락 끝 빈 줄(Z)은 남김: 두 단락을 한 창에 잇는 화면에서 줄이 붙음(11/08)
                new.append('Z')
        else:
            new, kl, W, limit = desc_segments(raws[i:j], adj[i:j], idx)
        if len(kl) > limit or any(dlg_raw_width(l.rstrip(' ').rstrip('.')) > W for l in kl):   # 끝 마침표는 매달림 허용
            REPORT.setdefault('desc_overflow', []).append({'id': 'R%08X' % members[i][0], 'lines': kl, 'limit': limit})
        out.append((members[i][0], enc_seg('N' + new[0], True)))
        out += [(None, enc_seg(x, True)) for x in new[1:]]
        stats['desc_reflowed'] += 1
        i = j
    return out


def label_indent(px):
    """px 만큼 비우는 들여쓰기: 반각 공백 7px + 빈 글자 THIN 3px 조합 중 가장 가까운 것."""
    a, b = min(((x, y) for x in range(px // 7 + 2) for y in range(7)), key=lambda ab: (abs(7 * ab[0] + 3 * ab[1] - px), ab[1]))
    return ' ' * a + THIN * b


def line_start_strip(segs):
    """도움말·튜토리얼 조각 목록에서 줄 맨 앞에 오는 반각 공백을 지움(11/08 사용자: 「 있다.」처럼 생겼다 없어졌다 함).
    segs[0] 은 접두 없음. Z 조각이 새 줄. 전각 공백(　) 들여쓰기와 「・」 항목의 둘째 줄 들여쓰기는 둠."""
    out = []; start = True; prev_line = ''; cur_line = ''
    for n, x in enumerate(segs):
        pre, t = ('', x) if n == 0 else (x[:1], x[1:])
        if pre == 'Z':
            start = True; prev_line = cur_line; cur_line = ''
        if start and t:
            if not re.match(r'[ 　]*[・·]', prev_line):
                t = t.lstrip(' ')
            if t:
                start = False
        cur_line += t
        out.append(pre + t)
    return out


def reflow_tutorial(members, raws, texts, adj, newmem, targets, stats):
    """seg1 튜토리얼·용어 쪽: 포인터마다 한 쪽(단락). 242px(아이콘 16px)를 넘는 줄이 있으면 1편처럼 줄바꿈을 다시 함."""
    if len(newmem) != len(members) or not any(t is not None for t in texts):
        return newmem
    ts = set(targets); runs = []
    for i, (p, _) in enumerate(members):
        if p in ts or not runs:
            runs.append([])
        runs[-1].append(i)
    out = []
    for run in runs:
        segs = [adj[k] for k in run]
        if any(t is None for t in segs) or len(run) < 2:
            out += [newmem[k] for k in run]; continue
        first_pre = is_prefixed(raws[run[0]])
        body = [segs[0][1:] if first_pre else segs[0]] + segs[1:]
        if any(not re.match('[ZNMIHKL]', x[:1]) for x in body[1:]):
            out += [newmem[k] for k in run]; continue
        # 「방어력：　…」 같은 항목 이름이 든 쪽(11/08 사용자): 들여쓰기를 모두 빼고 왼쪽에 붙임(창 세로가 모자라서)
        hang = ''
        labeled = any(re.match(r'^K *[^：:\n]{1,8}[：:]', x) for x in segs[1:]) or (first_pre and re.match(r'^K *[^：:\n]{1,8}[：:]', segs[0]))
        if labeled:
            hang = 'flat'
            body = [body[0].lstrip(' 　')] + [x[:1] + x[1:].lstrip(' 　') if x[:1] in 'ZK' else x for x in body[1:]]
        lines = reflow.lines_of(body)
        if not hang and max(reflow.icon_width(l, TUTORIAL_ICON) for l in lines) <= TUTORIAL_W and not any(reflow.COLOR_MARK in x for x in body):
            if line_start_strip(body) == body:
                out += [newmem[k] for k in run]; continue
            new = line_start_strip(body)           # 줄은 그대로, 줄 첫머리 공백만 지움
        else:
            body = reflow.split_marks(body)
            new = line_start_strip(reflow.reflow_block(body, TUTORIAL_W, icon=TUTORIAL_ICON, flat=(hang == 'flat')))
        jl = reflow.lines_of([raws[run[0]].decode('euc_jp', 'replace')[1 if first_pre else 0:]] + [raws[k].decode('euc_jp', 'replace') for k in run[1:]])
        kl = reflow.lines_of(new)
        if len(kl) > len(jl):
            REPORT.setdefault('tutorial_more_lines', []).append({'id': 'R%08X' % members[run[0]][0], 'lines': len(kl), 'jp': len(jl)})
        out.append((members[run[0]][0], enc_seg((segs[0][:1] if first_pre else '') + new[0], first_pre)))
        out += [(None, enc_seg(x, True)) for x in new[1:]]
        stats['tutorial_reflowed'] += 1
    return out


def reflow_desc(rom, source, disp, covered, stats):
    """설명 단락을 창 폭에 맞춰 줄바꿈을 다시 해서 원래 바이트 자리 안에 다시 씀(넘치면 조각별 제자리 넣기로 둠)."""
    runs = desc_runs(source, disp, covered); prev_end = None; idx = 0
    for run in runs:
        idx = idx + 1 if prev_end == run['start'] else 0     # 같은 파츠의 두 번째 단락(폭탄·포드 아래 칸)
        prev_end = run['end']
        mem = run['members']
        raws = [source[a:b] for a, b in mem]
        texts = [disp[a]['translation'] if a in disp else None for a, _ in mem]
        if all(t is None for t in texts):
            continue
        parts = [t if t is not None else r.decode('euc_jp', 'replace') for t, r in zip(texts, raws)]
        adj = adjust_parts(parts)
        jl = reflow.lines_of([raws[0].decode('euc_jp')[1:]] + [r.decode('euc_jp') for r in raws[1:]])
        W = max(DESC_W, max(dlg_raw_width(l) for l in jl))
        adj = reflow.split_marks(reflow.drop_periods(adj))
        new = reflow.reflow_block([adj[0][1:]] + adj[1:], W)
        for i in range(len(new)):                      # 줄 끝 공백은 바이트만 먹음
            if i + 1 == len(new) or new[i + 1][:1] == 'Z':
                new[i] = new[i].rstrip(' ')
        kl = reflow.lines_of(new)
        while len(kl) > 1 and not kl[-1].strip():   # 끝 빈 줄은 화면에 안 보임: 줄 수에서 뺌
            kl = kl[:-1]
        limit = max(DESC_LINES[min(idx, 1)], len(jl))
        body = b'\0'.join([enc_seg('N' + new[0], True)] + [enc_seg(x, True) for x in new[1:]]) + b'\0'
        size = run['end'] - run['start']
        if not run['next_ndot']:                       # 단락 뒤 0 채움(문자열 칸 남는 자리)도 씀, 끝 4바이트는 다음 자료일 수 있어 남김
            z = 0
            while source[run['end'] + z] == 0:
                z += 1
            size += max(0, z - 4)
        if len(kl) > limit or any(dlg_raw_width(l) > W for l in kl) or len(body) > size:
            REPORT.setdefault('desc_overflow', []).append(
                {'id': 'R%08X' % run['start'], 'lines': kl, 'limit': limit, 'bytes': [len(body), size]})
        if len(body) > size:
            stats['desc_too_long'] += 1; continue
        rom[run['start']:run['start'] + size] = body + bytes(size - len(body))
        covered.update(a for a, _ in mem); stats['desc_reflowed'] += 1


# 대전·데모 설정과 기체 동작 자료: 이름이 실수(float) 자료 바로 뒤에 붙어 있어 추출에서 빠진 자리(적 정보 화면의 파츠 이름 등)
INLINE_AREAS = [(0x3FAE70, 0x41F7D0), (0x980340, 0x9B6600),
                (0xFE000, 0x100000), (0x11A000, 0x128000)]   # seg7·seg10 파츠 자료(이름 앞이 실수 자료)


# 적 정보 화면(ENEMY) 커맨더 이름: 배틀 기록(0x980340~)에 있는 이름. 번역은 대사 화자 이름을 따름(11/07).
COMMANDER_NAMES = {
    '少年': '소년', '少女': '소녀', 'ユリエ': '유리에', 'カリン': '카린', 'シンイチ': '신이치', 'フカシ': '후카시',
    'ジロウ': '지로', 'ハヤオ': '하야오', 'カトレア': '카트레아', 'ジェイク': '제이크', 'ケンゴ': '켄고', 'リヒト': '리히트',
    'あやしい少年': '수상한 소년', 'シーザー': '시저', 'マモル': '마모루', 'トラジ': '토라지', 'あやしい少女': '수상한 소녀',
    'ロボキチ': '로보키치', 'スバル': '스바루', 'ゴウセツ': '고우세츠', 'ミナモ': '미나모', 'ホムラ': '호무라', 'じいや': '집사',
    'ツルギ・ヤイバ': '츠루기 형제', 'あやしい大男': '수상한 덩치', 'クレオパトラ': '클레오파트라', 'あやつられ少女': '조종된 소녀',
    'シノノメ': '시노노메', 'あやつられ少年': '조종된 소년', 'パンチ': '펀치', 'ゴロー': '고로', 'ロディ': '로디', 'ペペ': '페페',
    'サルエ': '사루에', 'サルヅカ': '사루즈카', 'サルムラ': '사루무라', 'イク': '이쿠', 'ナオキ': '나오키', 'マリ': '마리',
    'セイジ': '세이지', 'ジュウゾウ': '주조', 'サチコ': '사치코', 'ミツル': '미츠루', 'ツルギ＆ヤイバ': '츠&야', 'ピータロウ': '피타로',
    '友情コンビ': '우정 콤비', 'やみ戦士': '어둠의 전사', 'タクマ塾少年': '타쿠마 소년', 'タクマ塾少女': '타쿠마 소녀',   # 적 정보 칸에 다 안 들어가 줄임(11/08 사용자)
}


def patch_inline_names(rom, source, disp):
    """화면 문자열과 같은 일본어 이름이 위 구역에서 NUL 로 끝나는 자리에 있으면 제자리에 번역을 넣음(길이 안에서만).
    이름 비교(strcmp)는 키 사전이 일본어로 되돌림."""
    names = {}
    for p, r in disp.items():
        t, src = r['translation'], r['source']
        if t is None or len(src) < 2 or src[:1] in 'ZNMIHKL' or not re.search('[ぁ-ゟァ-ヺ一-鿿]', src):
            continue
        names.setdefault(src.encode('euc_jp'), t)
    cmd_keys = set()
    for j, k in COMMANDER_NAMES.items():   # 적 정보 화면 커맨더 이름 칸(internal 로 분류돼 빠져 있던 것)
        names.setdefault(j.encode('euc_jp'), k); cmd_keys.add(j.encode('euc_jp'))
    stats = collections.Counter(); done = set()
    for b in sorted(names, key=len, reverse=True):
        for a0, a1 in INLINE_AREAS:
            i = source.find(b, a0, a1)
            while i >= 0:
                e = i + len(b)
                prev2 = source[i - 2:i]
                if (source[e] == 0 and not any(i <= x < e for x in done) and rom[i:e + 1] == source[i:e + 1]
                        and not (len(prev2) == 2 and prev2[0] >= 0xA1 and prev2[1] >= 0xA1
                                 and not (i % 4 == 0 and (source[i - 4] & 0x7F) in range(0x3C, 0x45)))):   # 앞 4바이트가 실수면 이름 시작
                    k = enc_seg(names[b], False)
                    z = 0
                    if b in cmd_keys or a0 == 0x980340:   # 대전 기록의 커맨더·로보 이름 칸은 32바이트 고정 칸: 이름 뒤 0 바이트까지 써도 됨(끝 0 하나는 남김, 로보 이름 11/08 「独眼爺」)
                        while source[e + z] == 0 and rom[e + z] == 0:
                            z += 1
                    if len(k) <= len(b):
                        rom[i:e] = k + bytes(len(b) - len(k)); done.add(i); stats['in_place'] += 1
                    elif len(k) <= len(b) + z - 1:
                        rom[i:i + len(k)] = k; done.add(i); stats['in_slot'] += 1
                    else:
                        stats['too_long'] += 1
                i = source.find(b, i + 1, a1)
    return dict(stats)


def build_raw(rom, source, disp):
    S = segments(source)

    def overlap(a, b):
        return not (a['bss_end'] <= b['ram'] or b['bss_end'] <= a['ram'])
    segpos = [p for p in disp if seg_of_rom(S, p)]
    segids = sorted({seg_of_rom(S, p)['id'] for p in segpos})
    words = {s['id']: struct.unpack_from('>%dI' % ((s['rom_end'] - s['data_rom']) // 4), source, s['data_rom']) for s in S}
    crefs = {s['id']: code_refs(source, s) for s in S}
    bylui = collections.defaultdict(list)
    for s in S:
        for r in crefs[s['id']]:
            bylui[(s['id'], r[1])].append(r)
    pointers = collections.defaultdict(list)
    for sid in segids:
        s = S[sid]; ps = [p for p in segpos if seg_of_rom(S, p)['id'] == sid]
        lo = min(ps); hi = max(ps) + 400
        vlo = s['ram'] + lo - s['rom_start']; vhi = s['ram'] + hi - s['rom_start']
        for t in S:
            if t['id'] != sid and t['id'] != 0 and overlap(s, t):
                continue
            for i, w in enumerate(words[t['id']]):
                if vlo <= w < vhi:
                    pointers[s['rom_start'] + w - s['ram']].append(('data', t['data_rom'] + 4 * i))
            for r in crefs[t['id']]:
                if vlo <= r[5] < vhi:
                    pointers[s['rom_start'] + r[5] - s['ram']].append(('code', t['id'], r))

    def walk(p):
        mem = []
        cr = CREDITS[0] <= p < CREDITS[1]
        while True:
            e = source.index(b'\0', p); mem.append((p, e)); p = e + 1
            if cr:                       # 크레디트: 빈 문자열(단락)까지 구역 끝까지 한 묶음
                if p >= CREDITS[1]:
                    break
            elif source[p] not in PREFIX:
                break
        return mem
    ignored, blocks = [], {}
    for t in pointers:
        if source[t - 1] != 0:
            ignored.append(hex(t)); continue
        blocks[t] = walk(t)
    spans = sorted((mem[0][0], mem[-1][1], t) for t, mem in blocks.items())
    clusters = []
    for a, b, t in spans:
        if clusters and a <= clusters[-1]['end']:
            c = clusters[-1]; c['end'] = max(c['end'], b); c['targets'].append(t)
        else:
            clusters.append({'start': a, 'end': b, 'targets': [t]})
    stats = collections.Counter(); blob = bytearray(); patches = []; covered = set()
    for c in clusters:
        members = sorted({x for t in c['targets'] for x in blocks[t]})
        if not any(p in disp and disp[p]['translation'] is not None for p, _ in members):
            continue
        covered.update(p for p, _ in members)
        # 같은 묶음(이어 붙는 조각)마다 띄어쓰기 규칙 반영
        texts = [disp[p]['translation'] if p in disp and disp[p]['translation'] is not None else None for p, _ in members]
        raws = [source[p:e] for p, e in members]
        parts = [t if t is not None else r.decode('euc_jp', 'replace') for t, r in zip(texts, raws)]
        adj = adjust_parts(parts)
        # 색 조각 앞 띄어쓰기는 앞 조각 끝으로 옮김: 엔진이 조각째 다음 줄로 넘길 때 줄 첫머리에 공백이 남지 않게(11/08 「 샤이닝」「 커맨더」)
        for i in range(1, len(adj)):
            if adj[i][:1] in 'NMIHKL' and adj[i][1:2] == ' ' and adj[i][2:3] not in ('', ' ') and adj[i - 1] and not adj[i - 1].endswith(' '):
                adj[i] = adj[i][0] + adj[i][2:]
                if adj[i - 1].rstrip() != 'Z' and not adj[i - 1].endswith('§Z'):   # 바로 앞이 빈 줄바꿈(Z·§Z)이면 줄 첫머리라 공백은 그냥 뺌
                    adj[i - 1] += ' '
        newmem = []
        for i, ((p, e), t, r, a) in enumerate(zip(members, texts, raws, adj)):
            if t is None and a == parts[i]:
                newmem.append((p, r))
            else:
                pre = is_prefixed(r)
                if CREDITS[0] <= p < CREDITS[1]:   # 스태프 롤은 글자를 2바이트씩만 읽음: 반각(1바이트)이 있으면 멈춤(1편 11/05 함정), 공백은 전각으로
                    a = a.replace(' ', '　')
                newmem.append((p, enc_seg(a, pre)))
        plain_mem = newmem
        if 'reflow' not in OFF:
            newmem = reflow_cluster(members, raws, texts, adj, newmem, set(c['targets']), stats)
            if seg_of_rom(S, c['start'])['id'] == 1:
                newmem = reflow_tutorial(members, raws, texts, adj, newmem, c['targets'], stats)
        reflowed = [x for x in newmem] != [x for x in plain_mem]   # 줄바꿈을 다시 한 묶음은 이미 §를 나눴음(11/07 스탠더드 포드 줄 섞임)
        if not reflowed and any(t and reflow.COLOR_MARK in t for t in texts):          # 번역 안 §X: 그 자리부터 새 색 조각
            mem2 = []
            for (p, b), a in zip(newmem, adj) if len(newmem) == len(adj) else []:
                if reflow.COLOR_MARK in a:
                    bits = reflow.split_marks([a])
                    mem2.append((p, enc_seg(bits[0], is_prefixed(source[p:source.index(b'\0', p)]))))
                    mem2 += [(None, enc_seg(x, True)) for x in bits[1:]]
                else:
                    mem2.append((p, b))
            if mem2:
                newmem = mem2
        q = c['end'] + 1
        while q < len(source) and source[q] == 0:
            q += 1
        body = b'\0'.join(b for _, b in newmem) + b'\0'
        contiguous = all(members[i][1] + 1 == members[i + 1][0] for i in range(len(members) - 1))
        if len(body) + 1 <= q - c['start'] and contiguous:
            rom[c['start']:q] = body + bytes(q - c['start'] - len(body)); stats['in_place'] += 1
            offs = {}; pos = c['start']
            for p, b in newmem:
                if p is not None:
                    offs[p] = pos
                pos += len(b) + 1
            for t in c['targets']:
                if offs[t] != t:
                    patches.append((t, offs[t] - t, 'rom'))
            continue
        base = len(blob); offs = {}; pos = base
        for p, b in newmem:
            if p is not None:
                offs[p] = pos
            pos += len(b) + 1
        blob += body + b'\0'; blob += bytes((-len(blob)) % 4)
        for t in c['targets']:
            patches.append((t, offs[t], 'blob'))
        stats['relocated'] += 1
    newaddr = {}
    for t, v, kind in patches:
        s = seg_of_rom(S, t); old = s['ram'] + t - s['rom_start']
        newaddr[old] = old + v if kind == 'rom' else BLOB_VA + v
    lui_new = {}
    for t, v, kind in patches:
        s = seg_of_rom(S, t); old = s['ram'] + t - s['rom_start']; new = newaddr[old]
        for ref in pointers[t]:
            if ref[0] == 'data':
                struct.pack_into('>I', rom, ref[1], new); stats['data_ptr'] += 1
            else:
                _, sid, (va, lva, op, rs, rt, tg) = ref; seg = S[sid]
                lo_rom = seg['rom_start'] + va - seg['ram']; hi_rom = seg['rom_start'] + lva - seg['ram']
                if op == 0x0d:
                    hi, lo = new >> 16, new & 0xffff
                else:
                    hi, lo = ((new + 0x8000) >> 16) & 0xffff, new & 0xffff
                key = (sid, lva)
                if key in lui_new:
                    assert lui_new[key] == hi, ('같은 lui 를 다른 값이 씀', hex(lva))
                else:
                    for other in bylui[key]:
                        ot = other[5]; n2 = newaddr.get(ot, ot)
                        assert n2 >> 16 == hi or ((n2 + 0x8000) >> 16) & 0xffff == hi or other[0] == va, ('shared lui', hex(lva), hex(ot))
                    lui_new[key] = hi
                w = struct.unpack_from('>I', rom, hi_rom)[0]; struct.pack_into('>I', rom, hi_rom, (w & 0xffff0000) | hi)
                w = struct.unpack_from('>I', rom, lo_rom)[0]; struct.pack_into('>I', rom, lo_rom, (w & 0xffff0000) | lo)
                stats['code_ptr'] += 1
    # 파츠 설명 단락: 창 폭에 맞춰 줄바꿈을 다시 해서 단락 자리 안에 다시 씀
    if 'reflow' not in OFF:
        reflow_desc(rom, source, disp, covered, stats)
    # 포인터로 닿지 않는 표시 문자열(세그먼트 밖 표 포함): 제자리에 들어갈 때만
    kept = []
    for p, r in disp.items():
        if p in covered or r['translation'] is None:
            continue
        e = source.index(b'\0', p); raw0 = source[p:e]
        pre = is_prefixed(raw0)
        b = enc_seg(r['translation'], pre)
        if len(b) <= e - p:
            rom[p:e + 1] = b + bytes(e + 1 - p - len(b)); stats['unreferenced_in_place'] += 1
        else:
            stats['unreferenced_kept_original'] += 1; kept.append(r['id'])
    REPORT['raw'] = dict(stats); REPORT['raw_kept_original'] = kept; REPORT['raw_ignored_midstring_pointers'] = ignored
    return bytes(blob)


# ---------------------------------------------------------------- 그림
def to5551(a):
    a = a.astype(np.uint32); q = (a * 31 + 127) // 255
    return ((q[..., 0] << 11) | (q[..., 1] << 6) | (q[..., 2] << 1) | (a[..., 3] >= 128)).astype(np.uint16)


def apply_images(rom, append):
    import graphics_targets as GT
    streams = {r['offset']: r for r in load(ROOT / 'manifests/compressed-streams.json')}
    S = segments(rom)
    ui_tab, ui_base = 0x4A090, 0x8D7300
    s4 = S[4]; tex_tab = s4['rom_start'] + 0x8015A8BC - s4['ram']; tex_base = 0x62EAA0
    rep = []
    for t in GT.TARGETS:
        tid, bank, off, fmt, w, h, flip = t[:7]
        im = Image.open(GFX / f'{tid}.png').convert('RGBA')
        assert im.size == (w, h), tid
        if flip:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        a = np.array(im)
        orig, _ = decode(rom, off)
        if fmt in ('CI8', 'CI4'):
            npal = 256 if fmt == 'CI8' else 16
            pal = struct.unpack_from('>%dH' % npal, orig, 0)
            v = to5551(a)
            lut = {}
            for i, c in enumerate(pal):
                lut.setdefault(c, i)
            idx = np.vectorize(lambda c: lut[int(c)])(v).astype(np.uint8)
            if fmt == 'CI8':
                px = idx.tobytes(); head = orig[:512]
            else:
                f_ = idx.reshape(-1); px = bytes((f_[0::2] << 4) | f_[1::2]); head = orig[:32]
            new = head + px
        elif fmt == 'RGBA32':
            new = a.tobytes()
        else:                                    # RGBA16H: 머리 8바이트 + 픽셀
            new = orig[:8] + to5551(a).astype('>u2').tobytes()
        assert len(new) <= len(orig), (tid, len(new), len(orig))
        new = new + orig[len(new):]
        packed = encode(new); assert decode(packed, 0)[0] == new
        slot = streams[off]['stored_size']
        if len(packed) <= slot:
            rom[off:off + slot] = packed + bytes(slot - len(packed)); pos = off
        else:
            pos = append(packed, f'image_{tid}')
            if bank == 'ui':
                tab = list(struct.unpack_from('>93I', rom, ui_tab)); i = tab.index(off - ui_base)
                struct.pack_into('>I', rom, ui_tab + 4 * i, pos - ui_base)
            elif bank == 'world':
                tab = list(struct.unpack_from('>290I', rom, tex_tab))
                for i in [i for i, x in enumerate(tab) if x == off - tex_base]:
                    struct.pack_into('>I', rom, tex_tab + 4 * i, pos - tex_base)
            else:
                assert struct.unpack_from('>I', rom, 0xC5CC8)[0] == off - 0x1A6230, tid
                struct.pack_into('>I', rom, 0xC5CC8, pos - 0x1A6230)
        assert decode(rom, pos)[0] == new
        rep.append({'id': tid, 'moved': pos != off, 'packed': len(packed)})
    return {'inserted': len(rep), 'moved': [r['id'] for r in rep if r['moved']]}


# ---------------------------------------------------------------- main
def main(out_name):
    source = SRC.read_bytes(); rom = bytearray(source)
    assert crc6102(source) == source[16:24]
    free = (len(source.rstrip(b'\xff')) + 15) & ~15
    alloc = []

    def append(data, label):
        nonlocal free
        start = free
        assert start + len(data) <= len(rom) and rom[start:start + len(data)] == b'\xff' * len(data), (label, hex(start))
        rom[start:start + len(data)] = data; free = (start + len(data) + 15) & ~15
        alloc.append({'label': label, 'offset': start, 'bytes': len(data)}); return start

    rows, bysource = load_dialogue(); disp = load_raw()
    texts = list(bysource.values()) + [r['translation'] for r in disp.values() if r['translation']]
    used = {c for t in texts for c in t if '가' <= c <= '힣'}
    assert used <= set(name_input.KS), sorted(used - set(name_input.KS))[:20]
    glyphs = name_input.KS + name_input.JAMO
    GLYPHS.update({c: name_input.idx2code(i) for i, c in enumerate(glyphs)})
    hangul_codes = {c: v for c, v in GLYPHS.items() if '가' <= c <= '힣'}
    # 조사 자리 글자: 글리프 바로 뒤 번호(빈 칸). 그릴 때 조사 모듈이 앞 글자 받침을 보고 바꿈
    for k, (tok, _) in enumerate(particles.KINDS):
        GLYPHS[particles.CHAR[tok]] = name_input.idx2code(len(glyphs) + k)
    # 한글 아닌 글자가 원래 글꼴에 있는지
    codes = set(struct.unpack_from('>%dH' % font_cache.GLYPHS, source, 0x3EE40))
    other = {c for t in texts for c in CONTROL.sub('', t) if not ('가' <= c <= '힣') and c not in ' \n%=#' and c not in GLYPHS}
    nofont = []
    for c in sorted(other):
        try:
            b = literal(c).encode('euc_jp')
        except UnicodeEncodeError:
            nofont.append(c); continue
        if len(b) == 2 and int.from_bytes(b, 'big') not in codes:
            nofont.append(c)
    REPORT['chars_not_in_font'] = nofont
    keys = {}
    for r in disp.values():
        if r['translation'] is not None and r['source'][:1] not in 'ZNMIHKL':
            keys.setdefault(r['source'], r['translation'])
    if 'scen' not in OFF:
        build_scenarios(rom, append, rows, bysource, keys)
    blob = bytearray(build_raw(rom, source, disp) if 'raw' not in OFF else b'')
    if 'inline' not in OFF:
        REPORT['inline_names'] = patch_inline_names(rom, source, disp)
    REPORT['raw_blob_bytes'] = len(blob)
    # 이름 입력 + 가짜 이름
    blob += bytes((-len(blob)) % 16); mod, entry = name_input.module(BLOB_VA + len(blob)); blob += mod
    blob += bytes((-len(blob)) % 16)
    tbl, ptrs = fake_name.place(source, BLOB_VA + len(blob)); blob += tbl
    if 'name' not in OFF:
        for o, v in ptrs:
            struct.pack_into('>I', rom, o, v)
        S = segments(source); s10 = S[10]
        h = name_input.hook_bytes(entry); a = s10['rom_start'] + name_input.HOOK - s10['ram']
        assert source[a:a + 4] == bytes.fromhex('3c098022'); rom[a:a + len(h)] = h
        g = name_input.GRID_ROM
        assert source[g:g + 130].decode('euc_jp').startswith('アカサタナ') and source[g + 130] == 0
        rom[g:g + 130] = b''.join(GLYPHS.get(c) or c.encode('euc_jp') for c in name_input.GRID)
    # 이름 비교: 한글 → 원래 일본어
    pairs = {}
    for r in disp.values():
        if r['translation'] is None or r['source'][:1] in 'ZNMIHKL':
            continue
        ko = enc_seg(r['translation'], False); jp = r['source'].encode('euc_jp')
        if ko == jp:
            continue
        if ko not in pairs:
            pairs[ko] = jp
        elif pairs[ko] != jp:
            REPORT.setdefault('key_dict_collisions', []).append(r['source'])
    for j, k in COMMANDER_NAMES.items():   # 적 커맨더 이름도 비교 때 일본어로 되돌림(11/08 배틀 스퀘어 입장 멈춤)
        ko = enc_seg(k, False); jp = j.encode('euc_jp')
        if pairs.setdefault(ko, jp) != jp:
            REPORT.setdefault('key_dict_collisions', []).append(j)
    # 이름 뒤 조사: 글자 조회 입구(LOOKUP)가 먼저 이 모듈로 감
    blob += bytes((-len(blob)) % 16)
    pmod, pentry = particles.module(BLOB_VA + len(blob), hangul_codes,
                                    [GLYPHS[particles.CHAR[tok]] for tok, _ in particles.KINDS],
                                    font_cache.HOOK, font_cache.TEXTURES + BLANK_GLYPH * 96,
                                    [int.from_bytes(c.encode('euc_jp'), 'big') for c in '』」）'])
    blob += pmod
    REPORT['particles'] = {'entry': hex(pentry), 'bytes': len(pmod), 'kinds': [tok for tok, _ in particles.KINDS]}
    blob += bytes((-len(blob)) % 16)
    tab, tab_va, mask = key_dict.table(BLOB_VA + len(blob), list(pairs.items())); blob += tab
    REPORT['key_dict'] = {'entries': len(pairs), 'table': hex(tab_va)}
    blob = bytes(blob) + bytes((-len(blob)) % 16)
    # 묶음은 압축해 ROM 에 두고, 부팅 때 바로 뒤에 둔 루틴(펼치기·풀기)이 BLOB_VA 로 푼다
    rt_va = BLOB_VA + len(blob)
    rt_code, rt = font_pack.runtime_code(rt_va, BLOB_VA, len(blob))
    comp = font_pack.pack(blob); assert font_pack.unpack(comp, len(blob)) == blob
    chunk = rt_code + comp; chunk += bytes((-len(chunk)) % 8)
    assert rt_va + len(chunk) <= BLOB_LIMIT, len(chunk)
    REPORT['blob'] = {'ram': hex(BLOB_VA), 'bytes': len(blob), 'packed': len(comp), 'runtime': hex(rt_va)}
    # 글꼴: 원래 글꼴은 부팅 때 1비트에서 펼치고, 한글은 1비트(20바이트 간격)로 두고 캐시에 넣을 때 펼침
    font = ImageFont.truetype(str(FONT), 12)
    ko_rom = append(font_pack.korean_rom_bytes([glyph_bitmap(font, c) for c in glyphs]), 'korean_font_1bpp')
    chunk_rom = append(chunk, 'ram_blob_packed')
    REPORT['font'] = font_pack.patch(rom, ko_rom, len(glyphs), (chunk_rom, rt_va, len(chunk)), rt)
    font_codes = struct.unpack_from('>%dH' % font_cache.GLYPHS, source, 0x3EE40)
    for c, w in ADV_FIX.items():   # 원래 글꼴 폭 표(번호표 바로 뒤, 글자당 1바이트)
        rom[0x3EE40 + 2 * font_cache.GLYPHS + font_codes.index(int.from_bytes(c.encode('euc_jp'), 'big'))] = w
    for c, pix in BRACKETS.items():
        a_ = np.zeros((12, 12), np.uint8)
        for y, x in pix:
            a_[y, x] = 1
        i = font_codes.index(int.from_bytes(c.encode('euc_jp'), 'big'))
        rom[font_cache.FONT_ROM + 18 * i:font_cache.FONT_ROM + 18 * i + 18] = np.packbits(a_.reshape(-1)).tobytes()
    a = font_cache.rom_of(font_cache.LOOKUP)
    assert rom[a:a + 8] == font_cache.asm(f'j {font_cache.HOOK}\nnop', font_cache.LOOKUP)
    if 'particles' not in OFF:
        rom[a:a + 8] = font_cache.asm(f'j {pentry}\nnop', font_cache.LOOKUP)
    c = key_dict.code(tab_va, mask); a = font_cache.rom_of(key_dict.CODE_VA)
    assert rom[a:a + len(c)] == bytes(len(c)); rom[a:a + len(c)] = c
    if 'keydict' not in OFF:
        a = font_cache.rom_of(key_dict.STRCMP)
        assert rom[a:a + 8] == bytes.fromhex('9082000090a30000')
        rom[a:a + 8] = key_dict.hook_bytes(key_dict.CODE_VA)
    if 'images' not in OFF:
        REPORT['images'] = apply_images(rom, append)
    # 필요 없는 뒤쪽은 자르지 않음(32MB 고정)
    rom[16:24] = crc6102(rom)
    out = ROOT / 'build' / out_name; out.parent.mkdir(exist_ok=True); out.write_bytes(rom)
    REPORT.update(file=str(out.relative_to(ROOT)), md5=hashlib.md5(rom).hexdigest(), sha256=hashlib.sha256(rom).hexdigest(),
                  crc6102=rom[16:24].hex(), allocations=alloc, rom_used_end=hex(free), off=sorted(OFF))
    (ROOT / 'manifests/full-build.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=1), encoding='utf-8')
    show = {k: v for k, v in REPORT.items() if k not in ('allocations', 'overwide_lines', 'font', 'raw_kept_original', 'raw_ignored_midstring_pointers')}
    print(json.dumps(show, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'Custom Robo V2 (Japan) [KO test].z64')
