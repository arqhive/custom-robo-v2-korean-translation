"""용어집을 합친다: 1편 용어·화자 번역 + 1편 핵심 용어 + 2편 새 용어(glossary-new.json).

출력: work/glossary/glossary-ko.json  {원문: {ko, src(v1/new), cat, q?}}
후보(candidates.json) 중 용어집에 없는 이름은 「빠짐」으로 출력한다.
"""
import json, os
from v1_reuse import V1, load

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, '..', 'work', 'glossary')

# 1편 대사·설명에서 확인한 핵심 용어(1편 번역 그대로)
V1_CORE = {
    'コマンダー': '커맨더', 'ホロセウム': '홀로세움', 'ホロセウム・デッキ': '홀로세움 덱',
    'ダイブ': '다이브', 'パーツ・ジェネレータ': '파츠 제너레이터', 'ロボキューブ': '로보 큐브',
    'アイ・コンタクト・レジスター': '아이 콘택트 레지스터', 'グレート・ロボカップ': '그레이트 로보 컵',
    'ロボカップ': '로보 컵', 'レギュレーション': '레귤레이션', '実体化': '실체화', 'デッキ': '덱',
    'ロボバトル': '로보 배틀', 'ロボステーション': '로보 스테이션',
    'カスタムロボステーション': '커스텀 로보 스테이션', 'パーツデータ': '파츠 데이터',
    '違法パーツ': '불법 파츠', 'ドレッド': '드레드', 'キャノボット': '캐노봇', 'カスタムロボ': '커스텀 로보',
    'パーツ': '파츠', 'ガン': '건', 'ボム': '봄', 'ポッド': '포드', 'レッグ': '레그', 'ロボ': '로보',
}


def main():
    out = {}
    for k, v in load(V1 + '/terms-ko.json').items():
        out[k] = {'ko': v, 'src': 'v1', 'cat': 'v1용어'}
    for k, v in load(os.path.join(G, 'v1-speakers.json')).items():
        out.setdefault(k, {'ko': next(iter(v)), 'src': 'v1', 'cat': '인물'})
    for k, v in V1_CORE.items():
        out.setdefault(k, {'ko': v, 'src': 'v1', 'cat': '핵심 용어'})
    new = load(os.path.join(G, 'glossary-new.json'))
    for cat, d in new.items():
        if cat.startswith('_'):
            continue
        for k, v in d.items():
            e = {'ko': v, 'src': 'new', 'cat': cat} if isinstance(v, str) else \
                {'ko': v['ko'], 'src': 'new', 'cat': cat, 'q': v['q']}
            if k in out and out[k]['ko'] != e['ko']:
                print('1편과 다름:', k, out[k]['ko'], '→', e['ko'])
            out[k] = e
    with open(os.path.join(G, 'glossary-ko.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 빠진 이름 검사: 파츠는 낱말 조합(건·봄·포드·레그 앞 부분)이 용어집에 있으면 통과
    cand = load(os.path.join(G, 'candidates.json'))
    miss = {}
    for cat in ('speakers', 'parts', 'stages', 'others'):
        for k, e in cand[cat].items():
            if k in out:
                continue
            if cat == 'speakers' and (e['count'] < 2 or k.startswith('［')):
                continue
            if cat == 'parts':
                stem = k
                for suf in ('ガン', 'ボム', 'ポッド', 'レッグ'):
                    if k.endswith(suf):
                        stem = k[:-len(suf)]
                if stem in out or any(stem == x for x in out):
                    continue
            miss.setdefault(cat, []).append(k)
    print('용어집', len(out), '항목 (1편', sum(1 for e in out.values() if e['src'] == 'v1'),
          '/ 새', sum(1 for e in out.values() if e['src'] == 'new'), ')')
    for cat, l in miss.items():
        print('빠짐', cat, len(l), ' / '.join(l))


if __name__ == '__main__':
    main()
