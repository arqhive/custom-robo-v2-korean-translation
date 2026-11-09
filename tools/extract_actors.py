"""인물 스프라이트(ROM 0x673CA0~) 전 프레임 추출.

인물 표: 세그먼트 4 RAM 0x8015B578, 레코드 0x510바이트, 개수 0x8015B570.
  +0 이름 포인터, +4 ?, +8 인물 데이터 시작(0x673CA0 기준),
  +0xC 프레임 오프셋 halfword[16 행][24 칸](행=0x8014BBxx 의 arg 0x40, 칸=arg 0x3c),
  +0x310 팔레트 256색 RGBA5551.
프레임 해제: 0x8014BD04 를 옮김(아래 decode_frame). 0x400바이트 버퍼를 뒤에서부터 채우고
끝나면 32x32 를 돌려 쓴다(a2=0 경우).
"""
import sys, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from segments import segments, ram_to_rom, ROOT
from PIL import Image, ImageDraw

BASE = 0x673CA0
DELTA_VA = 0x8017F128

def decode_frame(b, p, delta):
    """0x8014BD04: 출력은 buf[0x3ff]부터 아래로. 반환 (32x32 CI8 bytes, 소비 바이트)."""
    buf = bytearray(0x400); w = 0x3ff; a3 = 0; start = p
    def put(v):
        nonlocal w
        if w >= 0: buf[w] = v & 0xff
        w -= 1
    while True:
        s2 = b[p]; p += 1
        if s2 == 0xff: break
        cont = (s2 == 0xfe)
        for _ in range(s2 - cont): put(0)          # 0 연속
        if cont: continue
        while True:                                # 명령 묶음
            s2 = b[p]; p += 1
            more = s2 & 0x80; n = s2 & 0x1f; mode = s2 & 0x60
            if mode == 0x00:                       # 같은 값 반복
                v = b[p]; p += 1
                for _ in range(n): put(v)
            elif mode == 0x20:                     # 그대로 복사
                for _ in range(n): put(b[p]); p += 1
            else:
                if mode == 0x60:                   # 기준값 새로 받고 델타
                    a3 = b[p]; p += 1; put(a3)
                nib = 0xff                         # 델타(4비트, 표 0..7,-8..-1)
                for _ in range(n):
                    if nib == 0xff:
                        nib = (b[p] + 0xff00) & 0xffff; p += 1
                    a3 = (delta[nib & 0xf] + a3) & 0xff; nib >>= 4
                    put(a3)
            if not more: break
        if w < -1: raise ValueError('overflow')
    # 회전(a2=0): out[(31-c)*32 + r] = buf[r*32 + c]
    out = bytearray(0x400); k = 0
    for c in range(31, -1, -1):
        for r in range(32):
            out[k] = buf[r * 32 + c]; k += 1
    return bytes(out), p - start, w

def pal_rgba(raw):
    cols = []
    for i in range(256):
        v = struct.unpack_from('>H', raw, i * 2)[0]
        r = (v >> 11) & 31; g = (v >> 6) & 31; bb = (v >> 1) & 31; a = v & 1
        cols.append((r * 255 // 31, g * 255 // 31, bb * 255 // 31, 255 if a else 0))
    return cols

def main():
    rom = (ROOT / 'Custom Robo V2 (Japan).z64').read_bytes()
    seg = segments(rom)[4]
    delta = [x - (1 << 32) if x & 0x80000000 else x for x in struct.unpack_from('>16I', rom, ram_to_rom(seg, DELTA_VA))]
    tab = ram_to_rom(seg, 0x8015B578)
    count = struct.unpack_from('>I', rom, ram_to_rom(seg, 0x8015B570))[0]
    outdir = ROOT / 'work/survey/actors'; (outdir / 'frames').mkdir(parents=True, exist_ok=True)
    rows = []; total = 0; errors = []
    for i in range(count):
        rec = rom[tab + i * 0x510: tab + (i + 1) * 0x510]
        nameptr, f4, start = struct.unpack_from('>3I', rec, 0)
        np_ = ram_to_rom(seg, nameptr); name = rom[np_:rom.index(b'\0', np_)].decode('euc_jp', 'replace')
        offs = struct.unpack_from('>384H', rec, 0xC)
        uniq = sorted(set(offs))
        pal = pal_rgba(rec[0x310:0x510])
        imgs = []
        for o in uniq:
            src = BASE + start + o
            try:
                px, used, w = decode_frame(rom, src, delta)
            except Exception as e:
                errors.append((i, o, repr(e))); continue
            im = Image.new('RGBA', (32, 32)); im.putdata([pal[v] for v in px])
            im.save(outdir / 'frames' / f'{i:02d}_{o:04X}.png')
            imgs.append((o, im, used, w))
        total += len(imgs)
        # 접촉 시트: 4배 확대, 회색 바탕, 칸 아래 오프셋
        cols = 12; sc = 4; cw = 32 * sc + 6; ch = 32 * sc + 18
        nrow = max(1, (len(imgs) + cols - 1) // cols)
        sheet = Image.new('RGB', (cols * cw, nrow * ch + 20), (96, 96, 96))
        d = ImageDraw.Draw(sheet); d.text((4, 4), f'{i:02d} start=0x{start:X} frames={len(imgs)}', fill=(255, 255, 255))
        for k, (o, im, used, w) in enumerate(imgs):
            x = (k % cols) * cw + 3; y = (k // cols) * ch + 22
            big = im.resize((32 * sc, 32 * sc), Image.NEAREST)
            sheet.paste(big, (x, y), big)
            d.text((x, y + 32 * sc + 2), f'{o:04X}', fill=(255, 255, 0))
        sheet.save(outdir / f'sheet_{i:02d}.png')
        rows.append({'index': i, 'name': name, 'word4': f4, 'start': start, 'rom': hex(BASE + start),
                     'frames': len(imgs), 'offsets': [f'{o:04X}' for o, *_ in imgs],
                     'consumed': [u for _, _, u, _ in imgs], 'unfilled': [w + 1 for *_, w in imgs]})
    (outdir / 'actors.json').write_text(json.dumps({'count': count, 'frames_total': total, 'errors': errors, 'actors': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('actors', count, 'frames', total, 'errors', len(errors))

if __name__ == '__main__':
    main()
