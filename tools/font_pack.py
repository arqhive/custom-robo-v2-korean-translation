"""글꼴 1비트 방식(ROM 절약, 2026-10-30). font_cache 의 「미리 펼친 텍스처를 ROM 에서 DMA」 대신 쓴다.

미리 펼친 글꼴(원래 1,673칸 160KB + 한글 2,401칸 230KB)을 ROM 에 넣지 않는다.
펼치기 루틴(expand)과 부팅 루틴(boot)을 RAM 묶음 맨 앞에 두고,
  부팅: 원래 1비트 글꼴(스크래치 버퍼)을 TEXTURES 로 펼치고 대체 칸을 0xFF 로, 캐시 키를 비움
  훅  : 한글 글리프 1비트(20바이트 간격, 18바이트 + 0 2개)를 카트에서 읽어 캐시 칸에 펼침
펼치기 규칙은 font_cache.expand(원래 초기화와 바이트까지 같음)과 같다.
"""
import struct
import re
from font_cache import (asm as _asm, rom_of, INIT, INIT_END, HOOK, FALLBACK, LOOKUP, KEYS, CURSOR, SLOT_TABLE, SLOTS,
                        SLOT_INDICES, TEXTURES, GLYPHS, FONT_ROM, DMA)

KO_STRIDE = 20


def asm(src, base):
    """어셈블러는 ASCII 만 받으므로 # 주석(한국어)을 지우고 넘긴다."""
    return _asm(re.sub(r'#.*', '', src), base)

EXPAND = '''
    expand:                         # a0 = 18바이트 1bpp 12x12, a1 = 96바이트 I4 12x16 (t0~t7 만 씀)
        move $t0,$zero              # 앞 줄(16비트 마스크)
        move $t1,$zero              # y
    erow:
        srl $t2,$t1,1
        sll $t3,$t2,1
        addu $t3,$t3,$t2
        addu $t3,$t3,$a0            # src + 3*(y>>1)
        andi $t2,$t1,1
        bnez $t2,eodd
        nop
        lbu $t4,0($t3)
        lbu $t5,1($t3)
        sll $t4,$t4,4
        srl $t5,$t5,4
        b egot
        or $t4,$t4,$t5
    eodd:
        lbu $t4,1($t3)
        lbu $t5,2($t3)
        andi $t4,$t4,15
        sll $t4,$t4,8
        or $t4,$t4,$t5
    egot:
        sll $t4,$t4,4               # C: 열 x 는 비트 15-x
        srl $t5,$t4,1
        or $t5,$t5,$t0
        srl $t6,$t0,1
        or $t5,$t5,$t6              # S = 그림자(왼쪽, 위, 왼위)
        or $t5,$t5,$t4              # S|C
        li $t2,15
    ebyte:
        srlv $t6,$t4,$t2
        andi $t6,$t6,1
        subu $t6,$zero,$t6
        andi $t6,$t6,12
        srlv $t7,$t5,$t2
        andi $t7,$t7,1
        subu $t7,$zero,$t7
        andi $t7,$t7,3
        or $t3,$t6,$t7
        sll $t3,$t3,4               # 윗 4비트
        addiu $t2,$t2,-1
        srlv $t6,$t4,$t2
        andi $t6,$t6,1
        subu $t6,$zero,$t6
        andi $t6,$t6,12
        srlv $t7,$t5,$t2
        andi $t7,$t7,1
        subu $t7,$zero,$t7
        andi $t7,$t7,3
        or $t3,$t3,$t6
        or $t3,$t3,$t7
        sb $t3,0($a1)
        addiu $a1,$a1,1
        addiu $t2,$t2,-1
        bgez $t2,ebyte
        nop
        move $t0,$t4
        addiu $t1,$t1,1
        sltiu $t2,$t1,12
        bnez $t2,erow
        nop
        jr $ra
        nop
'''

DECOMP = '''
    decomp:                         # a0 = 압축 묶음, a1 = 쓸 곳(KSEG1), a2 = 끝(KSEG1). 거리형 LZSS(pack 참고)
        sltu $t0,$a1,$a2
        beqz $t0,ddone
        nop
        lbu $t1,0($a0)
        addiu $a0,$a0,1
        li $t2,8
    dbit:
        sltu $t0,$a1,$a2
        beqz $t0,ddone
        andi $t0,$t1,1
        beqz $t0,dmatch
        srl $t1,$t1,1
        lbu $t3,0($a0)
        addiu $a0,$a0,1
        sb $t3,0($a1)
        b dnext
        addiu $a1,$a1,1
    dmatch:
        lbu $t3,0($a0)
        lbu $t4,1($a0)
        addiu $a0,$a0,2
        andi $t5,$t4,0xf0
        sll $t5,$t5,4
        or $t3,$t3,$t5
        addiu $t3,$t3,1
        subu $t3,$a1,$t3            # 거리 1~4096 앞에서 복사
        andi $t4,$t4,15
        addiu $t4,$t4,3
    dcopy:
        lbu $t5,0($t3)
        addiu $t3,$t3,1
        sb $t5,0($a1)
        addiu $t4,$t4,-1
        bnez $t4,dcopy
        addiu $a1,$a1,1
    dnext:
        addiu $t2,$t2,-1
        bnez $t2,dbit
        nop
        b decomp
        nop
    ddone:
        jr $ra
        nop
'''


def pack(raw):
    """DECOMP 짝 압축: 플래그 바이트(1=그대로), 짝 2바이트 = (거리-1) 12비트 + (길이-3) 4비트."""
    import collections
    pos = collections.defaultdict(list); out = bytearray(); i = 0; n = len(raw)
    while i < n:
        fp = len(out); out.append(0)
        for bit in range(8):
            if i >= n:
                break
            best = (0, 0)
            if i + 3 <= n:
                lim = min(18, n - i)
                for at in reversed(pos[raw[i:i + 3]]):
                    if i - at > 4096:
                        break
                    l = 3
                    while l < lim and raw[at + l] == raw[i + l]:
                        l += 1
                    if l > best[0]:
                        best = (l, i - at)
                        if l == lim:
                            break
            if best[0] >= 3:
                l, d = best; out += bytes(((d - 1) & 255, (((d - 1) >> 4) & 0xf0) | (l - 3)))
            else:
                out[fp] |= 1 << bit; out.append(raw[i]); l = 1
            for k in range(i, i + l):
                pos[raw[k:k + 3]].append(k)
            i += l
    return bytes(out)


def unpack(comp, size):
    out = bytearray(); i = 0
    while len(out) < size:
        f = comp[i]; i += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if f >> bit & 1:
                out.append(comp[i]); i += 1
            else:
                d = (comp[i] | (comp[i + 1] & 0xf0) << 4) + 1; l = (comp[i + 1] & 15) + 3; i += 2
                for _ in range(l):
                    out.append(out[-d])
    return bytes(out)


def boot_src(blob_va, blob_size, comp_va):
    """부팅: 묶음 풀기(앞뒤 캐시 무효화) → 원래 글꼴 펼치기 + 대체 칸 + 캐시 키 비우기."""
    end = blob_va + blob_size
    return f'''
    boot:
        addiu $sp,$sp,-24
        sw $ra,20($sp)
        sw $s0,16($sp)
        sw $s1,12($sp)
        sw $s2,8($sp)
        li $t0,{blob_va & ~31}
        li $t1,{(end + 31) & ~31}
    binv:
        cache 17,0($t0)
        cache 16,0($t0)
        cache 17,16($t0)
        addiu $t0,$t0,32
        bne $t0,$t1,binv
        nop
        li $a0,{comp_va}
        li $a1,{(blob_va | 0x20000000) & 0xffffffff}
        li $a2,{(end | 0x20000000) & 0xffffffff}
        bal decomp                  # li 는 두 명령이 될 수 있어 지연 칸에 두지 않는다
        nop
''' + BOOT


BOOT = f'''
        lui $t0,0x800d
        lw $s0,0x3f58($t0)          # 스크래치(1비트 글꼴을 DMA 한 곳)
        li $t0,0x20000000
        or $s0,$s0,$t0
        li $s1,{(TEXTURES | 0x20000000) & 0xffffffff}
        li $s2,{GLYPHS}
    bloop:
        move $a0,$s0
        bal expand
        move $a1,$s1
        addiu $s0,$s0,18
        addiu $s1,$s1,96
        addiu $s2,$s2,-1
        bnez $s2,bloop
        nop
        li $t0,-1
        addiu $t1,$s1,96
    bff:
        sw $t0,0($s1)
        addiu $s1,$s1,4
        bne $s1,$t1,bff
        nop
        li $t0,{KEYS}
        li $t1,{CURSOR + 4}
    bclear:
        sw $zero,0($t0)
        addiu $t0,$t0,4
        bne $t0,$t1,bclear
        nop
        lw $s2,8($sp)
        lw $s1,12($sp)
        lw $s0,16($sp)
        lw $ra,20($sp)
        jr $ra
        addiu $sp,$sp,24
'''


def runtime_code(base, blob_va, blob_size):
    """RAM base 에 둘 expand·decomp·boot 루틴. 압축 묶음은 이 코드 바로 뒤(8바이트 정렬, 'comp')에 둔다.
    (bytes, {'expand': va, 'boot': va, 'comp': va})"""
    n = len(asm(EXPAND + DECOMP, base)); comp = base + 0x400
    for _ in range(4):                  # li 길이가 값에 따라 달라지므로 맞을 때까지
        code = asm(EXPAND + DECOMP + boot_src(blob_va, blob_size, comp), base)
        if base + ((len(code) + 7) & ~7) == comp:
            break
        comp = base + ((len(code) + 7) & ~7)
    else:
        raise AssertionError('runtime size')
    code += bytes(comp - base - len(code))
    for i in range(0, len(code), 4):       # keystone 가 bal 을 $gp 호출로 바꾸지 않았는지
        w = int.from_bytes(code[i:i + 4], 'big')
        assert not ((w >> 21) & 31 == 28 and w >> 26 in (0x23, 0x09)), hex(base + i)
    return code, {'expand': base, 'boot': base + n, 'comp': comp}


def init_code(blob, boot):
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
        li $a2,{GLYPHS * 18}
        li $a0,{blob[0]}
        li $a1,{blob[1]}
        li $a2,{blob[2]}
        jal {DMA}
        nop
        jal {boot}
        nop
        lw $ra,28($sp)
        addiu $sp,$sp,32
        jr $ra
        nop''', INIT)


def korean_rom_bytes(bitmaps):
    """1비트 18바이트 글리프 → 20바이트 간격(카트는 4바이트 단위로 읽음)."""
    return b''.join(b + b'\0\0' for b in bitmaps)


def hook_code(korean_rom, glyph_count, expand_va):
    return asm(f'''
        andi $a0,$a0,65535
        srl $t0,$a0,8
        addiu $t0,$t0,-129
        sltiu $t1,$t0,32
        beqz $t1,original
        nop
        addiu $t1,$t0,-13
        sltiu $t1,$t1,2
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
        sll $t1,$t0,4
        sll $t2,$t0,2
        addu $t0,$t1,$t2
        li $t1,{0xb0000000 + korean_rom}
        addu $t1,$t1,$t0
        move $v0,$t3
        addiu $t4,$t3,96
    invalidate:
        cache 17,0($t3)
        addiu $t3,$t3,16
        bne $t3,$t4,invalidate
        nop
        addiu $sp,$sp,-24
        lw $t5,0($t1)
        sw $t5,0($sp)
        lw $t5,4($t1)
        sw $t5,4($sp)
        lw $t5,8($t1)
        sw $t5,8($sp)
        lw $t5,12($t1)
        sw $t5,12($sp)
        lw $t5,16($t1)
        sw $t5,16($sp)
        move $t8,$ra
        move $t9,$a1
        move $a0,$sp
        li $t4,0x20000000
        jal {expand_va}
        or $a1,$v0,$t4
        addiu $sp,$sp,24
        move $ra,$t8
        move $a1,$t9
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
        nop''', HOOK)


def patch(rom, korean_rom, glyph_count, blob, rt):
    """blob=(rom, ram, size), rt=runtime_code 의 주소."""
    def put(va, data):
        a = rom_of(va); rom[a:a + len(data)] = data
    put(INIT, bytes(INIT_END - INIT))
    put(SLOT_TABLE, struct.pack('>%dH' % SLOTS, *SLOT_INDICES))
    init = init_code(blob, rt['boot']); assert INIT + len(init) <= HOOK, len(init); put(INIT, init)
    hook = hook_code(korean_rom, glyph_count, rt['expand'])
    assert HOOK + len(hook) <= FALLBACK, len(hook); put(HOOK, hook)
    put(FALLBACK, asm(f'addiu $sp,$sp,-32\nsw $a1,36($sp)\nj {LOOKUP + 8}\nnop', FALLBACK))
    put(LOOKUP, asm(f'j {HOOK}\nnop', LOOKUP))
    return {'mode': 'packed-1bpp', 'cache_slots': SLOTS, 'hook_bytes': len(hook), 'init_bytes': len(init),
            'expand': hex(rt['expand']), 'boot': hex(rt['boot'])}
