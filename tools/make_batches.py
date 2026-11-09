"""대사를 번역 묶음으로 나눈다.

- 디버그 대사(스크립트 안 「全台詞」 뒤)는 뺀다(measure_dialogue.py 와 같은 기준).
- 같은 원문은 처음 나온 id(대표 id) 하나만 넣고, 나머지 id는 dup-map.json 에 적는다.
- 스크립트 경계에서 끊어 묶음 하나가 약 LIMIT 글자가 되게 한다.
출력: work/translation/batches/dlg-NN.json [{id, source}], dup-map.json {대표 id: [같은 원문 id...]},
      raw-NN.json(화면 문자열, raw_batches)
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
OUT = os.path.join(TR, 'batches')
LIMIT = 24000


def dialogue_rows():
    rows = json.load(open(os.path.join(TR, 'source-texts.json'), encoding='utf-8'))
    debug, last, out = False, None, []
    for r in rows:
        if r['script'] != last:
            debug, last = False, r['script']
        if r['source'] == '全台詞':
            debug = True
        if r['kind'] == 'dialogue' and not debug:
            out.append(r)
    return out


def main():
    rows = dialogue_rows()
    first, dup, uniq = {}, {}, []
    for r in rows:
        s = r['source']
        if s in first:
            dup.setdefault(first[s], []).append(r['id'])
        else:
            first[s] = r['id']
            uniq.append(r)
    os.makedirs(OUT, exist_ok=True)
    batches, cur, size, last = [], [], 0, None
    for r in uniq:
        if size >= LIMIT and r['script'] != last:
            batches.append(cur)
            cur, size = [], 0
        cur.append({'id': r['id'], 'source': r['source']})
        size += len(r['source'])
        last = r['script']
    if cur:
        batches.append(cur)
    for i, b in enumerate(batches):
        with open(os.path.join(OUT, f'dlg-{i:02d}.json'), 'w', encoding='utf-8') as f:
            json.dump(b, f, ensure_ascii=False, indent=1)
        sc = sorted({x['id'][1:4] for x in b})
        print(f'dlg-{i:02d}', len(b), '줄', sum(len(x['source']) for x in b), '자', '스크립트', sc[0], '~', sc[-1])
    with open(os.path.join(OUT, 'dup-map.json'), 'w', encoding='utf-8') as f:
        json.dump(dup, f, ensure_ascii=False, indent=1)
    print('대표', len(uniq), '중복 id', sum(len(v) for v in dup.values()))
    raw_batches()


def raw_batches(limit=9000):
    """화면 문자열(class=display)을 원문 단위로 한 번씩, 구역·롬 순서대로 묶는다 → raw-NN.json [{id, area, source}]"""
    rows = json.load(open(os.path.join(TR, 'raw-text-all.json'), encoding='utf-8'))
    rows = [r for r in rows if r.get('class') == 'display']
    rows.sort(key=lambda r: r['rom_offset'])
    seen, uniq = set(), []
    for r in rows:
        if r['source'] not in seen:
            seen.add(r['source'])
            uniq.append({'id': r['id'], 'area': r['area'], 'source': r['source']})
    batches, cur, size = [], [], 0
    for r in uniq:
        if size >= limit:
            batches.append(cur)
            cur, size = [], 0
        cur.append(r)
        size += len(r['source'])
    if cur:
        batches.append(cur)
    for i, b in enumerate(batches):
        with open(os.path.join(OUT, f'raw-{i:02d}.json'), 'w', encoding='utf-8') as f:
            json.dump(b, f, ensure_ascii=False, indent=1)
        print(f'raw-{i:02d}', len(b), '개', sum(len(x['source']) for x in b), '자', sorted({x['area'] for x in b}))


if __name__ == '__main__':
    main()
