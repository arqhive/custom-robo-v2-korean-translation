"""7단계 기계 검수: 대사 번역 전체(out/dlg-*.json)에 검사를 돌려 work/review/machine-checks.json 으로 낸다.

검사
  창: 한 줄 204px·한 쪽 3줄(빌드가 줄을 다시 나누므로 「넘침 줄 수」는 참고), 한 낱말이 204px보다 길어 못 나누는 곳은 문제
  문장부호: 종결어미로 끝났는데 부호 없음, 말줄임표·물결표 뒤 마침표, 마침표 둘, 「・・・」 남음
  용어집: 원문에 용어집 원문(3자 이상)이 있는데 번역에 그 번역이 없음
"""
import collections, json, os, re
from check_dialogue import width, LINE_W, MAX_LINES

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
OUT = os.path.join(HERE, '..', 'work', 'review')
CODE = re.compile(r'\$[A-Z][0-9]{0,2}|#[A-Za-z]')
# 문장 끝으로 보는 어미(뒤에 부호가 있어야 함)
ENDING = re.compile(r'(다|요|까|지|야|어|아|네|군|걸|게|자|라|냐|니|래|죠|여|유|오|소|세|마|나|구먼|구나|거든|는데|잖아)$')


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def sentences_end(ko):
    """쪽·대기·닫는 괄호 앞의 말 끝 조각들을 돌려준다."""
    t = CODE.sub(lambda m: '\x00' if m.group(0) in ('$W', '$P', '$D') else '', ko)
    for seg in re.split(r'\x00|」', t):
        s = seg.rstrip(' 　')
        if s:
            yield s


def main():
    src, tr = {}, {}
    for f in sorted(os.listdir(os.path.join(TR, 'batches'))):
        if re.fullmatch(r'dlg-\d\d\.json', f):
            for x in load(os.path.join(TR, 'batches', f)):
                src[x['id']] = x['source']
            tr.update(load(os.path.join(TR, 'out', f))['translations'])
    gl = load(os.path.join(HERE, '..', 'work', 'glossary', 'glossary-ko.json'))
    terms = sorted(((k, v['ko']) for k, v in gl.items() if len(k) >= 3 and not k.startswith('〜')), key=lambda kv: -len(kv[0]))
    res = collections.defaultdict(list)
    overflow = 0
    for k, s in src.items():
        ko = tr[k]
        # 창
        over = False
        for page in ko.split('$P'):
            lines = page.split('$R')
            if len(lines) > MAX_LINES or any(width(l) > LINE_W for l in lines):
                over = True
            for l in lines:
                for w in re.split(r'[ 　]', CODE.sub('', l)):
                    if w and width(w) > LINE_W:
                        res['낱말이 한 줄보다 김'].append({'id': k, 'word': w})
        overflow += over
        # 문장부호
        for seg in sentences_end(ko):
            last = seg.split('$R')[-1] if '$R' in seg else seg
            if ENDING.search(last) and not re.search(r'[「『（(]$', last):
                res['문장 끝 부호 없음'].append({'id': k, 'end': last[-20:]})
        if re.search(r'[…~〜]\.', CODE.sub('', ko)):
            res['말줄임표·물결표 뒤 마침표'].append({'id': k})
        if re.search(r'(?<!\.)\.\.(?!\.)', ko):
            res['마침표 둘'].append({'id': k})
        if '・・' in ko:
            res['・・ 남음'].append({'id': k})
        # 용어집
        rest = s
        for jp, kv in terms:
            if jp in rest:
                rest = rest.replace(jp, '')
                if kv.replace(' ', '') not in ko.replace(' ', '') and not re.search(r'[（(]', kv):
                    res['용어집 불일치'].append({'id': k, 'jp': jp, 'ko': kv})
    os.makedirs(OUT, exist_ok=True)
    rep = {'대사 수': len(src), '빌드에서 줄 다시 나눌 대사': overflow,
           '검사별 개수': {k: len(v) for k, v in res.items()}, '항목': res}
    with open(os.path.join(OUT, 'machine-checks.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: rep[k] for k in ('대사 수', '빌드에서 줄 다시 나눌 대사', '검사별 개수')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
