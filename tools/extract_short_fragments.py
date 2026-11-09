"""4단계 보충: extract_raw_text.py 가 걸러 낸 짧은 표시 조각을 raw-text-all.json 에 더한다.

원래 조건(가나가 있거나 일본 글자 2자 이상)에 걸려 빠진 것: 「Z ２回」「N、」「N。」「M右」「１個」「%d点」 등.
고르는 기준: 표시 문자열(class=display)에서 0x80 바이트 안에 있고,
  일본 글자·일본 문장부호(、。？！（）・)·전각 숫자+단위(回発個点)가 든 것.
뺄 것: 맵 번호(ＧＤ１＿２ 등), 깨진 바이트(? 섞임), 디버그 문구.
더한 항목은 class=display, rule=short_fragment. 이미 있는 오프셋은 건너뛴다(여러 번 돌려도 같음).
"""
import bisect, json, re
from survey_rom import ROOT
from segments import segments

NEAR = 0x80
SHOW = re.compile(r'[ぁ-ゟァ-ヺ一-鿿、。？！（）・]|[０-９]|%\d*d')
MAPID = re.compile(r'^[Ａ-Ｚ]{2}[０-９]+＿[０-９]+$')


def main():
    rom = (ROOT / 'Custom Robo V2 (Japan).z64').read_bytes()
    p = ROOT / 'work/translation/raw-text-all.json'
    rows = json.loads(p.read_text(encoding='utf-8'))
    have = {r['rom_offset'] for r in rows}
    disp = sorted(r['rom_offset'] for r in rows if r.get('class') == 'display')
    areas = [(f"seg{s['id']}", s['data_rom'], s['rom_end']) for s in segments(rom)]
    areas += [('robo_moves', 0x3fae70, 0x41f7d0), ('battle_setup', 0x980340, 0x9b5980),
              ('demo_setup', 0x9b5980, 0x9b6600)]
    pat = re.compile(rb'(?:[\xa1-\xfe][\xa1-\xfe]|[\x20-\x7e\n]){1,}\x00')
    add = []
    for name, a, b in areas:
        for m in pat.finditer(rom, a, b):
            o = m.start()
            if o in have or (o > a and rom[o - 1] != 0):
                continue
            t = m.group()[:-1]
            if not re.search(rb'[\xa1-\xfe]', t):
                continue
            try:
                u = t.decode('euc_jp')
            except UnicodeDecodeError:
                continue
            if any(ord(c) < 32 and c != '\n' for c in u) or '?' in u or '★' in u or 'So_' in u:
                continue
            i = bisect.bisect_left(disp, o)
            near = min([abs(disp[j] - o) for j in (i - 1, i) if 0 <= j < len(disp)] or [1 << 30])
            if near >= NEAR or not SHOW.search(u) or MAPID.match(u.strip()):
                continue
            add.append({'id': f'R{o:08X}', 'area': name, 'rom_offset': o, 'bytes': len(t),
                        'source': u, 'shared_areas': [], 'rule': 'short_fragment', 'class': 'display'})
    rows += add
    rows.sort(key=lambda r: r['rom_offset'])
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
    uniq = sorted({r['source'] for r in add})
    print('더함', len(add), '고유', len(uniq))
    print(uniq)


if __name__ == '__main__':
    main()
