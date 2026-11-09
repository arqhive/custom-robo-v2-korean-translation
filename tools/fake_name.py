"""가짜 이름($B00) 한글 규칙 — 안 A (2026-10-23 사용자 결정).

게임 함수 0x8003B35C 는 주인공 이름(0x800F4080)을 세 단계로 바꿔 가짜 이름(0x800F4890)을 만든다.
  1단계 표 A(원래 탁점 붙이기)로 글자마다 바꿈 → 하나라도 바뀌면 끝
  2단계 글자 순서 뒤집기 → 바뀌면 끝
  3단계 표 B(원래 같은 행 모음 한 칸)로 바꿈
코드는 그대로 두고 표 A·B 뒤에 한글 짝을 붙인다.
  표 A 한글: 초성 예사소리 → 된소리(ㄱㄷㅂㅅㅈ → ㄲㄸㅃㅆㅉ)
  표 B 한글: 모음 한 칸(ㅏ→ㅣ→ㅜ→ㅔ→ㅗ→ㅏ, ㅑ→ㅠ→ㅖ→ㅛ→ㅑ, ㅓ→ㅡ→ㅐ→ㅓ, ㅕ↔ㅒ)
바꾼 글자가 완성형(KS X 1001)에 없으면 짝을 만들지 않는다(그 글자는 그대로).
표는 원래 자리(seg0 데이터)에 안 들어가므로 RAM 묶음에 두고 포인터 4개(0x8006F5BC~)만 바꾼다.
"""
import struct
import name_input as N

PTR_VA = 0x8006F5BC            # 표 A 원문, 표 A 결과, 표 B 원문, 표 B 결과 포인터
TABLE_ROM = (0x4FB38, 0x4FC0C, 0x4FCE0, 0x4FDF4)

L = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
V = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
TENSE = {'ㄱ': 'ㄲ', 'ㄷ': 'ㄸ', 'ㅂ': 'ㅃ', 'ㅅ': 'ㅆ', 'ㅈ': 'ㅉ'}
VROT = {'ㅏ': 'ㅣ', 'ㅣ': 'ㅜ', 'ㅜ': 'ㅔ', 'ㅔ': 'ㅗ', 'ㅗ': 'ㅏ',
        'ㅑ': 'ㅠ', 'ㅠ': 'ㅖ', 'ㅖ': 'ㅛ', 'ㅛ': 'ㅑ',
        'ㅓ': 'ㅡ', 'ㅡ': 'ㅐ', 'ㅐ': 'ㅓ', 'ㅕ': 'ㅒ', 'ㅒ': 'ㅕ'}
KS = set(N.KS)


def _dec(c):
    u = ord(c) - 0xAC00
    return u // 588, (u % 588) // 28, u % 28


def _enc(l, v, t):
    c = chr(0xAC00 + l * 588 + v * 28 + t)
    return c if c in KS else None


def tense(c):
    l, v, t = _dec(c)
    n = TENSE.get(L[l])
    return _enc(L.index(n), v, t) if n else None


def rotate(c):
    l, v, t = _dec(c)
    n = VROT.get(V[v])
    return _enc(l, V.index(n), t) if n else None


def pairs():
    a = [(c, tense(c)) for c in N.KS if tense(c)]
    b = [(c, rotate(c)) for c in N.KS if rotate(c)]
    return a, b


def fake_ref(name):
    """파이썬 기준 구현(한글만)."""
    a = ''.join((tense(c) or c) if c in KS else c for c in name)
    if a != name:
        return a
    r = name[::-1]
    if r != name:
        return r
    return ''.join((rotate(c) or c) if c in KS else c for c in name)


def _strip(b):
    """원래 표: 2바이트 글자 목록 + NUL."""
    n = b.index(0)
    assert n % 2 == 0
    return b[:n]


def tables(rom):
    """표 4개의 새 바이트(원래 글자 + 한글 짝 + NUL 2개)."""
    A, B = pairs()
    raw = [_strip(rom[o:o + 0x200]) for o in TABLE_ROM]
    assert len(raw[0]) == len(raw[1]) and len(raw[2]) == len(raw[3])
    code = lambda c: N.idx2code(N.KS.index(c))
    out = [raw[0] + b''.join(code(s) for s, _ in A), raw[1] + b''.join(code(d) for _, d in A),
           raw[2] + b''.join(code(s) for s, _ in B), raw[3] + b''.join(code(d) for _, d in B)]
    return [t + b'\0\0' for t in out]


def place(rom, base):
    """RAM base 에 둘 표 묶음(bytes)과, 롬 안 포인터 4개를 바꿀 (롬 오프셋, 값) 목록을 돌려준다."""
    from segments import segments
    s0 = segments(rom)[0]
    blob = bytearray()
    ptrs = []
    for t in tables(rom):
        blob += bytes((-len(blob)) % 4)
        ptrs.append(base + len(blob))
        blob += t
    po = s0['rom_start'] + PTR_VA - s0['ram']
    old = struct.unpack_from('>4I', rom, po)
    assert [o - s0['ram'] + s0['rom_start'] for o in old] == list(TABLE_ROM), [hex(x) for x in old]
    return bytes(blob), [(po + 4 * i, p) for i, p in enumerate(ptrs)]
