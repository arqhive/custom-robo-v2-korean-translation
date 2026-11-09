"""검수 수정안 대조표: work/review/out-*.json 을 모아 work/review/검수_대조표.html 로 낸다.

열: id | 종류 | 원문 | 수정 전 | 수정 후 | 이유. 질문 항목은 따로 모은다.
제어 코드는 흐리게, $R·$P 는 줄바꿈 표시로 보여 준다. 종류별 거르기(브라우저에서 체크 상자).
"""
import html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
TR = os.path.join(ROOT, 'work', 'translation')
RV = os.path.join(ROOT, 'work', 'review')


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def show(s):
    s = html.escape(s or '')
    s = s.replace('$P', '<span class=c>$P</span><br><br>').replace('$R', '<span class=c>$R</span><br>')
    return re.sub(r'(\$[A-Z][0-9]{0,2}|#[A-Za-z])', r'<span class=c>\1</span>', s)


def main():
    src = {}
    for f in os.listdir(os.path.join(TR, 'batches')):
        if re.fullmatch(r'(dlg|raw)-\d\d\.json', f):
            for x in load(os.path.join(TR, 'batches', f)):
                src[x['id']] = x['source']
    rows, qs = [], []
    for f in sorted(os.listdir(RV)):
        m = re.fullmatch(r'out-((?:dlg|raw)-\d\d)\.json', f)
        if not m:
            continue
        for it in load(os.path.join(RV, f)):
            it['batch'] = m.group(1)
            (qs if it.get('after') is None else rows).append(it)
    kinds = sorted({r.get('kind', '?') for r in rows})
    css = ('body{font-family:"Malgun Gothic","Yu Gothic",sans-serif;font-size:14px;margin:16px;background:#fafafa}'
           'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;vertical-align:top}'
           'th{background:#334;color:#fff;position:sticky;top:0}.c{color:#aaa;font-size:11px}'
           'td.k{white-space:nowrap}tr:nth-child(even){background:#f0f0f4}.jp{font-family:"Yu Gothic",sans-serif}')
    out = [f'<!doctype html><meta charset=utf-8><title>V2 검수 대조표</title><style>{css}</style>',
           f'<h1>커스텀 로보 V2 원문 대조 검수</h1><p>수정안 {len(rows)}건 · 질문 {len(qs)}건</p><p>']
    for k in kinds:
        n = sum(1 for r in rows if r.get('kind') == k)
        out.append(f'<label><input type=checkbox checked onchange="f()" value="{html.escape(k)}"> {html.escape(k)} {n}</label> ')
    out.append('</p><table><tr><th>id</th><th>종류</th><th>원문</th><th>수정 전</th><th>수정 후</th><th>이유</th></tr>')
    for r in rows:
        out.append(f'<tr data-k="{html.escape(r.get("kind", "?"))}"><td class=k>{r["id"]}</td><td class=k>{html.escape(r.get("kind", ""))}</td>'
                   f'<td class=jp>{show(src.get(r["id"]))}</td><td>{show(r.get("before"))}</td><td>{show(r["after"])}</td>'
                   f'<td>{html.escape(r.get("reason", ""))}</td></tr>')
    out.append('</table>')
    if qs:
        out.append('<h2>질문</h2><table><tr><th>id</th><th>원문</th><th>지금 번역</th><th>질문</th></tr>')
        for r in qs:
            out.append(f'<tr><td class=k>{r["id"]}</td><td class=jp>{show(src.get(r["id"]))}</td><td>{show(r.get("before"))}</td>'
                       f'<td>{html.escape(r.get("question", ""))}</td></tr>')
        out.append('</table>')
    out.append('<script>function f(){const on=[...document.querySelectorAll("input:checked")].map(e=>e.value);'
               'document.querySelectorAll("tr[data-k]").forEach(t=>t.style.display=on.includes(t.dataset.k)?"":"none")}</script>')
    with open(os.path.join(RV, '검수_대조표.html'), 'w', encoding='utf-8') as fo:
        fo.write('\n'.join(out))
    print('수정안', len(rows), '질문', len(qs), {k: sum(1 for r in rows if r.get('kind') == k) for k in kinds})


if __name__ == '__main__':
    main()
