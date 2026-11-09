"""파츠 설명 단락이 빌드에서 들어가는지 검사(롬 안 씀). 바꿀 번역을 넣어 보고 맞는지 확인하는 데 씀.

usage:
  python -X utf8 check_desc_fit.py packet <출력.json> [후보.json] → 안 들어가는 설명(같은 원문 묶음은 하나로) 작업 묶음
  python -X utf8 check_desc_fit.py check <후보.json> [id ...] → 후보 {조각 id: 새 번역}을 넣고 설명마다 맞는지
판정 = 빌드 reflow_desc 와 같음: 폭 120px(원문이 더 넓으면 그 폭), 줄 수 큰 칸 6·아래 칸 4(원문이 더 많으면 원문),
바이트는 참고로만 보여 줌(설명은 포인터 묶음 안이라 빌드가 옮길 수 있어 제한 아님).
"""
import json, sys, collections
import build_full as B, name_input, particles, reflow

SRC = (B.ROOT / 'Custom Robo V2 (Japan).z64').read_bytes()


def setup():
    g = name_input.KS + name_input.JAMO
    B.GLYPHS.update({c: name_input.idx2code(i) for i, c in enumerate(g)})
    for k, (tok, _) in enumerate(particles.KINDS):
        B.GLYPHS[particles.CHAR[tok]] = name_input.idx2code(len(g) + k)
    return B.load_raw()


def evaluate(disp):
    """설명 단락마다 (run, 결과 dict)."""
    out = []; prev_end = None; idx = 0
    for run in B.desc_runs(SRC, disp, set()):
        idx = idx + 1 if prev_end == run['start'] else 0
        prev_end = run['end']
        mem = run['members']; raws = [SRC[a:b] for a, b in mem]
        texts = [disp[a]['translation'] if a in disp else None for a, _ in mem]
        if all(t is None for t in texts):
            continue
        parts = [t if t is not None else r.decode('euc_jp', 'replace') for t, r in zip(texts, raws)]
        adj = B.adjust_parts(parts)
        jl = reflow.lines_of([raws[0].decode('euc_jp')[1:]] + [r.decode('euc_jp') for r in raws[1:]])
        W = max(B.DESC_W, max(B.dlg_raw_width(l) for l in jl))
        adj = reflow.split_marks(reflow.drop_periods(adj))
        new = reflow.reflow_block([adj[0][1:]] + adj[1:], W)
        for i in range(len(new)):
            if i + 1 == len(new) or new[i + 1][:1] == 'Z':
                new[i] = new[i].rstrip(' ')
        kl = reflow.lines_of(new)
        while len(kl) > 1 and not kl[-1].strip():   # 끝 빈 줄은 화면에 안 보임: 줄 수에서 뺌
            kl = kl[:-1]
        limit = max(B.DESC_LINES[min(idx, 1)], len(jl))
        body = b'\0'.join([B.enc_seg('N' + new[0], True)] + [B.enc_seg(x, True) for x in new[1:]]) + b'\0'
        size = run['end'] - run['start']
        if not run['next_ndot']:
            z = 0
            while SRC[run['end'] + z] == 0:
                z += 1
            size += max(0, z - 4)
        # 바이트는 판정에서 뺌: 설명은 파츠 이름 포인터 묶음 안이라 빌드가 묶음째 옮길 수 있음(11/07 확인)
        ok = len(kl) <= limit and all(B.dlg_raw_width(l) <= W for l in kl)
        out.append((run, {'start': 'R%08X' % run['start'], 'ok': ok, 'lines': kl, 'limit': limit, 'W': W,
                          'bytes': len(body), 'size': size, 'jp': jl,
                          'members': [('R%08X' % a, SRC[a:b].decode('euc_jp', 'replace'), t) for (a, b), t in zip(mem, texts)]}))
    return out


def main():
    cmd = sys.argv[1]
    disp = setup()
    candf = sys.argv[2] if cmd == 'check' else (sys.argv[3] if len(sys.argv) > 3 else None)
    if candf:
        cand = json.load(open(candf, encoding='utf-8'))
        src_of = {'R%08X' % p: r['source'] for p, r in disp.items()}
        bysrc = {src_of[k]: v for k, v in cand.items()}
        for p, r in disp.items():
            if r['source'] in bysrc:
                r['translation'] = bysrc[r['source']]
        ov = B.TR / 'desc-overrides.json'          # 자리별 덮어쓰기가 원문 단위 후보보다 앞섬
        if ov.exists():
            for k, v in json.load(open(ov, encoding='utf-8')).items():
                if int(k[1:], 16) in disp:
                    disp[int(k[1:], 16)]['translation'] = v
    res = evaluate(disp)
    groups = collections.OrderedDict()
    for run, r in res:
        key = tuple(m[1] for m in r['members'])
        g = groups.setdefault(key, {'runs': [], 'ok': True, 'size': 10 ** 9, 'limit': 99, 'r': r})
        g['runs'].append(r['start']); g['ok'] &= r['ok']; g['size'] = min(g['size'], r['size']); g['limit'] = min(g['limit'], r['limit'])
        if r['bytes'] - r['size'] > g['r']['bytes'] - g['r']['size']:
            g['r'] = r
    if cmd == 'packet':
        pk = []
        for key, g in groups.items():
            if g['ok']:
                continue
            r = g['r']
            pk.append({'desc': r['start'], 'runs': g['runs'], 'max_bytes': g['size'], 'max_lines': g['limit'], 'width': r['W'],
                       'now_bytes': r['bytes'], 'now_lines': r['lines'], 'jp_lines': r['jp'],
                       'fragments': [{'id': i, 'source': s, 'ko': t} for i, s, t in r['members']]})
        json.dump(pk, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('안 들어가는 설명', len(pk), '/', len(groups))
        return
    want = set(sys.argv[3:])
    bad = 0
    for key, g in groups.items():
        r = g['r']
        if want and not want & set(g['runs']):
            continue
        bad += not g['ok']
        if want or not g['ok']:
            print(('OK  ' if g['ok'] else 'OVER'), r['start'], f"바이트 {r['bytes']}/{g['size']} 줄 {len(r['lines'])}/{g['limit']}")
            if want:
                for l in r['lines']: print('    ', B.dlg_raw_width(l), l)
    print('안 들어가는 설명', bad, '/', len(groups))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
