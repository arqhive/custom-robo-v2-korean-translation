"""대사 번역 기계 검사.

usage: python -X utf8 check_translation.py <묶음 이름 dlg-NN> [...]
  입력 work/translation/batches/<묶음>.json, 결과 work/translation/out/<묶음>/part-*.json(합쳐 읽음)
검사:
  누락·남는 id / 제어 코드($R 빼고 순서 동일, 쪽마다 $R 개수 동일) / 일본어 글자 / 후리가나 〔〕
  완성형(KS X 1001) 밖 한글·허용 밖 기호 / $A00·$B00 뒤 받침 따라 바뀌는 조사
  말줄임표·물결표 뒤 마침표 / 화자 이름이 용어집 번역과 같은지
합친 결과는 work/translation/out/<묶음>.json 으로 저장한다.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
G = os.path.join(HERE, '..', 'work', 'glossary')

KS_SET = {bytes([a, b]).decode('euc_kr') for a in range(0xB0, 0xC9) for b in range(0xA1, 0xFF)}
CODE = re.compile(r'\$[A-Z][0-9]{0,2}|#[A-Za-z]')
JP = re.compile(r'[ぁ-ゟァ-ヺ一-鿿]')
ALLOWED = set('、。，．・：；？！ー―‐／＼〜…‥‘’“”（）［］｛｝〈〉《》「」『』【】＋−±×÷＝≠＜＞≦≧∞∴♂♀°℃％＃＆＊＠☆★○●◎◇◆□■△▲▽▼※→←↑↓〓'
              '!?.,:;()%&*+-/~\'" 　$#=\n')
BAD_PARTICLE = re.compile(r'\$[AB]00(은|는|이|가|을|를|와|과|랑|이랑|야|이야|라는|이라는|으로|로|이라|라|여|이여)(?![가-힣])')
# 원문 그대로 두는 항목: 이름 입력 가나 표 4개(8단계 한글 이름 입력에서 따로 만든다),
# 실수 데이터를 문자열로 잘못 읽은 것 2개, 크레디트 저작권 줄(仝=© 글자)
KEEP = {'R0004FB38', 'R0004FC0C', 'R0004FCE0', 'R0004FDF4', 'R0011A3D4', 'R00147DD0', 'R000B1413'}
SPEAKER = re.compile(r'(?:^|\$P|\$F\d\d|\$R)([^「$　 ]{1,24})(?:\$R)?「')
SPEAKER_KO = re.compile(r'(?:^|\$P|\$F\d\d|\$R)([^「$　]{1,16})(?:\$R)?「')  # 번역 이름엔 띄어쓰기가 있다


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def merged(name):
    d = os.path.join(TR, 'out', name)
    tr, notes = {}, []
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            x = load(os.path.join(d, f))
            for k, v in x['translations'].items():
                if k in tr:
                    print('중복 id', k, f)
                tr[k] = v
            notes += x.get('notes', [])
    return tr, notes


def codes_wo_r(s):
    return [c for c in CODE.findall(s) if c != '$R']


def r_per_page(s):
    return [p.count('$R') for p in s.split('$P')]


def check_one(src, ko, gl):
    p = []
    if codes_wo_r(src) != codes_wo_r(ko):
        p.append('제어 코드 다름')
    elif r_per_page(src) != r_per_page(ko):
        p.append(f'쪽별 $R 개수 다름 {r_per_page(src)}→{r_per_page(ko)}')
    if JP.search(CODE.sub('', ko)):
        p.append('일본어 남음: ' + ''.join(JP.findall(ko))[:10])
    if '〔' in ko or '〕' in ko:
        p.append('후리가나 남음')
    for c in set(CODE.sub('', ko)):
        if '가' <= c <= '힣':
            if c not in KS_SET:     # euc_kr 코덱은 완성형 밖 글자도 8바이트 조합으로 바꿔 주므로 목록으로 확인
                p.append('완성형 밖 한글 ' + c)
        elif not (c.isascii() and c.isalnum()) and c not in ALLOWED and not ('０' <= c <= '９' or 'Ａ' <= c <= 'ｚ'):
            p.append('허용 밖 기호 ' + repr(c))
    m = BAD_PARTICLE.search(ko)
    if m:
        p.append('이름 뒤 조사 ' + m.group(0))
    if re.search(r'[…~〜]\.', ko):
        p.append('말줄임표·물결표 뒤 마침표')
    # 화면 문자열 조각 접두(Z N M I H K L)와 그 뒤 반각 공백 수는 그대로
    m1 = re.match(r'[ZNMIHKL](?=[^A-Za-z])( *)', src)
    if m1 and not ko.startswith(src[0] + m1.group(1)):
        p.append('조각 접두·앞 공백 바뀜')
    a = [x.group(1) for x in SPEAKER.finditer(src)]
    b = [x.group(1) for x in SPEAKER_KO.finditer(ko)]
    if len(a) == len(b):
        for x, y in zip(a, b):
            if x in gl and gl[x]['ko'] != y:
                p.append(f'화자 {x}→{y} (용어집 {gl[x]["ko"]})')
    else:
        p.append(f'화자 표시 수 다름 {len(a)}→{len(b)}')
    return p


def main():
    gl = load(os.path.join(G, 'glossary-ko.json'))
    for name in sys.argv[1:]:
        src = {x['id']: x['source'] for x in load(os.path.join(TR, 'batches', name + '.json'))}
        tr, notes = merged(name)
        miss = [k for k in src if k not in tr]
        extra = [k for k in tr if k not in src]
        bad = 0
        for k, s in src.items():
            if k in tr and k not in KEEP:
                p = check_one(s, tr[k], gl)
                if p:
                    bad += 1
                    print(k, '|', '; '.join(p))
        with open(os.path.join(TR, 'out', name + '.json'), 'w', encoding='utf-8') as f:
            json.dump({'translations': tr, 'notes': notes}, f, ensure_ascii=False, indent=1)
        print(f'{name}: 원문 {len(src)} / 번역 {len(tr)} / 빠짐 {len(miss)} / 남는 id {len(extra)} / 문제 {bad} / 메모 {len(notes)}')
        if miss:
            print('빠짐:', miss[:20])


if __name__ == '__main__':
    main()
