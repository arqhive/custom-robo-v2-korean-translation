"""さん 호칭을 관계대로 바꾼다(10/23 사용자 결정: 권장안).

아이가 손위에게: 겐타·타이헤이·소년 → 형/누나, 유리에·소녀·후타바 → 오빠/언니.
대상은 타쿠마·지로·켄고·토라지(남)·나나세(여). 마모루는 1편처럼 「씨」 유지, 어른·공적 관계도 「씨」.
「씨」 뒤 조사는 받침에 맞게 고친다(씨가→형이). 화자 단위(tone_survey.split)로 원문에 その人+さん/しゃん 이 있을 때만.
기록: work/translation/unify-log.json 에 덧붙임.
"""
import json, os, re
from tone_survey import split

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, '..', 'work', 'translation')
TARGET = {'タクマ': ('타쿠마', 'm'), 'ジロウ': ('지로', 'm'), 'ケンゴ': ('켄고', 'm'), 'トラジ': ('토라지', 'm'), 'ナナセ': ('나나세', 'f')}
BOYS = {'ゲンタ', 'タイヘイ', '少年'}
GIRLS = {'ユリエ', '少女', 'フタバ', '妹のフタバ'}
# 「씨」 뒤 조사 → (받침 있는 말 뒤, 받침 없는 말 뒤)
PART = {'가': ('이', '가'), '는': ('은', '는'), '를': ('을', '를'), '와': ('과', '와'), '랑': ('이랑', '랑'),
        '야': ('이야', '야'), '로': ('으로', '로'), '라': ('이라', '라'), '라고': ('이라고', '라고'),
        '라는': ('이라는', '라는'), '였': ('이었', '였'), '예요': ('이에요', '예요'), '여': ('이여', '여')}


def title(sp, g):
    if sp in BOYS:
        return '형' if g == 'm' else '누나'
    return '오빠' if g == 'm' else '언니'


def fix_seg(sp, jp, kt):
    for j, (ko, g) in TARGET.items():
        if j + 'さん' not in jp and j + 'しゃん' not in jp:
            continue
        t = title(sp, g)
        batchim = t == '형'

        def rep(m):
            p = m.group(1) or ''
            for k in sorted(PART, key=len, reverse=True):
                if p.startswith(k):
                    p = PART[k][0 if batchim else 1] + p[len(k):]
                    break
            return f'{ko} {t}{p}'
        kt = re.sub(ko + r' ?씨((?:라고|라는|예요|[가는를와랑야로라였여])?)', rep, kt)
    return kt


def main():
    log_p = os.path.join(TR, 'unify-log.json')
    log = json.load(open(log_p, encoding='utf-8'))
    src = {}
    for f in os.listdir(os.path.join(TR, 'batches')):
        if re.fullmatch(r'dlg-\d\d\.json', f):
            for x in json.load(open(os.path.join(TR, 'batches', f), encoding='utf-8')):
                src[x['id']] = x['source']
    n = skipped = 0
    for b in sorted(os.listdir(os.path.join(TR, 'out'))):
        d = os.path.join(TR, 'out', b)
        if not (os.path.isdir(d) and b.startswith('dlg-')):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            data = json.load(open(p, encoding='utf-8'))
            ch = False
            for k, v in data['translations'].items():
                a, bb = split(src[k]), split(v)
                if not any(s in BOYS | GIRLS for s, _ in a):
                    continue
                if len(a) != len(bb):
                    if any(j + 'さん' in src[k] for j in TARGET):
                        skipped += 1
                        print('화자 정렬 안 맞음(손으로 확인):', k)
                    continue
                # 화자 조각 단위로 다시 조립: 번역문에서 각 조각 위치를 찾아 바꾼다
                new, pos = v, 0
                for (sp, jt), (_, kt) in zip(a, bb):
                    if sp not in BOYS | GIRLS:
                        continue
                    fk = fix_seg(sp, jt, kt)
                    if fk != kt:
                        i = new.find(kt, pos)
                        new = new[:i] + fk + new[i + len(kt):]
                        pos = i + len(fk)
                if new != v:
                    log.append({'id': k, '묶음': b, 'rule': 'さん 호칭 관계대로(형·누나·오빠·언니)', 'before': v, 'after': new})
                    data['translations'][k] = new
                    ch = True
                    n += 1
            if ch:
                json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(log, open(log_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('바뀐 줄', n, '손으로 볼 줄', skipped)


if __name__ == '__main__':
    main()
