"""6단계: 번역할 그림 23장 목록과 원본 미리보기 시트.

출력: manifests/graphics-targets.json (id, 묶음, 롬 스트림, 형식, 크기, 뒤집힘, 원문, 번역안)
      work/graphics/preview-all.png (원본 확대 + 원문·번역안)
그림은 화면에 보이는 방향으로 그린다(텍스처는 위아래 뒤집혀 저장돼 있어 바로 세운다).
"""
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from survey_rom import ROOT

STREAMS = {r['offset']: r for r in json.loads((ROOT / 'manifests/compressed-streams.json').read_text())}
SURVEY = ROOT / 'work/survey/images'

# (id, 묶음, 롬 스트림, 형식, 폭, 높이, 뒤집힘, 원문, 번역안)
TARGETS = [
    ('U01', 'ui', 0x8F155C, 'CI8', 320, 240, False, 'カスタムロボ V2 (타이틀 화면 로고)', '커스텀 로보 V2'),
    ('U02', 'ui', 0x8F88E8, 'CI8', 48, 384, False, 'カ・ス・タ・ム・ロ・ボ (로고 글자 조각, 세로 8칸)', '커·스·텀·로·보'),
    ('U03', 'ui', 0x922208, 'CI8', 320, 240, False, 'カスタムロボ V2 (작은 로고, 화면 1)', '커스텀 로보 V2'),
    ('U04', 'ui', 0x927178, 'CI8', 320, 240, False, 'カスタムロボ V2 (작은 로고, 화면 2)', '커스텀 로보 V2'),
    ('U05', 'ui', 0x8FA89C, 'CI8', 128, 32, False, 'シナリオ', '시나리오'),
    ('U06', 'ui', 0x8FAD3C, 'CI8', 128, 32, False, 'VSバトル', 'VS 배틀'),
    ('U07', 'ui', 0x8FB2AC, 'CI8', 128, 32, False, '2on2バトル', '2on2 배틀'),
    ('U08', 'ui', 0x8FB850, 'CI8', 128, 32, False, 'フリーバトル', '프리 배틀'),
    ('U09', 'ui', 0x8FBD38, 'CI8', 128, 32, False, 'オプション', '옵션'),
    ('U10', 'ui', 0x8FC258, 'CI8', 128, 48, False, '旅立ち編 (후리가나 たびだちへん)', '여행 편'),
    ('U11', 'ui', 0x8FCC24, 'CI8', 128, 48, False, '激闘編 (후리가나 げきとうへん)', '격투 편'),
    ('U12', 'ui', 0x8FD528, 'CI8', 128, 48, False, '激闘編 (어두운 판, 잠김)', '격투 편'),
    ('U13', 'ui', 0x8FFA20, 'CI8', 192, 32, False, 'せつめい', '설명'),
    ('U14', 'ui', 0x900684, 'CI8', 128, 32, False, 'むげんバトル', '무한 배틀'),
    ('U15', 'ui', 0x900CDC, 'RGBA32', 160, 48, False, '赤の勝ち', '빨강의 승리'),
    ('U16', 'ui', 0x901C00, 'RGBA32', 160, 48, False, '青の勝ち', '파랑의 승리'),
    ('U17', 'ui', 0x911488, 'CI8', 160, 32, False, 'カスタマイズ完了', '커스터마이즈 완료'),
    ('U18', 'ui', 0x91190C, 'CI8', 48, 32, False, '完了', '완료'),
    ('U20', 'ui', 0x8F96E4, 'CI8', 64, 160, False, 'ロボ (오프닝 로고 큐브, 위아래 두 벌)', '로보'),
    ('U21', 'ui', 0x9000A8, 'CI8', 128, 32, False, 'ポイントマッチ (앞 숫자 칸은 비어 있고 3·5·10 은 따로 얹힘)', '포인트 매치'),
    ('U19', 'ui', 0x913F1C, 'CI8', 224, 160, False,
     '조작 안내: チェンジ(2on2専用)·ジャンプ·アタック·ガン·ボム·ポーズ·移動·ポッド',
     '체인지(2on2 전용)·점프·어택·건·봄·포즈·이동·포드'),
    ('T01', 'world', 0x656080, 'RGBA16H', 64, 32, True, '関係者以外 立入禁止', '관계자 외 출입 금지'),
    ('T02', 'world', 0x65B81C, 'RGBA16H', 128, 16, True, 'マリンパーク フェスティバル', '마린 파크 페스티벌'),
    ('T03', 'world', 0x6568B4, 'RGBA16H', 16, 32, True, '使用禁止 (세로쓰기)', '사용 금지 (세로쓰기)'),
    ('B01', 'battle', 0x1C4AA0, 'CI4', 64, 64, True, '나무 간판(손글씨, 판독 안 됨)', '(사용자 확인)'),
]


def rgba16(raw):
    v = np.frombuffer(raw, dtype='>u2').astype(np.uint16)
    out = np.empty((len(v), 4), np.uint8)
    for i, s in enumerate((11, 6, 1)):
        n = (v >> s) & 31
        out[:, i] = (n << 3) | (n >> 2)
    out[:, 3] = (v & 1) * 255
    return out


def load(t):
    tid, bank, off, fmt, w, h, flip = t[:7]
    if bank == 'ui':
        d = (ROOT / STREAMS[off]['file']).read_bytes()
        if fmt == 'CI8':
            pal = rgba16(d[:512])
            a = pal[np.frombuffer(d[512:512 + w * h], np.uint8)].reshape(h, w, 4)
        else:
            a = np.frombuffer(d[:w * h * 4], np.uint8).reshape(h, w, 4)
        im = Image.fromarray(a, 'RGBA')
    else:
        folder = '62eaa0' if bank == 'world' else '1a6230'
        im = Image.open(SURVEY / folder / f'{off:08X}.png').convert('RGBA')
    if flip:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    assert im.size == (w, h), (tid, im.size)
    return im


def main():
    font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
    jfont = ImageFont.truetype('C:/Windows/Fonts/YuGothM.ttc', 15)  # 원문 줄: 맑은 고딕에 없는 일본 한자가 있다
    out = ROOT / 'work/graphics'
    out.mkdir(parents=True, exist_ok=True)
    rows, man = [], []
    for t in TARGETS:
        im = load(t)
        s = 1 if t[4] >= 300 else (2 if t[4] >= 128 or t[5] >= 128 else 4)
        if t[0] == 'U02':
            s = 1
        rows.append((t, im.resize((im.width * s, im.height * s), Image.NEAREST)))
        man.append({'id': t[0], 'bank': t[1], 'rom_stream': t[2], 'format': t[3], 'width': t[4], 'height': t[5],
                    'stored_flipped': t[6], 'source': t[7], 'proposal': t[8]})
    W = 1100
    H = sum(max(r.height, 44) + 14 for _, r in rows) + 10
    sh = Image.new('RGB', (W, H), (52, 60, 70))
    dr = ImageDraw.Draw(sh)
    y = 8
    for t, r in rows:
        bg = Image.new('RGBA', r.size, (30, 30, 30, 255))
        bg.alpha_composite(r)
        sh.paste(bg.convert('RGB'), (8, y))
        x = 8 + min(r.width, 660) + 16
        dr.text((x, y), f'{t[0]}  {t[3]} {t[4]}x{t[5]}' + ('  (위아래 뒤집혀 저장)' if t[6] else ''), font=font, fill=(255, 220, 120))
        cx = x
        for c in '원문: ' + t[7]:  # 한글은 맑은 고딕, 나머지는 유 고딕
            f = font if '가' <= c <= '힣' or c.isascii() else jfont
            dr.text((cx, y + 20), c, font=f, fill=(235, 235, 235))
            cx += f.getlength(c)
        dr.text((x, y + 40), '번역안: ' + t[8], font=font, fill=(140, 230, 160))
        y += max(r.height, 60) + 14
    sh = sh.crop((0, 0, W, y))
    sh.save(out / 'preview-all.png')
    (ROOT / 'manifests/graphics-targets.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(man), sh.size)


if __name__ == '__main__':
    main()
