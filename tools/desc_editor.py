"""파츠 설명 편집 도구(11/07 사용자 요청).

python -X utf8 tools/desc_editor.py [제안.json]
  → work/translation/desc/desc-editor.html (브라우저로 열어 편집, 줄마다 넘침 경고)
python -X utf8 tools/desc_editor.py --apply <내려받은 desc-edits.json>
  → work/translation/desc-overrides.json 에 반영

편집 형식: 한 줄 = 한 항목(「・」 줄, 「 공중: …」 머리 줄). [글자] = 노란 강조(M), {L:글자} 같은 꼴 = 그 밖의 색.
화면 줄바꿈은 빌드와 같은 방식(reflow_dense: 글자 단위로 꽉 채움, 이어지는 줄은 한 칸 들여씀)으로 미리 보여 줌.
"""
import json, re, sys, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import build_full as B
import reflow

OUT = B.ROOT / 'work/translation/desc/desc-editor.html'
COLORS = {'M': '#f4e04d', 'L': '#7fd6ff', 'I': '#9cf59c', 'H': '#ff9c9c', 'K': '#c8a2ff'}


def paragraphs():
    src = {int(r['id'][1:], 16): r['source'] for r in B.load(B.TR / 'raw-text-all.json')}
    offs = sorted(src); out = []; i = 0
    while i < len(offs):
        if not src[offs[i]].startswith('N・'):
            i += 1; continue
        j = i + 1
        while j < len(offs) and src[offs[j]][:1] and ord(src[offs[j]][0]) in B.PREFIX and not src[offs[j]].startswith('N・'):
            j += 1
        out.append(offs[i:j]); i = j
    return src, out


def segs_to_edit(adj, drop=True):
    """조각 목록(접두 글자 포함) → 편집 글(줄 = 항목, [ ] = 노랑)."""
    parts = reflow.split_marks(reflow.drop_periods(adj) if drop else adj)
    out = ['']; cur = 'N'
    for k, t in enumerate(parts):
        st, x = t[:1], t[1:]
        if k == 0:
            st = 'N'
        if st == 'Z':
            out.append(''); st = 'N'
        if st == 'N' and re.match(r'[ 　]*[^ 　:：・·]{1,4}[:：]', x) and re.sub(r'[\[\]]|\{[A-Z]:|\}', '', out[-1]).strip(' 　・·'):
            out.append(' ' + x.lstrip(' 　'))      # 줄 중간 「공중:」 머리는 새 줄
        elif st == 'N':
            out[-1] += x
        elif st == 'M':
            out[-1] += '[' + x + ']' if x else ''
        else:
            out[-1] += '{%s:%s}' % (st, x) if x else ''
    # 원래 줄(일본어 줄 자리)을 항목으로 합침: 항목 시작(・, 머리 콜론, 빈 줄)이 아니면 앞 줄에 이어 붙임
    items = []
    for l in out:
        plain = re.sub(r'[\[\]]|\{[A-Z]:|\}', '', l)
        if not items or re.match(r'[ 　]*[・·]', plain) or re.match(r'[ 　]*[^ 　]{1,4}[:：]', plain):
            items.append(l.rstrip(' '))
        elif plain.strip(' 　'):
            prev_plain = re.sub(r'[\[\]]|\{[A-Z]:|\}', '', items[-1])
            body = l.lstrip(' 　')
            sep = '' if reflow.attaches(re.sub(r'[\[\]]|\{[A-Z]:|\}', '', body), prev_plain) else ' '
            items[-1] = items[-1].rstrip(' ') + sep + body
    t = '\n'.join(items).replace('][', '')
    t = re.sub(r' +([\]}])', r'\1 ', t)              # 색 구간 끝 공백은 밖으로
    t = re.sub(r'(?<=\S)  +', ' ', t)
    return '\n'.join(l.rstrip(' ') for l in t.split('\n'))


def edit_to_segs(text):
    """편집 글 → 빌드용 한 조각 글(§ 표시)."""
    out = []
    for n, line in enumerate(text.split('\n')):
        if not line.strip():
            continue
        if n and out:
            out.append('§Z')
        pos = 0
        for m in re.finditer(r'\[([^\]]*)\]|\{([A-Z]):([^}]*)\}', line):
            if m.start() > pos:
                out.append('§N' + line[pos:m.start()])
            out.append('§M' + m.group(1) if m.group(1) is not None else '§' + m.group(2) + m.group(3))
            pos = m.end()
        if pos < len(line):
            out.append('§N' + line[pos:])
    s = ''.join(out)
    s = s[1:] if s.startswith('§') else s          # 첫 조각은 접두 글자 그대로
    s = re.sub(r'§Z§N', '§Z', s)
    return s


RETRANS = {}   # 원문에서 다시 번역한 「안 줄인 번역」(work/translation/desc/retrans/out-*.json, 11/07)
for _f in sorted((B.ROOT / 'work/translation/desc/retrans').glob('out-*.json')):
    RETRANS.update(json.loads(_f.read_text(encoding='utf-8')))


def build(proposals):
    src, paras = paragraphs()
    disp = B.load_raw()
    base = {}
    for f in sorted((B.TR / 'out').glob('raw-*.json')):
        for k, v in B.load(f)['translations'].items():
            base[k] = v
    by_src = {}
    for k, v in base.items():
        by_src.setdefault(src.get(int(k[1:], 16)), v)
    sec = B.second_paras()
    rows = []; chars = set()
    for o in paras:
        if all((disp.get(x) or {}).get('translation') is None for x in o):
            continue
        pid = 'R%08X' % o[0]
        raws = [src[x].encode('euc_jp') for x in o]
        jl = reflow.lines_of([src[o[0]][1:]] + [src[x] for x in o[1:]])
        W = max(B.DESC_W, max(B.dlg_raw_width(l) for l in jl))
        limit = max(B.DESC_LINES[1 if o[0] in sec else 0], len(jl))
        best_adj = ['N・'] + [(by_src.get(src[x]) or src[x]) for x in o[1:]]
        if src[o[0]] != 'N・':
            best_adj = [(by_src.get(src[o[0]]) or src[o[0]])] + best_adj[1:]
        cur_adj = [(disp.get(x) or {}).get('translation') or src[x] for x in o]
        best = RETRANS.get(pid) or segs_to_edit(best_adj, drop=False)
        cur = segs_to_edit(cur_adj)
        if pid in proposals:
            cur = segs_to_edit(['N・', proposals[pid]] + ['N'] * (len(o) - 2))
        W = B.DESC_EDIT_W; limit = B.DESC_LINES[1 if o[0] in sec else 0]   # 편집 글은 빌드에서 120px·칸 줄 수로 검사(11/07)
        rows.append({'id': pid, 'limit': limit, 'W': W, 'jp': jl, 'best': best, 'cur': cur,
                     'second': o[0] in sec, 'proposed': pid in proposals})
        chars |= set(best + cur)
    widths = {c: B.dlg_raw_width(c) for c in chars if not ('가' <= c <= '힣') and c not in '\n[]{}'}
    widths[' '] = 7
    widths['□'] = B.dlg_raw_width('□')   # #a 같은 아이콘 코드 폭(빌드와 같게)
    data = json.dumps({'rows': rows, 'widths': widths, 'colors': COLORS}, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(PAGE.replace('/*DATA*/null', data), encoding='utf-8')
    print(OUT, len(rows))


def apply(path):
    edits = json.loads(Path(path).read_text(encoding='utf-8'))
    src, paras = paragraphs()
    first = {'R%08X' % o[0]: o for o in paras}
    ov = B.load(B.TR / 'desc-overrides.json')
    edited = dict(B.load(B.DESC_EDITED)) if B.DESC_EDITED.exists() and isinstance(B.load(B.DESC_EDITED), dict) else {}
    n = 0
    for pid, text in edits.items():
        o = first[pid]
        if len(o) < 2:
            print('조각 하나뿐이라 건너뜀', pid); continue
        ov['R%08X' % o[0]] = 'N・'
        body = re.sub(r'^(\[?)[・·]', lambda m: m.group(1), text, count=1)   # 첫 「・」는 첫 조각(N・)이 그림
        ov['R%08X' % o[1]] = edit_to_segs(body)
        for x in o[2:]:
            ov['R%08X' % x] = 'N'
        n += 1; edited[pid] = text
    (B.TR / 'desc-overrides.json').write_text(json.dumps(ov, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    B.DESC_EDITED.write_text(json.dumps(edited, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('반영', n)


PAGE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>파츠 설명 편집</title>
<style>
:root{--bg:#1d1b22;--card:#2a2730;--ink:#eee;--sub:#aaa;--bad:#ff6b6b;--ok:#6bd68b;--box:#5a2c3c}
body{background:var(--bg);color:var(--ink);font:14px/1.5 "Malgun Gothic",sans-serif;margin:0;padding:16px}
h1{font-size:18px;margin:0 0 8px}
.bar{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:2;display:flex;gap:12px;flex-wrap:wrap;align-items:center;border-bottom:1px solid #444}
.row{background:var(--card);border-radius:8px;padding:12px;margin:12px 0;display:grid;grid-template-columns:1fr 1fr 1fr 1.3fr 170px;gap:12px}
.row.bad{outline:2px solid var(--bad)}
.col h3{font-size:12px;color:var(--sub);margin:0 0 4px;font-weight:normal}
.txt{white-space:pre-wrap;font-size:13px}
textarea{width:100%;box-sizing:border-box;min-height:90px;background:#141217;color:var(--ink);border:1px solid #555;border-radius:4px;font:14px/1.5 "Malgun Gothic",monospace;padding:6px}
.prev{background:var(--box);padding:6px;font:12px/16px "Malgun Gothic",monospace;white-space:pre;border-radius:4px}
.ln{display:block}.ln.over{background:rgba(255,80,80,.35)}
.ln.extra{background:rgba(255,80,80,.6)}.ln.warn{background:rgba(255,180,0,.3)}.msg.warn{color:#ffb400}
.msg{font-size:12px;margin-top:4px}.msg.bad{color:var(--bad)}.msg.ok{color:var(--ok)}
.id{font-size:11px;color:var(--sub)}
button{background:#444;color:#fff;border:0;border-radius:4px;padding:6px 10px;cursor:pointer}
@media (max-width:900px){.row{grid-template-columns:1fr}}
</style></head><body>
<h1>파츠 설명 편집 <span class="id">한 줄 = 한 항목 · [글자] = 노란 강조 · 마침표는 입력 그대로 · 미리보기는 빌드와 같은 줄바꿈(글자 단위로 꽉 채움)</span></h1>
<div class="bar">
<label><input type="checkbox" id="onlyBad"> 넘치는 것만</label>
<label><input type="checkbox" id="onlyChanged"> 직접 고친 것만</label>

<button id="refilter" title="걸러 보기 목록을 지금 상태로 다시 고름">목록 다시 고르기</button>
<span id="sum"></span>
<button id="dl">전부 내려받기 (desc-edits.json)</button>
<button id="reset">입력 모두 안 줄인 번역으로</button>
</div>
<div id="list"></div>
<script>
const D=/*DATA*/null;
const KEY='desc-editor-v1';
let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const cw=c=>c===' '?7:(c>='가'&&c<='힣')?12:c.length>1?(D.widths['□']??12):(D.widths[c]??12);
const units=s=>s.match(/#[a-zA-Z]|[\s\S]/gu)||[];
const tw=s=>units(s).reduce((a,c)=>a+cw(c),0);
function parse(line){const out=[];let re=/\[([^\]]*)\]|\{([A-Z]):([^}]*)\}/g,p=0,m;
 while((m=re.exec(line))){if(m.index>p)out.push(['N',line.slice(p,m.index)]);out.push(m[1]!==undefined?['M',m[1]]:[m[2],m[3]]);p=re.lastIndex}
 if(p<line.length)out.push(['N',line.slice(p)]);return out}
function wrap(text,W){const lines=[];
 for(const raw of text.split('\n')){if(!raw.trim())continue;
  const segs=parse(raw);   // 마침표는 입력 그대로(11/07)
  const flat=[];segs.forEach(([st,x])=>units(x).forEach(c=>flat.push([st,c])));
  const s=flat.map(f=>f[1]).join('');
  const cont=/^[ 　]*[・·]/.test(s)?' ':(s.match(/^[ 　]*/)[0]);
  const cc=[...cont].map(c=>['N',c]);
  const lastReal=flat.reduce((a,f,i)=>f[1].trim()?i:a,-1);
  const isP=(fi,c)=>fi===lastReal&&(c==='.'||c==='。');
  const wrapIt=keepall=>{const L=[[]];let t='';
   for(const [fi,[st,c]] of flat.entries()){
    if(t.trim()&&tw(t+c)>W){
     if(isP(fi,c))continue;   // 넘치는 끝 마침표는 뺌(빌드와 같음)
     if(keepall&&c!==' '){const cur=L[L.length-1];let sp=-1;cur.forEach((x,i)=>{if(x[1]===' '&&i>cont.length)sp=i});
      if(sp<=0)return null;const moved=cur.slice(sp+1);L[L.length-1]=cur.slice(0,sp);L.push(cc.map(x=>[...x]).concat(moved));t=L[L.length-1].map(x=>x[1]).join('')}
     else{L.push(cc.map(x=>[...x]));t=cont;if(c===' ')continue}
     if(tw(t+c)>W){if(isP(fi,c))continue;return null}}
    L[L.length-1].push([st,c]);t+=c}
   return L};
  const dense=wrapIt(false),ka=wrapIt(true);
  const il=(ka&&ka.length<=dense.length)?ka:dense;   // 낱말 단위로 바꿔도 줄 수가 안 늘면 낱말째 내림(빌드와 같음)
  il.forEach(l=>lines.push(l))}
 return lines}
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function render(lines,W,limit){let bad=0;const html=lines.map((l,i)=>{const t=l.map(x=>x[1]).join('');const w=tw(t);const wc=tw(t.replace(/ *\.$/,''));
  const over=wc>W,extra=i>=limit,warn=false;if(over||extra)bad++;
  const inner=l.map(([st,c])=>st==='N'?esc(c):`<span style="color:${D.colors[st]||'#fff'}">${esc(c)}</span>`).join('');
  return `<span class="ln ${over?'over':''} ${extra?'extra':''} ${warn?'warn':''}" title="${w}px">${inner||'&nbsp;'}</span>`}).join('');
 return {html,bad,n:lines.length}}
const list=document.getElementById('list');
D.rows.forEach(r=>{
 const el=document.createElement('div');el.className='row';el.dataset.id=r.id;
 el.innerHTML=`<div class="col"><h3>원문 <span class="id">${r.id} · ${r.second?'아래 칸':'큰 칸'} ${r.limit}줄·${r.W}px</span></h3><div class="txt">${esc(r.jp.join('\n'))}</div></div>
 <div class="col"><h3>안 줄인 번역</h3><div class="txt">${esc(r.best)}</div></div>
 <div class="col"><h3>현재 번역</h3><div class="txt">${esc(r.cur)}</div></div>
 <div class="col"><h3>입력</h3><textarea spellcheck="false"></textarea><div class="msg"></div></div>
 <div class="col"><h3>화면 미리보기</h3><div class="prev"></div></div>`;
 const ta=el.querySelector('textarea');ta.value=saved[r.id]??r.best;
 const upd=()=>{const W=r.W;const L=wrap(ta.value,W);const o=render(L,W,r.limit);
  el.querySelector('.prev').innerHTML=o.html;const msg=el.querySelector('.msg');
  const lineMsg=L.map((l,i)=>{const w=tw(l.map(x=>x[1]).join('').replace(/ *\.$/,''));return w>W?`${i+1}번째 줄 ${w}px (한계 ${W})`:null}).filter(Boolean);
  if(o.n>r.limit)lineMsg.push(`${o.n}줄 — ${r.limit}줄 넘음`);
  const warnN=L.filter(l=>{const w=tw(l.map(x=>x[1]).join(''));return false}).length;
  msg.className='msg '+(lineMsg.length?'bad':warnN?'warn':'ok');
  msg.textContent=lineMsg.length?'⚠ '+lineMsg.join(' · '):warnN?`△ ${o.n}/${r.limit}줄 · 120px 넘는 줄 ${warnN}개(원문 폭 기준으론 통과, 칸에서 잘릴 수 있음)`:`✓ ${o.n}/${r.limit}줄`;
  el.classList.toggle('bad',lineMsg.length>0);el.dataset.bad=lineMsg.length?1:0;
  el.dataset.changed=ta.value!==r.best?1:0;
  if(ta.value!==r.best)saved[r.id]=ta.value;else delete saved[r.id];
  try{localStorage.setItem(KEY,JSON.stringify(saved))}catch(e){}
  filt()};
 ta.addEventListener('input',upd);el._upd=upd;list.appendChild(el)});
let badSnap=null,chgSnap=null;   // 걸러 보기는 체크한 순간의 목록으로 고정(고치는 중에 줄이 사라지지 않게)
function snap(){badSnap=onlyBad.checked?new Set([...list.querySelectorAll('.row')].filter(e=>e.dataset.bad==='1').map(e=>e.dataset.id)):null;
 chgSnap=onlyChanged.checked?new Set([...list.querySelectorAll('.row')].filter(e=>e.dataset.changed==='1').map(e=>e.dataset.id)):null;filt()}
function filt(){let b=0,c=0;
 list.querySelectorAll('.row').forEach(e=>{b+=+e.dataset.bad;c+=+e.dataset.changed;e.style.display=(badSnap&&!badSnap.has(e.dataset.id))||(chgSnap&&!chgSnap.has(e.dataset.id))?'none':''});
 sum.textContent=`전체 ${D.rows.length} · 넘침 ${b} · 고침 ${c}`}
onlyBad.onchange=snap;onlyChanged.onchange=snap;refilter.onclick=snap;
list.querySelectorAll('.row').forEach(e=>e._upd());
dl.onclick=()=>{const out={};list.querySelectorAll('.row').forEach(e=>{const r=D.rows.find(x=>x.id===e.dataset.id);const v=e.querySelector('textarea').value;out[r.id]=v});
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download='desc-edits.json';a.click()};
reset.onclick=()=>{if(!confirm('입력을 모두 안 줄인 번역으로 되돌릴까요? 직접 고친 내용은 지워집니다.'))return;saved={};try{localStorage.removeItem(KEY)}catch(e){};list.querySelectorAll('.row').forEach(e=>{e.querySelector('textarea').value=D.rows.find(x=>x.id===e.dataset.id).best;e._upd()})};
</script></body></html>'''


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--apply':
        apply(sys.argv[2])
    else:
        build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')) if len(sys.argv) > 1 else {})
