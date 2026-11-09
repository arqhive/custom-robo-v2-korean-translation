"""Korean glyph cache for Custom Robo V2 (same scheme as Custom Robo 1, V2 addresses).

Original font initializer (0x8002A390) loads overlay 9, gets a scratch buffer from it
(0x802D18B0), DMAs the 1,672 1bpp glyphs there, expands them to I4 textures at
0x800ACBF0 (96 bytes each) and fills the fallback texture at 0x800D3EF0 with 0xFF.
The replacement keeps those side effects (overlay load, buffer, raw glyph DMA) but
DMAs the pre-expanded textures, then uses the rest of the old function body for the
lookup hook, cache keys and slot table. Unused CJK textures hold cached Hangul.
Hangul code -> glyph index follows name_input.idx2code (leads 0x81..0x8D, 0x90..; 0x8E·0x8F skipped).
"""
from pathlib import Path
import struct,json
import numpy as np
from keystone import Ks, KS_ARCH_MIPS, KS_MODE_MIPS32, KS_MODE_BIG_ENDIAN
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_PC, UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2
from unicorn.mips_const import UC_MIPS_REG_A3, UC_MIPS_REG_V0, UC_MIPS_REG_V1

ROOT=Path(__file__).resolve().parents[1]
GLYPHS=1672
FONT_ROM=0x14b420            # 18-byte 1bpp glyphs
INIT=0x8002a390
INIT_END=0x8002acd0          # comparator follows
LOOKUP=0x8002ad08
HOOK=0x8002a460
FALLBACK=0x8002a740
KEYS=0x8002a760
TEXTURES=0x800acbf0
DMA=0x8003a87c
SCRATCH=0x802d18b0
SLOTS=272                    # 320 -> 272: frees the initializer tail for key_dict (strcmp map)
CURSOR=KEYS+2*SLOTS
SLOT_TABLE=(CURSOR+4+15)&~15
assert SLOT_TABLE+2*SLOTS<=INIT_END
CAND=[r['index'] for r in json.loads((ROOT/'manifests/font-unused-candidates.json').read_text(encoding='utf-8')) if r['char']!='皇']
SLOT_INDICES=CAND[:SLOTS]
assert len(SLOT_INDICES)==SLOTS

def rom_of(va):return va-0x80025c60+0x1060

def asm(code,address):
    k=Ks(KS_ARCH_MIPS,KS_MODE_MIPS32|KS_MODE_BIG_ENDIAN)
    return bytes(k.asm('.set noreorder\n'+code,addr=address)[0])

def expand(bits):
    a=np.unpackbits(np.frombuffer(bits,dtype=np.uint8)).reshape(12,12)
    out=np.zeros((13,16),dtype=np.uint8)
    out[:12,:12]=a*15
    out[:12,1:13]|=a*3
    out[1:13,:12]|=a*3
    out[1:13,1:13]|=a*3
    flat=out[:12].reshape(-1)
    return ((flat[::2]<<4)|flat[1::2]).tobytes()

def original_expanded(rom):
    """Run the original initializer (MIPS32 emulation) and check the offline expansion."""
    uc=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_BIG_ENDIAN)
    uc.mem_map(0,0x400000)
    uc.mem_write(0x25c60,rom[0x1060:0x52990])
    uc.reg_write(UC_MIPS_REG_SP,0x803f0000);uc.reg_write(UC_MIPS_REG_RA,0x80001000)
    ret=lambda u:u.reg_write(UC_MIPS_REG_PC,u.reg_read(UC_MIPS_REG_RA))
    def service(u,address,size,data):
        if address==DMA:
            src=u.reg_read(UC_MIPS_REG_A0);dst=u.reg_read(UC_MIPS_REG_A1)&0x1fffffff;n=u.reg_read(UC_MIPS_REG_A2)
            u.mem_write(dst,rom[src:src+n]);ret(u)
        elif address==0x802856c0:u.reg_write(UC_MIPS_REG_V0,SCRATCH);ret(u)
        elif address in (0x8003a948,0x8004c3d0):ret(u)
        elif address in (0x80052274,0x800521d0):
            value=(u.reg_read(UC_MIPS_REG_A0)<<32)|u.reg_read(UC_MIPS_REG_A1);shift=u.reg_read(UC_MIPS_REG_A3)&63
            r=(value<<shift)&0xffffffffffffffff if address==0x80052274 else value>>shift
            u.reg_write(UC_MIPS_REG_V0,r>>32);u.reg_write(UC_MIPS_REG_V1,r&0xffffffff);ret(u)
    for a in (DMA,0x802856c0,0x8003a948,0x8004c3d0,0x80052274,0x800521d0):uc.hook_add(UC_HOOK_CODE,service,begin=a,end=a)
    uc.emu_start(INIT,0x80001000,count=30000000)
    assert uc.reg_read(UC_MIPS_REG_PC)==0x80001000
    result=bytes(uc.mem_read(TEXTURES&0x1fffffff,(GLYPHS+1)*96))
    expected=b''.join(expand(rom[p:p+18]) for p in range(FONT_ROM,FONT_ROM+GLYPHS*18,18))+b'\xff'*96
    assert expected==result,'offline expansion differs from the original initializer'
    return result

def init_code(tex_rom,blob=None):
    extra=f'''
        li $a0,{blob[0]}
        li $a1,{blob[1]}
        li $a2,{blob[2]}
        jal {DMA}
        nop''' if blob else ''
    return asm(f'''
        addiu $sp,$sp,-32
        sw $ra,28($sp)
        jal 0x8003a948
        li $a0,9
        jal 0x802856c0
        nop
        lui $at,0x800d
        jal 0x8004c3d0
        sw $v0,0x3f58($at)
        li $a0,{FONT_ROM}
        lui $a1,0x800d
        lw $a1,0x3f58($a1)
        jal {DMA}
        li $a2,{GLYPHS*18}
        li $a0,{tex_rom}
        li $a1,{TEXTURES}
        li $a2,{(GLYPHS+1)*96}
        jal {DMA}
        nop{extra}
        li $t0,{KEYS}
        li $t1,{CURSOR+4}
    clear:
        sw $zero,0($t0)
        addiu $t0,$t0,4
        bne $t0,$t1,clear
        nop
        lw $ra,28($sp)
        addiu $sp,$sp,32
        jr $ra
        nop''',INIT)

def patch(rom,tex_rom,korean_rom,glyph_count,blob=None,hook_lookup=True):
    def put(va,data):a=rom_of(va);rom[a:a+len(data)]=data
    put(INIT,bytes(INIT_END-INIT))
    put(SLOT_TABLE,struct.pack('>%dH'%SLOTS,*SLOT_INDICES))
    init=init_code(tex_rom,blob);assert INIT+len(init)<=HOOK;put(INIT,init)
    hook=asm(f'''
        andi $a0,$a0,65535
        srl $t0,$a0,8
        addiu $t0,$t0,-129
        sltiu $t1,$t0,32
        beqz $t1,original
        nop
        addiu $t1,$t0,-13
        sltiu $t1,$t1,2             # lead 0x8E/0x8F: EUC-JP SS2/SS3, not Hangul (name_input.idx2code)
        bnez $t1,original
        sltiu $t1,$t0,15
        bnez $t1,lead_low
        nop
        addiu $t0,$t0,-2
    lead_low:
        andi $t1,$a0,255
        addiu $t1,$t1,-161
        sltiu $t2,$t1,94
        beqz $t2,original
        nop
        li $t2,94
        multu $t0,$t2
        mflo $t0
        addu $t0,$t0,$t1
        sltiu $t2,$t0,{glyph_count}
        beqz $t2,original
        nop
        li $t1,{KEYS}
        move $t2,$zero
    search:
        lhu $t3,0($t1)
        beq $t3,$a0,hit
        nop
        addiu $t2,$t2,1
        sltiu $t3,$t2,{SLOTS}
        bnez $t3,search
        addiu $t1,$t1,2
        li $t1,{CURSOR}
        lw $t2,0($t1)
        addiu $t3,$t2,1
        sltiu $t4,$t3,{SLOTS}
        bnez $t4,store_cursor
        nop
        move $t3,$zero
    store_cursor:
        sw $t3,0($t1)
        li $t3,{KEYS}
        sll $t4,$t2,1
        addu $t3,$t3,$t4
        sh $a0,0($t3)
        li $t3,{SLOT_TABLE}
        sll $t4,$t2,1
        addu $t3,$t3,$t4
        lhu $t2,0($t3)
        sll $t3,$t2,6
        sll $t4,$t2,5
        addu $t3,$t3,$t4
        li $t4,{TEXTURES}
        addu $t3,$t3,$t4
        sll $t1,$t0,6
        sll $t2,$t0,5
        addu $t0,$t1,$t2
        li $t1,{0xb0000000+korean_rom}
        addu $t1,$t1,$t0
        move $v0,$t3
        addiu $t4,$t3,96
    invalidate:
        cache 17,0($t3)
        addiu $t3,$t3,16
        bne $t3,$t4,invalidate
        nop
        li $t4,0x20000000
        or $t3,$v0,$t4
        addiu $t4,$t3,96
    copy:
        lw $t5,0($t1)
        sw $t5,0($t3)
        addiu $t1,$t1,4
        addiu $t3,$t3,4
        bne $t3,$t4,copy
        nop
        li $t0,12
        sw $t0,0($a1)
        jr $ra
        nop
    hit:
        li $t3,{SLOT_TABLE}
        sll $t4,$t2,1
        addu $t3,$t3,$t4
        lhu $t2,0($t3)
        sll $t3,$t2,6
        sll $t4,$t2,5
        addu $t3,$t3,$t4
        li $v0,{TEXTURES}
        addu $v0,$v0,$t3
        li $t0,12
        sw $t0,0($a1)
        jr $ra
        nop
    original:
        j {FALLBACK}
        nop''',HOOK)
    assert HOOK+len(hook)<=FALLBACK;put(HOOK,hook)
    put(FALLBACK,asm(f'addiu $sp,$sp,-32\nsw $a1,36($sp)\nj {LOOKUP+8}\nnop',FALLBACK))
    if hook_lookup:put(LOOKUP,asm(f'j {HOOK}\nnop',LOOKUP))
    return {'cache_slots':SLOTS,'keys':hex(KEYS),'slot_table':hex(SLOT_TABLE),'hook_bytes':len(hook),'init_bytes':len(init)}

if __name__=='__main__':
    rom=(ROOT/'Custom Robo V2 (Japan).z64').read_bytes()
    original_expanded(rom)
    print('original initializer and offline expansion match for all',GLYPHS,'glyphs + fallback')
