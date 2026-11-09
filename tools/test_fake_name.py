"""가짜 이름 시험: 게임 함수 0x8003B35C 를 CPU 에뮬레이터로 돌려 한글 표(fake_name)를 넣은 결과를 기준 구현과 대조.
원래 가나 이름 결과가 그대로인지도 본다."""
import random, struct
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_BIG_ENDIAN
from unicorn.mips_const import UC_MIPS_REG_SP, UC_MIPS_REG_RA
from survey_rom import ROOT
from segments import segments
import name_input as N
import fake_name as F

rom = (ROOT / 'Custom Robo V2 (Japan).z64').read_bytes()
s0 = segments(rom)[0]
BASE = 0x802E8000
blob, ptrs = F.place(rom, BASE)
patched = bytearray(rom)
for o, v in ptrs:
    struct.pack_into('>I', patched, o, v)
rev = {N.idx2code(i): c for i, c in enumerate(N.KS + N.JAMO)}


def run(img, name_bytes):
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_BIG_ENDIAN)
    uc.mem_map(0, 0x400000)
    uc.mem_write(s0['ram'] & 0x1fffffff, bytes(img[s0['rom_start']:s0['rom_end']]))
    uc.mem_write(BASE & 0x1fffffff, blob)
    uc.mem_write(0x0F4080, name_bytes + b'\0\0')
    uc.reg_write(UC_MIPS_REG_SP, 0x803f0000)
    uc.reg_write(UC_MIPS_REG_RA, 0x80300000)
    uc.emu_start(0x8003B35C, 0x80300000, count=2000000)
    return bytes(uc.mem_read(0x0F4890, 40)).split(b'\0')[0]


def ko(s):
    return b''.join(N.idx2code(N.KS.index(c)) for c in s)


def unko(b):
    return ''.join(rev.get(b[i:i + 2]) or b[i:i + 2].decode('euc_jp') for i in range(0, len(b), 2))


bad = 0
for n in ['カスタム', 'タロウ', 'アイ', 'ナナ', 'ア', 'マモル']:      # 원래 동작 유지
    a, b = run(rom, n.encode('euc_jp')), run(patched, n.encode('euc_jp'))
    print(n, '→', b.decode('euc_jp'), '' if a == b else ' 원래와 다름!')
    bad += a != b
for n in ['철수', '지훈', '바다', '김치', '하야토', '민', '토마토', '나나', '한', '영희', '유리']:
    got = unko(run(patched, ko(n)))
    print(n, '→', got, '' if got == F.fake_ref(n) else ' 기준 ' + F.fake_ref(n))
    bad += got != F.fake_ref(n)
random.seed(2)
for _ in range(500):
    n = ''.join(random.choice(N.KS) for _ in range(random.randint(1, 6)))
    if random.random() < 0.2:
        n = n[:len(n) // 2 + len(n) % 2] + n[:len(n) // 2][::-1]          # 회문
    got = unko(run(patched, ko(n)))
    if got != F.fake_ref(n):
        bad += 1
        print('불일치', n, got, F.fake_ref(n))
A, B = F.pairs()
print('표 A 한글', len(A), '표 B 한글', len(B), '묶음', len(blob), '바이트 / 불일치', bad)
