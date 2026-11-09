"""4단계 전수 조사: 미해독 묶음(이펙트·0x41F7D0·0x1529B0·맵)과 세그먼트 데이터 영역의 그림 조사.

결과: work/survey/models/ (그림 png, 접촉 시트, report.json)
- 이펙트 0x92CF40~0x980340: 머리 [이름4][하위 개수 N][오프셋 N개]; 하위 모델 +0 크기, +0x14 (?, 형식, log2 폭, log2 높이),
  +0x24 텍스처 시작(하위 모델 기준). 텍스처 = 하위 모델 끝까지(팔레트+인덱스 또는 직접색).
- 0x41F7D0: [크기][팔레트 512][CI8] 반복, 그 뒤 하위 메시 오프셋 표.
- 0x1529B0: 재질은 이름 + (xx FF log2w log2h) = 외부 텍스처(이름 참조), 그림 내장 없음.
- 맵 0x55FFC0: 물체 이름 = 텍스처 이름, 세그먼트 4 표(0x8015AD44, 290개)로 0x62EAA0 묶음 번호를 찾는다.
"""
import json, struct, math, re, collections, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from survey_rom import ROOT
from segments import segments

rom = (ROOT / 'Custom Robo V2 (Japan).z64').read_bytes()
streams = json.loads((ROOT / 'manifests/compressed-streams.json').read_text())
OUT = ROOT / 'work/survey/models'; OUT.mkdir(parents=True, exist_ok=True)
report = {}

def sread(r): return (ROOT / r['file'].replace('\\', '/')).read_bytes()
def in_range(a, b): return [r for r in streams if a <= r['offset'] < b]

def rgba16(raw, alpha=True):
    v = np.frombuffer(raw, dtype='>u2').astype(np.uint16); out = np.empty((len(v), 4), np.uint8)
    for i, s in enumerate((11, 6, 1)): n = (v >> s) & 31; out[:, i] = (n << 3) | (n >> 2)
    out[:, 3] = (v & 1) * 255 if alpha else 255; return out

def ci4(raw, pal, w, h):
    b = np.frombuffer(raw[:w * h // 2], np.uint8); idx = np.empty(len(b) * 2, np.uint8)
    idx[0::2] = b >> 4; idx[1::2] = b & 15; return Image.fromarray(pal[idx].reshape(h, w, 4), 'RGBA')

def ci8(raw, pal, w, h):
    idx = np.frombuffer(raw[:w * h], np.uint8); return Image.fromarray(pal[idx].reshape(h, w, 4), 'RGBA')

def rgba32(raw, w, h):
    return Image.fromarray(np.frombuffer(raw[:w * h * 4], np.uint8).reshape(h, w, 4).copy(), 'RGBA')

def sheet(tiles, name, cols=8, cw=210, ch=170):
    """tiles: (label, image). 원본 + 상하 뒤집은 것을 나란히."""
    paths = []
    for k in range(0, len(tiles), 48):
        batch = tiles[k:k + 48]
        sh = Image.new('RGB', (cols * cw, math.ceil(len(batch) / cols) * ch), (70, 80, 90)); dr = ImageDraw.Draw(sh)
        for i, (lab, im) in enumerate(batch):
            sc = max(1, min(3, 96 // max(im.width, im.height)))
            t = im.resize((im.width * sc, im.height * sc), Image.NEAREST)
            pair = Image.new('RGBA', (t.width * 2 + 4, t.height), (40, 40, 40, 255))
            pair.alpha_composite(t, (0, 0)); pair.alpha_composite(t.transpose(Image.FLIP_TOP_BOTTOM), (t.width + 4, 0))
            bg = Image.new('RGBA', pair.size, (40, 40, 40, 255)); bg.alpha_composite(pair)
            bg.thumbnail((cw - 6, ch - 20)); x = i % cols * cw; y = i // cols * ch
            sh.paste(bg.convert('RGB'), (x + 3, y + 3)); dr.text((x + 3, y + ch - 16), lab, fill='white')
        p = OUT / f'sheet_{name}_{k // 48:02d}.png'; sh.save(p); paths.append(str(p.relative_to(ROOT)))
    return paths

# ---------- 1. 이펙트 ----------
def effects():
    d_out = OUT / 'effects'; d_out.mkdir(exist_ok=True)
    tiles = []; fmts = collections.Counter(); bad = []
    for r in in_range(0x92CF40, 0x980340):
        d = sread(r); n = struct.unpack_from('>I', d, 4)[0]
        for i, o in enumerate(struct.unpack_from('>%dI' % n, d, 8)):
            size = struct.unpack_from('>I', d, o)[0]; fl = d[o + 0x14:o + 0x18]
            w, h = 1 << fl[2], 1 << fl[3]; t = struct.unpack_from('>I', d, o + 0x24)[0]
            reg = d[o + t:o + size]; P = w * h; code = fl[1]; ims = []
            if code in (8, 9, 0xb) and len(reg) == 32 + P // 2:
                ims = [('CI4', ci4(reg[32:], rgba16(reg[:32]), w, h))]
            elif code in (0, 1) and len(reg) == 512 + P:
                ims = [('CI8', ci8(reg[512:], rgba16(reg[:512]), w, h))]
            elif code in (4, 5) and len(reg) == 4 * P:
                ims = [('RGBA32', rgba32(reg, w, h))]
            elif code in (4, 5) and len(reg) % 4 == 0:
                px = len(reg) // 4   # 크기 칸과 맞지 않는 RGBA32: 폭 후보 여러 개
                for ww in (w, 32, 64):
                    if px % ww == 0: ims.append((f'RGBA32-w{ww}', rgba32(reg, ww, px // ww)))
            if not ims: bad.append([hex(r['offset']), hex(o), code, len(reg)]); continue
            for f, im in ims:
                lab = f"{r['offset']:08X}_{i}_{f}"; im.save(d_out / f'{lab}.png'); tiles.append((lab, im)); fmts[f.split('-')[0]] += 1
    report['effects'] = {'streams': len(in_range(0x92CF40, 0x980340)), 'images': len(tiles), 'formats': dict(fmts), 'unparsed': bad,
                         'sheets': sheet(tiles, 'effects')}

# ---------- 2. 0x41F7D0 ----------
def bank41():
    d_out = OUT / '41f7d0'; d_out.mkdir(exist_ok=True); tiles = []; info = []
    for r in in_range(0x41F7D0, 0x435FC0):
        d = sread(r)
        # 오프셋 표: 0x1000 뒤에서 처음 나오는 (0000 xxxx) 증가 낱말 8개 이상, 마지막 값이 파일 길이 근처
        tbl = None
        for p in range(0x1000, len(d) - 32, 4):
            ws = struct.unpack_from('>8I', d, p)
            if all(ws[k] < ws[k + 1] < len(d) for k in range(7)) and ws[0] == p + 4 * (len([1 for _ in range(0)]) ) or False:
                pass
            if all(0 < ws[k] < ws[k + 1] < len(d) for k in range(7)) and p < ws[0] <= p + 0x80:
                tbl = p; break
        # 여섯 스트림 모두 같은 배치(팔레트 0x4·0x604·0xE04, 메시 표 0x1904)임을 확인하고 고정 배치로 자른다.
        assert tbl == 0x1904, hex(tbl or 0)
        secs = [(0x4, 0x204, 0x604), (0x604, 0x804, 0xE04), (0xE04, 0x1004, 0x1904)]
        for j, (pp, a, b) in enumerate(secs):
            n = b - a
            for ww in (16, 24, 32, 48, 64):
                if n % ww == 0 and 16 <= n // ww <= 96:
                    im = ci8(d[a:b], rgba16(d[pp:pp + 512], alpha=False), ww, n // ww)
                    lab = f"{r['offset']:08X}_{j}_w{ww}"; im.save(d_out / f'{lab}.png'); tiles.append((lab, im))
        info.append({'stream': hex(r['offset']), 'mesh_table': hex(tbl) if tbl else None,
                     'textures': [{'palette': hex(pp), 'data': hex(a), 'bytes': b - a} for pp, a, b in secs]})
    report['41f7d0'] = {'streams': info, 'renders': len(tiles), 'sheets': sheet(tiles, '41f7d0', cols=6)}

# ---------- 3. 0x1529B0 ----------
def bank1529():
    names = collections.Counter(); emb = []; nstream = 0
    for r in in_range(0x1529B0, 0x1A6230):
        d = sread(r); nstream += 1
        for m in re.finditer(rb'[\x00-\x03][\x00-\xff][\x03-\x07][\x03-\x07]\x00\x00', d):
            o = m.start()
            if o % 4: continue
            pre = re.findall(rb'[A-Za-z0-9_]{3,}', d[max(0, o - 24):o])
            if d[o + 1] == 0xff: names[(pre[-1] if pre else b'?').decode()] += 1
            elif d[o + 1] in (0, 1, 4, 5, 8, 9, 0xb) and pre: emb.append([hex(r['offset']), hex(o), d[o:o + 4].hex()])
    report['1529b0'] = {'streams': nstream, 'external_material_refs': sum(names.values()), 'embedded_candidates': emb}

# ---------- 4. 맵 ----------
def maps():
    def r4(va): return 0x6d480 + va - 0x8013c5a0
    n = struct.unpack_from('>I', rom, r4(0x8015A8B8))[0]
    ptrs = struct.unpack_from('>%dI' % n, rom, r4(0x8015AD44))
    tex = []
    for va in ptrs:
        p = r4(va); tex.append(rom[p:rom.index(b'\0', p)].decode())
    texset = set(tex); recs = 0; miss = []; used = set(); odd = []
    for r in in_range(0x55FFC0, 0x62EAA0):
        d = sread(r); cnt = struct.unpack_from('>H', d, 0xA)[0]
        for k in range(cnt):
            o = struct.unpack_from('>I', d, 0xC + 4 * k)[0]
            nm = d[o + 4:d.index(b'\0', o + 4)].decode('ascii', 'replace'); recs += 1
            (used.add(nm) if nm in texset else miss.append([hex(r['offset']), hex(o), nm]))
        # 팔레트 같은 512바이트(홀수 낱말 90% 이상) 덩어리가 있는지
        for q in range(0, len(d) - 512, 0x20):
            ws = struct.unpack_from('>256H', d, q)
            if sum(x & 1 for x in ws) > 230 and len(set(ws)) > 32: odd.append([hex(r['offset']), hex(q)]); break
    report['maps'] = {'streams': len(in_range(0x55FFC0, 0x62EAA0)), 'records': recs, 'texture_names_in_table': n,
                      'distinct_names_used': len(used), 'names_not_in_table': miss[:50], 'names_not_in_table_count': len(miss),
                      'palette_like_blocks': odd}

# ---------- 5. 세그먼트 데이터 영역 ----------
def segdata():
    d_out = OUT / 'segments'; d_out.mkdir(exist_ok=True); sheets = []
    for s in segments(rom):
        a, b = s['data_rom'], s['rom_end']; raw = rom[a:b]
        if len(raw) < 64: continue
        # 보기 3가지: RGBA16 폭 32, I4 폭 64(4bpp 밝기), I8 폭 32. 세로로 잘라 512줄 단위 기둥으로 늘어놓는다.
        views = []
        n = len(raw) // 64 * 64
        v16 = rgba16(raw[:n], alpha=False)[:, :3].reshape(-1, 32, 3)
        b4 = np.frombuffer(raw[:n], np.uint8); i4 = np.empty(len(b4) * 2, np.uint8); i4[0::2] = (b4 >> 4) * 17; i4[1::2] = (b4 & 15) * 17
        i4 = np.stack([i4] * 3, 1).reshape(-1, 64, 3)
        i8 = np.stack([b4] * 3, 1).reshape(-1, 32, 3)
        for tag, arr in (('rgba16w32', v16), ('i4w64', i4), ('i8w32', i8)):
            rows = arr.shape[0]; colh = 512; ncol = math.ceil(rows / colh); w = arr.shape[1]
            for part in range(0, ncol, 16):
                cols = range(part, min(ncol, part + 16))
                img = Image.new('RGB', (len(cols) * (w + 6), colh), (255, 0, 255))
                for ci, c in enumerate(cols):
                    seg = arr[c * colh:(c + 1) * colh]
                    img.paste(Image.fromarray(np.ascontiguousarray(seg)), (ci * (w + 6), 0))
                p = d_out / f"seg{s['id']:02d}_{tag}_{part // 16:02d}.png"; img.save(p); sheets.append(str(p.relative_to(ROOT)))
    report['segments'] = {'sheets': sheets, 'note': '열 하나 = 512줄, RGBA16 열 하나 = 32KB, I4 64폭 열 = 16KB, I8 열 = 16KB, 열 순서대로 data_rom부터'}

# ---------- 6. 세그먼트 0 데이터의 무압축 RGBA16 아이콘(포인터 표 ROM 0x48984, 53개, 각 그림 뒤 8바이트) ----------
def seg0icons():
    d_out = OUT / 'seg0_icons'; d_out.mkdir(exist_ok=True)
    base = 0x80063880 - 0x3ec80
    ptrs = [struct.unpack_from('>I', rom, 0x48984 + 4 * i)[0] - base for i in range(53)] + [0x48860]
    tiles = []
    for a, b in zip(ptrs, ptrs[1:]):
        px = (b - a - 8) // 2
        for w in (8, 12, 16, 20, 24, 32, 48, 64):   # 폭 정보가 없어 후보를 모두 렌더(맞는 폭만 그림이 된다)
            if px % w == 0 and 4 <= px // w <= 96 and px // w <= w * 3:
                v = rgba16(rom[a:a + px * 2], alpha=False)
                im = Image.fromarray(v.reshape(-1, w, 4), 'RGBA'); lab = f'{a:06X}_w{w}'
                im.save(d_out / f'{lab}.png'); tiles.append((lab, im))
    # 표 밖 앞부분(0x3EC80~0x43CD8: 하늘·풀·벽돌·8폭 영문 글꼴 등)은 폭 32·8 띠로 저장
    for w, a, b in ((32, 0x3EC80, 0x42C80), (8, 0x42C80, 0x43C80), (32, 0x43C80, 0x43CD8)):
        n = (b - a) // (2 * w); Image.fromarray(rgba16(rom[a:a + n * w * 2], alpha=False).reshape(n, w, 4), 'RGBA').save(d_out / f'strip_{a:06X}_w{w}.png')
    # 세그먼트 6 연기 RGBA32(0xC6670~0xCA570)
    a = 0xC6670; n = (0xCA570 - a) // 128
    Image.fromarray(np.frombuffer(rom[a:a + n * 128], np.uint8).reshape(n, 32, 4).copy(), 'RGBA').save(d_out / 'seg06_smoke_C6670_rgba32_w32.png')
    report['seg0_icons'] = {'table': '0x48984', 'entries': 53, 'renders': len(tiles), 'sheets': sheet(tiles, 'seg0icons', cols=10)}

if __name__ == '__main__':
    for f in sys.argv[1:] or ['effects', 'bank41', 'bank1529', 'maps', 'segdata', 'seg0icons']:
        globals()[f]()
    prev = OUT / 'report.json'
    old = json.loads(prev.read_text(encoding='utf-8')) if prev.exists() else {}
    old.update(report); prev.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in report.items(): print(k, {x: (y if not isinstance(y, list) or len(y) < 6 else len(y)) for x, y in v.items()})
