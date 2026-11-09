"""이름 뒤 조사 모듈 시험(롬 빌드 없이): 모듈만 CPU 에뮬레이터에 올려 (이름, 조사) 마다 고른 글자를 확인.

글자 조회 입구에서 모듈로 들어가, 보통 글자는 그대로 HOOK 으로 넘어가는지,
조사 글자는 앞 글자 받침에 맞는 음절 코드로 바뀌어 HOOK 으로 가는지, {이}{으} 가 빠질 때 폭 0 빈 글자인지 본다.
"""
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_BIG_ENDIAN
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_RA, UC_MIPS_REG_PC, UC_MIPS_REG_V0
import font_cache, name_input, particles

VA = 0x802F0000
BLANK = font_cache.TEXTURES
glyphs = name_input.KS + name_input.JAMO
codes = {c: name_input.idx2code(i) for i, c in enumerate(glyphs)}
hangul = {c: v for c, v in codes.items() if '가' <= c <= '힣'}
pcodes = [name_input.idx2code(len(glyphs) + k) for k in range(len(particles.KINDS))]
SKIP = [int.from_bytes(c.encode('euc_jp'), 'big') for c in '』」）']   # 빌드와 같게(닫는 괄호 건너뜀)
mod, entry = particles.module(VA, hangul, pcodes, font_cache.HOOK, BLANK, SKIP)

uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_BIG_ENDIAN)
uc.mem_map(0, 0x400000)
uc.mem_write(VA & 0x1fffffff, mod)
RET = 0x80380000; WIDTH = 0x80300000
uc.mem_write(font_cache.HOOK & 0x1fffffff, bytes(8)); uc.mem_write(RET & 0x1fffffff, bytes(8))


def look(c):
    uc.mem_write(WIDTH & 0x1fffffff, b'\xff' * 4)
    uc.reg_write(UC_MIPS_REG_A0, int.from_bytes(c, 'big')); uc.reg_write(UC_MIPS_REG_A1, WIDTH); uc.reg_write(UC_MIPS_REG_RA, RET)
    uc.emu_start(entry, font_cache.HOOK, count=500)
    pc = uc.reg_read(UC_MIPS_REG_PC)
    if pc == font_cache.HOOK:
        return ('hook', (uc.reg_read(UC_MIPS_REG_A0) & 0xffff).to_bytes(2, 'big'))
    uc.emu_start(pc, RET, count=50)
    return ('blank', int.from_bytes(uc.mem_read(WIDTH & 0x1fffffff, 4), 'big'), uc.reg_read(UC_MIPS_REG_V0))


inv = {v: k for k, v in codes.items()}
fails = 0
# 0x8E·0x8F 를 건너뛴 뒤 리드(0x90~)에 있는 글자가 든 이름도 넣음
late = [c for c in name_input.KS if codes[c][0] >= 0x90][:3]
for name in ['레이', '영', '철', '진', '아키라', '삼', '켄', 'ㄱ', 'A'] + late:
    for k, (tok, sy) in enumerate(particles.KINDS):
        for ch in name:
            look(codes[ch] if ch in codes else ch.encode('euc_jp') if ord(ch) > 0x7f else chr(ord(ch) + 0xfee0).encode('euc_jp'))
        r = look(pcodes[k])
        want = sy[particles.final_class(name[-1])]
        got = inv.get(r[1]) if r[0] == 'hook' else None
        ok = (got == want) if want else (r[0] == 'blank' and r[1] == 0 and r[2] == BLANK)
        fails += not ok
        if not ok or name in ('레이', '철', '진'):
            print(name, tok, '->', got if r[0] == 'hook' else f'(빈칸 폭 {r[1]})', 'OK' if ok else f'틀림 (기대 {want})')
# 『이름』{을/를}: 닫는 괄호를 건너뛰고 이름 끝 글자로 고르는지(화면 문자열 「『%s』을(를) 실체화했습니다」, 11/08)
for name, want in [('스탠더드 봄', '을'), ('레이 건', '을'), ('드릴 포드', '를'), ('스타 레이어 건', '을')]:
    look('『'.encode('euc_jp'))
    for ch in name:
        look(codes[ch] if ch in codes else '　'.encode('euc_jp'))
    look('』'.encode('euc_jp'))
    r = look(pcodes[0]); got = inv.get(r[1])
    fails += got != want
    print('『%s』' % name, '{을/를} ->', got, 'OK' if got == want else '틀림')
print('닫는 괄호 자체는 그대로', look('』'.encode('euc_jp')) == ('hook', '』'.encode('euc_jp')))
print('보통 글자 그대로', look(codes['가']) == ('hook', codes['가']), look(codes['ㄱ']) == ('hook', codes['ㄱ']))
print('원래 글꼴 글자 그대로', look('あ'.encode('euc_jp')) == ('hook', 'あ'.encode('euc_jp')))
print('모듈', len(mod), '바이트, 틀린 수', fails)
