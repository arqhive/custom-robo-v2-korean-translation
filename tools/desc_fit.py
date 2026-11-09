"""파츠 설명 편집 글이 칸에 들어가는지 검사(편집기 미리보기·빌드와 같은 줄바꿈).

python -X utf8 tools/desc_fit.py <글.json {id: 편집 글}> [--w 120]
  줄마다 화면 줄과 px, 넘침을 보여 줌. --w 를 주면 모든 단락을 그 폭으로 검사(엄격, 기본 120).
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import build_full as B
import reflow
import desc_editor as E


def lines(text, W):
    kl = reflow.lines_of(reflow.edited_block(text, W))   # 빌드와 같은 길(입력 줄 그대로, 11/07)
    while len(kl) > 1 and not kl[-1].strip():
        kl = kl[:-1]
    return kl


def main():
    args = sys.argv[1:]
    W0 = B.DESC_EDIT_W
    if '--w' in args:
        i = args.index('--w'); W0 = int(args[i + 1]); del args[i:i + 2]
    texts = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    src, paras = E.paragraphs(); sec = B.second_paras()
    limit = {'R%08X' % o[0]: B.DESC_LINES[1 if o[0] in sec else 0] for o in paras}
    bad = 0
    for pid, t in texts.items():
        kl = lines(t, W0)
        over = [i for i, l in enumerate(kl) if B.dlg_raw_width(l.rstrip(' ').rstrip('.')) > W0]
        ok = not over and len(kl) <= limit[pid]
        bad += not ok
        print(('OK ' if ok else 'XX ') + pid, f'{len(kl)}/{limit[pid]}줄')
        for i, l in enumerate(kl):
            print('   ', ('!! ' if i in over else '   ') + l, B.dlg_raw_width(l))
    print('넘침', bad, '/', len(texts))


if __name__ == '__main__':
    main()
