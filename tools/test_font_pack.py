"""font_pack 시험: (0) 압축 묶음을 부팅 때 그대로 푸는지, (1) boot 루틴이 원래 1비트 글꼴을 원래 초기화와 바이트까지 같게 펼치는지,
(2) 훅이 한글 글리프를 카트에서 읽어 펼친 결과가 파이썬 expand 와 같은지, 캐시 키·되돌림값이 맞는지."""
import struct
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import *
from survey_rom import ROOT
import font_cache as F, font_pack as P, name_input as N
from build_full import glyph_bitmap, FONT
from PIL import ImageFont

rom = bytearray((ROOT / 'Custom Robo V2 (Japan).z64').read_bytes())
BASE = 0x802E4400
BLOB = bytes(rom[0x4FB38:0x4FB38 + 40000]) + bytes(rom[0x87CA0:0x87CA0 + 60000]) + bytes(5000) + bytes(rom[0x11A8D0:0x11A8D0 + 50000])
BLOB += bytes((-len(BLOB)) % 16)
RT = BASE + len(BLOB)
code, rt = P.runtime_code(RT, BASE, len(BLOB))
comp = P.pack(BLOB); assert P.unpack(comp, len(BLOB)) == BLOB
chunk = code + comp; chunk += bytes((-len(chunk)) % 8)
print('묶음', len(BLOB), '→ 압축', len(comp))
font = ImageFont.truetype(str(FONT), 12)
glyphs = N.KS[:300] + N.JAMO
ko = P.korean_rom_bytes([glyph_bitmap(font, c) for c in glyphs])
KO_ROM = 0x1000000            # 시험용 카트 위치
uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_BIG_ENDIAN)
uc.mem_map(0, 0x400000)
uc.mem_map(0x10000000, 0x2000000)            # 카트(0xB0000000 → 물리 0x10000000)
uc.mem_write(0x10000000, bytes(rom[:0x1000000]))
uc.mem_write(0x10000000 + KO_ROM, ko)
F.patch  # noqa
blob = (0x1100000, RT, len(chunk))
img = bytearray(rom) + bytes(0x200000)
P.patch(img, KO_ROM, len(glyphs), blob, rt)
uc.mem_write(0x25c60, bytes(img[0x1060:0x52990]))       # seg0
ret = lambda u: u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))


def service(u, address, size, data):
    if address == F.DMA:
        s = u.reg_read(UC_MIPS_REG_A0); d = u.reg_read(UC_MIPS_REG_A1) & 0x1fffffff; n = u.reg_read(UC_MIPS_REG_A2)
        if s < 0x1000000:
            u.mem_write(d, bytes(rom[s:s + n]))
        elif s == 0x1100000:
            u.mem_write(d, chunk[:n])
        ret(u)
    elif address == 0x802856c0:
        u.reg_write(UC_MIPS_REG_V0, F.SCRATCH); ret(u)
    elif address in (0x8003a948, 0x8004c3d0):
        ret(u)
for a in (F.DMA, 0x802856c0, 0x8003a948, 0x8004c3d0):
    uc.hook_add(UC_HOOK_CODE, service, begin=a, end=a)
uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: None)   # cache 명령은 unicorn 이 무시
uc.reg_write(UC_MIPS_REG_SP, 0x803f0000); uc.reg_write(UC_MIPS_REG_RA, 0x80001000)
uc.emu_start(F.INIT, 0x80001000, count=50000000)
G0 = bytes(uc.mem_read(BASE & 0x1fffffff, len(BLOB))); print('부팅 직후 풀기 같음:', G0 == BLOB, hex(uc.reg_read(UC_MIPS_REG_PC)))
got = bytes(uc.mem_read(F.TEXTURES & 0x1fffffff, (F.GLYPHS + 1) * 96))
exp = F.original_expanded(bytes(rom))
print('부팅 펼치기 원래와 같음:', got == exp)
G = bytes(uc.mem_read(BASE & 0x1fffffff, len(BLOB))); d = next((i for i in range(len(BLOB)) if G[i] != BLOB[i]), None)
print('묶음 풀기 같음:', d is None, d, G[d:d+8].hex() if d is not None else '', BLOB[d:d+8].hex() if d is not None else '')
bad = 0
for i in [0, 1, 93, 94, 1000 % len(glyphs), 299, 300, len(glyphs) - 1]:
    code_ = N.idx2code(i)
    uc.reg_write(UC_MIPS_REG_A0, int.from_bytes(code_, 'big')); uc.reg_write(UC_MIPS_REG_A1, 0x00300000 | 0x80000000)
    uc.reg_write(UC_MIPS_REG_SP, 0x803f0000); uc.reg_write(UC_MIPS_REG_RA, 0x80001000)
    uc.emu_start(F.LOOKUP, 0x80001000, count=200000)
    v0 = uc.reg_read(UC_MIPS_REG_V0); w = struct.unpack('>I', uc.mem_read(0x300000, 4))[0]
    tex = bytes(uc.mem_read(v0 & 0x1fffffff, 96))
    ok = tex == F.expand(glyph_bitmap(font, glyphs[i])) and w == 12
    bad += not ok
    print(glyphs[i], hex(int.from_bytes(code_, 'big')), '슬롯', hex(v0), '같음' if ok else '다름')
print('훅 불일치', bad)
