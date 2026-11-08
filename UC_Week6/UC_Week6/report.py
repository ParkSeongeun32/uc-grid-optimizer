"""
⑤ report.py : 결과를 "보기 좋은" HTML 대시보드로 만들기
------------------------------------------------------------
- 결과 HTML 파일을 더블클릭하면 브라우저에서 열림 (그래프는 마우스를 올리면 값이 보임)
- 그래프 라이브러리(Chart.js)는 인터넷으로 불러오므로 인터넷 연결이 필요
- 데이터는 HTML 안에 같이 저장되므로 파일 하나만 보내면 다른 사람도 볼 수 있음
"""
import json, html
from visualize import gen_colors, merit_order, text_on

CSS = r"""
:root{--bg:#FFFFFF;--panel:#F2F5F6;--ink:#1B2733;--muted:#5E6E7A;--line:#DDE3E7;--off:#E9EEF0;
--good:#2E9E6B;--bad:#D64545;--warn:#C27C0E;--same:#AEBBC3;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0F1720;--panel:#17222C;--ink:#E6ECEF;--muted:#93A3AE;
--line:#26343F;--off:#1E2B36;--good:#3DBB83;--bad:#E46161;--warn:#E3A43A;--same:#4A5B68;color-scheme:dark}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font-family:"IBM Plex Sans KR","Malgun Gothic","Apple SD Gothic Neo",sans-serif;line-height:1.55;
font-feature-settings:"tnum"}
.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 80px}
header .scn{font-size:15px;color:var(--muted);margin:0}
header h1{font-size:30px;margin:4px 0 22px;font-weight:600;letter-spacing:-.01em}
.hero{display:flex;align-items:flex-end;gap:36px;flex-wrap:wrap}
.big{font-size:64px;font-weight:700;line-height:1;letter-spacing:-.02em}
.big small{font-size:20px;font-weight:500;color:var(--muted);margin-left:8px}
.pill{display:inline-block;padding:3px 12px;border-radius:999px;font-size:13px;background:var(--panel);color:var(--muted)}
.pill.ok{color:var(--good)} .pill.no{color:var(--bad)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0;margin:30px 0 8px;
border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.stat{padding:16px 18px}
.stat+.stat{border-left:1px solid var(--line)}
.stat b{display:block;font-size:24px;font-weight:600}
.stat span{font-size:13px;color:var(--muted)}
.merit{margin:34px 0 6px}
.merit p{margin:0 0 8px;font-size:13px;color:var(--muted)}
.strip{display:flex;height:38px;border-radius:8px;overflow:hidden}
.strip div{display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;
min-width:28px;border-right:2px solid var(--bg)}
.ends{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-top:4px}
section{margin-top:52px}
h2{font-size:20px;margin:0 0 4px;font-weight:600}
.sub{color:var(--muted);font-size:14px;margin:0 0 18px}
.notes{list-style:none;padding:0;margin:0;display:grid;gap:10px}
.notes li{background:var(--panel);padding:12px 16px;border-radius:10px;font-size:15px}
.chart{position:relative;height:420px}
.chart.sm{height:300px}
.two{display:grid;grid-template-columns:1fr 1.4fr;gap:40px}
@media (max-width:820px){.two{grid-template-columns:1fr}.big{font-size:46px}}
.scroll{overflow-x:auto}
.hm{display:grid;gap:3px;min-width:760px}
.hm .c{height:30px;border-radius:4px;font-size:11px;display:flex;align-items:center;justify-content:center}
.hm .lab{font-size:13px;font-weight:600;justify-content:flex-start;padding-right:6px}
.hm .hd{font-size:11px;color:var(--muted);height:20px}
.hm .offc{background:var(--off)}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:640px}
th,td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:13px}
th:first-child,td:first-child{text-align:left}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px;vertical-align:middle}
.role{font-size:12px;padding:2px 8px;border-radius:999px;background:var(--panel)}
.delta.up{color:var(--bad)} .delta.down{color:var(--good)}
.scard{border-top:1px solid var(--line);padding-top:26px;margin-top:40px}
.scard h3{font-size:19px;margin:0;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
.scard .chg{font-size:14px;color:var(--muted);margin:4px 0 16px}
.legend{display:flex;gap:18px;font-size:13px;color:var(--muted);margin:10px 0;flex-wrap:wrap}
footer{margin-top:64px;color:var(--muted);font-size:12px}
.net{background:var(--panel);border-radius:14px;padding:14px 16px}
.net svg{width:100%;height:auto;display:block}
.ctl{display:flex;align-items:center;gap:14px;font-size:14px;margin:0 0 8px}
.ctl input[type=range]{flex:1}
.ctl b{min-width:72px}
.hm .u0{background:#B9C2C8}.hm .u1{background:#E0B52E}.hm .u2{background:#D64545;color:#fff;font-weight:700}.hm .u3{background:#7A1B2E;color:#fff;font-weight:700}
.tag{display:inline-block;font-size:12px;padding:2px 9px;border-radius:999px;background:var(--panel);color:var(--muted);margin-left:8px}
"""

HEAD = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>__CSS__</style></head><body><div class="wrap">"""

JS_COMMON = r"""
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
if(window.Chart){Chart.defaults.font.family='"IBM Plex Sans KR","Malgun Gothic",sans-serif';
Chart.defaults.color=css('--muted');Chart.defaults.borderColor=css('--line');}
"""


def _esc(s):
    return html.escape(str(s))


def _hex_alpha(hx, a):
    hx = hx.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return f"rgba({r},{g},{b},{a:.2f})"


def merit_strip(gens):
    col = gen_colors(gens)
    order = merit_order(gens)
    total = gens["p_max"].sum()
    cells = "".join(
        f'<div style="flex:{gens.loc[g,"p_max"]/total:.4f};background:{col[g]};color:{text_on(col[g])}" '
        f'title="{_esc(g)} · 최대 {gens.loc[g,"p_max"]:.0f} MW">{_esc(g)}</div>' for g in order)
    return (f'<div class="merit"><p>급전순위 — 왼쪽일수록 싼 발전기, 폭은 설비용량 (총 {total:,.0f} MW). '
            f'모든 그래프의 색은 이 순서를 따릅니다.</p><div class="strip">{cells}</div>'
            f'<div class="ends"><span>싸다 · 기저</span><span>비싸다 · 첨두</span></div></div>')


def heatmap_html(res):
    u, P, gens = res["u"], res["P"], res["gens"]
    col, order, T = gen_colors(gens), merit_order(gens), list(P.columns)
    cells = [f'<div class="c hd"></div>'] + [f'<div class="c hd">{t}</div>' for t in T]
    for g in order:
        cells.append(f'<div class="c lab">{_esc(g)}</div>')
        for t in T:
            if u.loc[g, t]:
                a = min(1.0, max(0.0, 0.35 + 0.65 * P.loc[g, t] / gens.loc[g, "p_max"]))
                fg = text_on(col[g], a)
                cells.append(f'<div class="c" style="background:{_hex_alpha(col[g], a)};color:{fg}" '
                             f'title="{_esc(g)} {t}시: {P.loc[g,t]:.1f} MW">{P.loc[g,t]:.0f}</div>')
            else:
                cells.append(f'<div class="c offc" title="{_esc(g)} {t}시: 정지"></div>')
    return (f'<div class="scroll"><div class="hm" style="grid-template-columns:56px repeat({len(T)},1fr)">'
            + "".join(cells) + "</div></div>")


def diff_html(base, res):
    order, T = merit_order(base["gens"]), list(base["u"].columns)
    ub, us = base["u"], res["u"]
    cells = [f'<div class="c hd"></div>'] + [f'<div class="c hd">{t}</div>' for t in T]
    for g in order:
        cells.append(f'<div class="c lab">{_esc(g)}</div>')
        for t in T:
            a, b = ub.loc[g, t], us.loc[g, t]
            if a and b:
                cells.append(f'<div class="c" style="background:var(--same)" title="{g} {t}시: 그대로 운전"></div>')
            elif b:
                cells.append(f'<div class="c" style="background:var(--good);color:#fff;font-weight:700" title="{g} {t}시: 새로 켜짐">+</div>')
            elif a:
                cells.append(f'<div class="c" style="background:var(--bad);color:#fff;font-weight:700" title="{g} {t}시: 꺼짐">−</div>')
            else:
                cells.append('<div class="c offc"></div>')
    return (f'<div class="scroll"><div class="hm" style="grid-template-columns:56px repeat({len(T)},1fr)">'
            + "".join(cells) + "</div></div>")


# ---------------- [Week6] 송전 · AIDC 구성요소 ----------------
def _util_cls(u):
    return "u3" if u > 1.001 else "u2" if u >= 0.999 else "u1" if u >= 0.8 else "u0"


def line_util_html(res):
    """선로 x 시간 이용률 표 (셀 색: 회색 <80%, 노랑 80~100%, 빨강 100% 혼잡)"""
    util, T = res["util"], list(res["util"].columns)
    cells = ['<div class="c hd"></div>'] + [f'<div class="c hd">{t}</div>' for t in T]
    for l in util.index:
        cells.append(f'<div class="c lab">{_esc(l)}</div>')
        for t in T:
            u = float(util.loc[l, t])
            cells.append(f'<div class="c {_util_cls(u)}" title="{l} {t}시: {res["flow"].loc[l,t]:+.1f} MW ({100*u:.1f}%)">{100*u:.0f}</div>')
    return (f'<div class="scroll"><div class="hm" style="grid-template-columns:56px repeat({len(T)},1fr)">'
            + "".join(cells) + "</div></div>")


def network_data(res):
    """계통도 그리기용 데이터 (JS 에서 시간 슬라이더로 다시 그림)"""
    b, ln, gens, T = res["buses"], res["lines"], res["gens"], list(res["P"].columns)
    N = list(b.index)
    return {
        "T": T,
        "buses": [{"n": int(n), "name": str(b.loc[n, "name"]), "x": float(b.loc[n, "x"]), "y": float(b.loc[n, "y"]),
                   "gens": [g for g in gens.index if int(gens.loc[g, "bus"]) == n],
                   "aidc": [a for a in res["aidc"].index if int(res["aidc"].loc[a, "bus"]) == n] if len(res["aidc"]) else [],
                   "load": [round(float(res["bus_load"].loc[n, t]), 1) for t in T],
                   "gen": [round(float(res["P"].loc[[g for g in gens.index if int(gens.loc[g, "bus"]) == n], t].sum()), 1) for t in T],
                   "aidcP": [round(float(res["aidc_P"].loc[[a for a in res["aidc"].index if int(res["aidc"].loc[a, "bus"]) == n], t].sum()), 1) if len(res["aidc"]) else 0 for t in T],
                   "nse": [round(float(res["nse_bus"].loc[n, t]), 1) for t in T]} for n in N],
        "lines": [{"l": l, "i": int(ln.loc[l, "from_bus"]), "j": int(ln.loc[l, "to_bus"]), "fmax": float(ln.loc[l, "f_max_MW"]),
                   "f": [round(float(res["flow"].loc[l, t]), 1) for t in T]} for l in ln.index],
        "peak": int(res["D_total"].idxmax()),
    }


JS_NET = r"""
function netSVG(ND, t, elId){
  const k=ND.T.indexOf(t); const xs=ND.buses.map(b=>b.x), ys=ND.buses.map(b=>b.y);
  const minx=Math.min(...xs)-0.9, maxx=Math.max(...xs)+0.9, miny=Math.min(...ys)-1.15, maxy=Math.max(...ys)+0.6;
  const S=130, W=(maxx-minx)*S, H=(maxy-miny)*S, X=x=>(x-minx)*S, Y=y=>(maxy-y)*S;
  const pos={}; ND.buses.forEach(b=>pos[b.n]=[X(b.x),Y(b.y)]);
  const col=u=>u>1.001?'#7A1B2E':u>=0.999?'#D64545':u>=0.8?'#E0B52E':'#6B7A86';
  let s=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans KR,Malgun Gothic,sans-serif">`;
  s+=`<defs>${['#7A1B2E','#D64545','#E0B52E','#6B7A86'].map(c=>`<marker id="m${c.slice(1)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker>`).join('')}</defs>`;
  ND.lines.forEach(L=>{const f=L.f[k], u=Math.abs(f)/L.fmax; let a=pos[L.i], b=pos[L.j]; if(f<0){[a,b]=[b,a];}
    const dx=b[0]-a[0], dy=b[1]-a[1], d=Math.hypot(dx,dy), ux=dx/d, uy=dy/d, pad=26;
    const x1=a[0]+ux*pad, y1=a[1]+uy*pad, x2=b[0]-ux*pad, y2=b[1]-uy*pad, c=col(u);
    s+=`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="${2+5*Math.min(u,1.2)}" marker-end="url(#m${c.slice(1)})"/>`;
    const mx=(a[0]+b[0])/2, my=(a[1]+b[1])/2;
    s+=`<g><rect x="${mx-34}" y="${my-19}" width="68" height="38" rx="6" fill="#fff" stroke="${c}" stroke-width="1.2"/>`+
       `<text x="${mx}" y="${my-5}" text-anchor="middle" font-size="10.5" font-weight="700" fill="${c==='#6B7A86'?'#1B2733':c}">${L.l} ${Math.abs(f).toFixed(0)} MW</text>`+
       `<text x="${mx}" y="${my+10}" text-anchor="middle" font-size="10.5" fill="${c==='#6B7A86'?'#1B2733':c}">(${(100*u).toFixed(0)}%)</text></g>`;});
  ND.buses.forEach(b=>{const [x,y]=pos[b.n], g=b.gens.length>0;
    s+=g?`<rect x="${x-18}" y="${y-18}" width="36" height="36" rx="5" fill="#F3A6A6" stroke="#1B2733" stroke-width="1.3"/>`
        :`<circle cx="${x}" cy="${y}" r="18" fill="#5B9BD5" stroke="#1B2733" stroke-width="1.3"/>`;
    s+=`<text x="${x}" y="${y+5}" text-anchor="middle" font-size="14" font-weight="700" fill="#1B2733">${b.n}</text>`;
    const lines=[`${b.name} · 부하 ${b.load[k].toLocaleString(undefined,{maximumFractionDigits:0})} MW`];
    if(g)lines.push(`${b.gens.join('·')} ${b.gen[k].toLocaleString(undefined,{maximumFractionDigits:0})} MW`);
    if(b.aidc.length)lines.push(`AIDC ${b.aidcP[k].toFixed(0)} MW`);
    if(b.nse[k]>0.05)lines.push(`⚠ 부하차단 ${b.nse[k].toFixed(0)} MW`);
    lines.forEach((tx,i)=>{s+=`<text x="${x}" y="${y+34+i*13}" text-anchor="middle" font-size="10.5" fill="${tx.startsWith('⚠')?'#D64545':'#5E6E7A'}" font-weight="${tx.startsWith('⚠')||tx.startsWith('AIDC')?'700':'400'}">${tx}</text>`;});});
  s+='</svg>'; document.getElementById(elId).innerHTML=s;
}
"""


def network_html(res, el="net", slider=True):
    nd = network_data(res)
    pk = nd["peak"]
    ctl = (f'<div class="ctl"><span>시간</span><input type="range" id="{el}_r" min="0" max="{len(nd["T"])-1}" value="{nd["T"].index(pk)}">'
           f'<b id="{el}_t">{pk}시</b><span class="tag">기본값 = 피크 시간</span></div>') if slider else ""
    legend = ('<div class="legend"><span><span class="dot" style="background:#F3A6A6;border:1px solid #1B2733"></span>발전 모선</span>'
              '<span><span class="dot" style="background:#5B9BD5;border-radius:50%"></span>부하 모선</span>'
              '<span><span class="dot" style="background:#6B7A86"></span>이용률 &lt;80%</span>'
              '<span><span class="dot" style="background:#E0B52E"></span>80–100%</span>'
              '<span><span class="dot" style="background:#D64545"></span>100% (혼잡)</span>'
              '<span><span class="dot" style="background:#7A1B2E"></span>&gt;100% (과부하)</span></div>')
    js = (f'const ND_{el}={json.dumps(nd, ensure_ascii=False)};netSVG(ND_{el},{pk},"{el}");'
          + (f'document.getElementById("{el}_r").addEventListener("input",e=>{{const t=ND_{el}.T[+e.target.value];'
             f'document.getElementById("{el}_t").textContent=t+"시";netSVG(ND_{el},t,"{el}");}});' if slider else ""))
    return f'<div class="net">{ctl}<div id="{el}"></div>{legend}</div>', js


def build_dashboard(res, path):
    gens, P, T = res["gens"], res["P"], list(res["P"].columns)
    col, order = gen_colors(gens), merit_order(gens)
    E = P.values.sum()
    ok = res["status"] == "optimal"
    net, has_aidc = res["network"], len(res["aidc_P"]) > 0
    stats = [
        (f"{E:,.0f}", "총 발전량 (MWh)"),
        (f"{res['cost']/E:,.2f}", "평균 발전단가 ($/MWh)"),
        (f"{res['D_total'].max():,.0f}", f"피크 수요 (MW, {res['D_total'].idxmax()}시{', AIDC 포함' if has_aidc else ''})"),
        (f"{int(res['v'].values.sum())}", "기동 횟수"),
        (f"{res['nse'].sum():,.1f}", "미공급전력 (MWh)"),
    ]
    if net:
        stats.append((f"{res['n_cong']}", "송전 혼잡 (선로·h)"))
    stats_html = "".join(f'<div class="stat"><b>{a}</b><span>{b}</span></div>' for a, b in stats)

    gs = res["gen_summary"]
    rows = ""
    for g in order:
        r = gs.loc[g]
        avg = "–" if r["평균단가($/MWh)"] is None or r["평균단가($/MWh)"] != r["평균단가($/MWh)"] else f'{r["평균단가($/MWh)"]:.2f}'
        rows += (f'<tr><td><span class="dot" style="background:{col[g]}"></span>{_esc(g)}</td><td>{int(r["모선"])}</td>'
                 f'<td><span class="role">{r["역할"]}</span></td><td>{int(r["운전시간(h)"])}</td>'
                 f'<td>{int(r["기동횟수"])}</td><td>{r["발전량(MWh)"]:,.0f}</td><td>{r["이용률(%)"]:.1f}%</td>'
                 f'<td>{r["비용($)"]:,.0f}</td><td>{avg}</td></tr>')

    # 선로 요약 표 / 계통도 / AIDC
    lrows, net_html, net_js, aidc_html = "", "", "", ""
    if net:
        for l, r_ in res["line_summary"].iterrows():
            cls = "u2" if r_["혼잡시간(h)"] > 0 else ""
            lrows += (f'<tr><td>{_esc(l)}</td><td>{int(r_["from"])} → {int(r_["to"])}</td><td>{r_["용량(MW)"]:,.0f}</td>'
                      f'<td>{r_["최대조류(MW)"]:,.0f}</td><td>{r_["최대이용률(%)"]:.0f}%</td>'
                      f'<td><span class="role {cls}" style="{"background:var(--bad);color:#fff" if cls else ""}">{int(r_["혼잡시간(h)"])}h</span></td>'
                      f'<td style="text-align:left">{_esc(r_["혼잡 시간대"]) or "–"}</td></tr>')
        net_html, net_js = network_html(res, "net")
    if has_aidc:
        arows = ""
        for a in res["aidc"].index:
            ai = res["aidc"].loc[a]
            idle = [t for t in T if int(res["aidc_x"].loc[a, t]) == 0]
            from main import _fmt_hours
            arows += (f'<tr><td>{_esc(a)}</td><td>{int(ai["bus"])} ({_esc(res["buses"].loc[int(ai["bus"]), "name"])})</td>'
                      f'<td>{ai["p_idle"]:.0f}</td><td>{ai["p_train"]:.0f}</td><td>{int(ai["train_hours"])}</td><td>{int(ai["min_block"])}</td>'
                      f'<td style="text-align:left">{_esc(_fmt_hours(idle)) or "– (평균부하)"}</td><td>{res["aidc_P"].loc[a].sum():,.0f}</td></tr>')
        mode_txt = {"average": "① 평균부하 (상수) — 언제 쓰는지 표현 불가, 수요반응 불가",
                    "step_fixed": "② 2상 고정 스케줄 (입력) — 학습/유휴 시간이 고정",
                    "step_dr": "③ 2상 + 수요반응 — 학습상태 x_d,t 를 솔버가 결정 (총 학습시간 보존)"}[res["aidc_mode"]]
        aidc_html = f"""
<section><h2>AI 데이터센터 부하 <span class="tag">{_esc(res['aidc_mode'])}</span></h2><p class="sub">{mode_txt}. 회색 막대는 기존 계통수요(우축).</p>
<div class="chart sm"><canvas id="aidc"></canvas></div>
<div class="scroll" style="margin-top:14px"><table><tr><th>AIDC</th><th>모선</th><th>유휴(MW)</th><th>학습(MW)</th><th>학습시간(h)</th><th>최소연속(h)</th><th>유휴 시간대</th><th>일 사용량(MWh)</th></tr>{arows}</table></div></section>"""

    data = {
        "T": T,
        "gens": [{"name": g, "color": col[g], "data": [round(float(x), 2) for x in P.loc[g].values]} for g in order],
        "D": [round(float(x), 2) for x in res["D_total"].values],
        "D0": [round(float(x), 2) for x in res["D"].values],
        "DR": [round(float(x), 2) for x in (res["D_total"] + res["R"]).values],
        "nse": [round(float(x), 2) for x in res["nse"].values],
        "cost": {k: round(v, 0) for k, v in res["breakdown"].items() if v > 0.5},
        "lmp": None if res["lmp"] is None else [{"name": f"모선{n} {res['buses'].loc[n,'name']}" if net else "SMP",
                                                  "data": [round(float(x), 2) for x in res["lmp"].loc[n].values]} for n in res["lmp"].index],
        "aidc": [round(float(x), 2) for x in res["aidc_P"].sum().values] if has_aidc else None,
        "aidc_avg": float(res["aidc"]["p_avg"].sum()) if has_aidc else None,
        "has_aidc": has_aidc,
    }
    notes = "".join(f"<li>{_esc(s)}</li>" for s in res["insights"])
    net_sections = "" if not net else f"""
<section><h2>송전조류 계통도</h2><p class="sub">화살표 = 조류 방향, 숫자 = 조류(MW)와 이용률, 선 색·굵기 = 이용률. 슬라이더로 시간을 바꿔 보세요.</p>{net_html}</section>
<section><h2>선로 이용률 (%)</h2><p class="sub">빨간 칸 = 용량 100% 도달(혼잡). 혼잡 시간에는 싼 발전기 대신 부하 근처 발전기가 투입됩니다(재급전).</p>{line_util_html(res)}
<div class="scroll" style="margin-top:14px"><table><tr><th>선로</th><th>from → to</th><th>용량(MW)</th><th>최대조류(MW)</th><th>최대이용률</th><th>혼잡</th><th>혼잡 시간대</th></tr>{lrows}</table></div></section>"""
    body = f"""
<header><p class="scn">시나리오 · {_esc(res['label'])} <span class="tag">{'송전제약 (DC 조류)' if net else '단일모선'}</span>{f'<span class="tag">AIDC {_esc(res["aidc_mode"])}</span>' if has_aidc else ''}</p><h1>하루 발전계획 리포트</h1>
<div class="hero"><div class="big">${res['cost']:,.0f}<small>/ 일 총 운영비용</small></div>
<div><span class="pill {'ok' if ok else 'no'}">{'최적해 (갭 ≤ 0.01%)' if ok else _esc(res['status'])}</span>
<div style="font-size:13px;color:var(--muted);margin-top:6px">변수 {res['nvars']:,}개 · 제약 {res['ncons']:,}개 · {res['seconds']:.1f}초{f' · 발전비용 ${res["gen_cost"]:,.0f} + 미공급 ${res["cost"]-res["gen_cost"]:,.0f}' if res['cost']-res['gen_cost']>0.5 else ''}</div></div></div>
<div class="stats">{stats_html}</div>{merit_strip(gens)}</header>
<section><h2>한눈에 보는 해설</h2><p class="sub">결과에서 자동으로 찾아낸 특징입니다. 발표 문장으로 그대로 써도 됩니다.</p><ul class="notes">{notes}</ul></section>
<section><h2>시간대별 발전과 수요</h2><p class="sub">싼 발전기부터 아래에 쌓았습니다. 범례를 누르면 발전기를 숨길 수 있습니다.</p>
<div class="chart"><canvas id="disp"></canvas></div></section>
<section><h2>기동정지 상태와 출력</h2><p class="sub">칸 안의 숫자는 출력(MW). 색이 진할수록 최대출력에 가깝고, 빈 칸은 정지입니다.</p>{heatmap_html(res)}</section>
{net_sections}{aidc_html}
<section class="two"><div><h2>비용 구성</h2><p class="sub">총 운영비용이 어디서 나오는지</p><div class="chart sm"><canvas id="cost"></canvas></div></div>
<div><h2>{'모선별 한계가격 (LMP)' if net else '시간대별 한계가격'}</h2><p class="sub">전기 1 MWh를 더 공급할 때 드는 비용 (기동정지 고정 LP의 수급균형 쌍대값){' — 혼잡이 생기면 모선마다 가격이 달라집니다' if net else ''}</p><div class="chart sm"><canvas id="smp"></canvas></div></div></section>
<section><h2>발전기별 성적표</h2><p class="sub">급전순위(싼 순)로 정렬</p><div class="scroll"><table>
<tr><th>발전기</th><th>모선</th><th>역할</th><th>운전(h)</th><th>기동</th><th>발전량(MWh)</th><th>이용률</th><th>비용($)</th><th>평균단가($/MWh)</th></tr>{rows}</table></div></section>
<footer>Pyomo + HiGHS · Morales-España et al. (2013) tight &amp; compact UC formulation{' · Stott et al. (2009) DC power flow' if net else ''} · 예비력 비율 {res['reserve_ratio']:.0%}{f' · S_base {res["s_base"]:.0f} MVA' if net else ''}</footer>
</div><script>{JS_COMMON}{JS_NET if net else ''}
{net_js}
const D={json.dumps(data, ensure_ascii=False)};
if(window.Chart){{
const ds=D.gens.map(g=>({{type:'bar',label:g.name,data:g.data,backgroundColor:g.color,stack:'s',borderWidth:0,order:2}}));
if(D.nse.some(x=>x>0))ds.push({{type:'bar',label:'미공급',data:D.nse,backgroundColor:css('--bad'),stack:'s',order:2}});
ds.push({{type:'line',label:D.has_aidc?'수요+AIDC':'수요',data:D.D,borderColor:css('--ink'),backgroundColor:css('--ink'),borderWidth:2.5,pointRadius:3,order:0,stack:'L1'}});
if(D.has_aidc)ds.push({{type:'line',label:'기존 수요',data:D.D0,borderColor:css('--muted'),borderDash:[2,3],borderWidth:1.5,pointRadius:0,order:1,stack:'L3'}});
ds.push({{type:'line',label:'수요+예비력',data:D.DR,borderColor:css('--muted'),borderDash:[6,4],borderWidth:1.5,pointRadius:0,order:1,stack:'L2'}});
new Chart(document.getElementById('disp'),{{data:{{labels:D.T,datasets:ds}},options:{{maintainAspectRatio:false,
interaction:{{mode:'index',intersect:false}},scales:{{x:{{stacked:true,title:{{display:true,text:'시간 (h)'}},grid:{{display:false}}}},
y:{{stacked:true,title:{{display:true,text:'MW'}}}}}},plugins:{{legend:{{position:'bottom'}},
tooltip:{{callbacks:{{label:c=>c.dataset.label+': '+c.parsed.y.toLocaleString(undefined,{{maximumFractionDigits:1}})+' MW'}}}}}}}}}});
const ck=Object.keys(D.cost),cv=Object.values(D.cost);
new Chart(document.getElementById('cost'),{{type:'doughnut',data:{{labels:ck,datasets:[{{data:cv,
backgroundColor:['#0B5563','#5FAE8E','#F0A04B','#D64545','#93A3AE'],borderColor:css('--bg'),borderWidth:3}}]}},
options:{{maintainAspectRatio:false,cutout:'62%',plugins:{{legend:{{position:'right'}},tooltip:{{callbacks:{{label:c=>c.label+': $'+c.parsed.toLocaleString()+
' ('+(100*c.parsed/cv.reduce((a,b)=>a+b,0)).toFixed(1)+'%)'}}}}}}}}}});
const LC=['#E2603F','#0B5563','#1F8A8A','#5FAE8E','#C9A227','#A62639','#6B7A86','#8E44AD'];
if(D.lmp)new Chart(document.getElementById('smp'),{{type:'line',data:{{labels:D.T,datasets:D.lmp.map((s,i)=>({{label:s.name,data:s.data,
stepped:'middle',borderColor:LC[i%LC.length],backgroundColor:D.lmp.length==1?'rgba(226,96,63,.12)':'transparent',fill:D.lmp.length==1,pointRadius:D.lmp.length==1?2:0,borderWidth:1.8}}))}},
options:{{maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:D.lmp.length>1,position:'bottom'}}}},
scales:{{x:{{title:{{display:true,text:'시간 (h)'}},grid:{{display:false}}}},y:{{title:{{display:true,text:'$/MWh'}}}}}}}}}});
if(D.aidc)new Chart(document.getElementById('aidc'),{{data:{{labels:D.T,datasets:[
{{type:'line',label:'AIDC 소비전력 (MW)',data:D.aidc,stepped:'middle',borderColor:'#E07B1A',borderWidth:2.5,pointRadius:0,yAxisID:'y',order:0}},
{{type:'line',label:'평균부하 (MW)',data:D.T.map(()=>D.aidc_avg),borderColor:css('--muted'),borderDash:[6,4],borderWidth:1.3,pointRadius:0,yAxisID:'y',order:1}},
{{type:'bar',label:'기존 계통수요 (MW, 우축)',data:D.D0,backgroundColor:css('--off'),yAxisID:'y2',order:2,barPercentage:1,categoryPercentage:1}}]}},
options:{{maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{position:'bottom'}}}},
scales:{{x:{{title:{{display:true,text:'시간 (h)'}},grid:{{display:false}}}},y:{{title:{{display:true,text:'AIDC (MW)'}},beginAtZero:true}},
y2:{{position:'right',title:{{display:true,text:'계통수요 (MW)'}},beginAtZero:true,grid:{{display:false}}}}}}}}}});
}} else {{document.querySelectorAll('canvas').forEach(c=>{{c.parentElement.style.height='auto';c.parentElement.innerHTML='<p class=sub>그래프를 보려면 인터넷 연결이 필요합니다 (Chart.js). 아래 표와 PNG 그림은 그대로 볼 수 있습니다.</p>';}});}}
</script></body></html>"""
    page = HEAD.replace("__TITLE__", _esc(f"UC 리포트 · {res['label']}")).replace("__CSS__", CSS) + body
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


def build_comparison(results, notes, path):
    """results[0] = Base. notes = 시나리오별 비교 해설(list of list)"""
    base = results[0]
    gens = base["gens"]
    col, order = gen_colors(gens), merit_order(gens)
    labels = [r["label"] for r in results]
    any_net = any(r["network"] for r in results)
    aidc_rs = [r for r in results if len(r["aidc_P"])]

    # 요약 표
    trs = ""
    for r in results:
        d = (r["cost"] - base["cost"]) / base["cost"] * 100
        cls = "up" if d > 0.005 else "down" if d < -0.005 else ""
        trs += (f"<tr><td>{_esc(r['label'])}</td><td style='text-align:left;color:var(--muted)'>{_esc(r.get('change',''))}</td>"
                f"<td>${r['cost']:,.0f}</td><td class='delta {cls}'>{'' if r is base else f'{d:+.2f}%'}</td>"
                f"<td>${r['gen_cost']:,.0f}</td><td>{r['nse'].sum():,.1f}</td>"
                + (f"<td>{r['n_cong'] if r['network'] else '–'}</td>" if any_net else "")
                + f"<td>{int(r['u'].values.sum())}</td><td>{int(r['v'].values.sum())}</td><td>{r['rshort'].sum():,.1f}</td></tr>")

    cards, net_js = "", ""
    for k, (r, ns) in enumerate(zip(results[1:], notes[1:])):
        d = (r["cost"] - base["cost"]) / base["cost"] * 100
        cls = "up" if d > 0 else "down"
        li = "".join(f"<li>{_esc(s)}</li>" for s in ns)
        extra = ""
        if r["network"]:
            nh, nj = network_html(r, f"net{k}")
            net_js += nj
            extra += f'<h4 style="margin:22px 0 6px;font-size:15px">송전조류 계통도 · 선로 이용률</h4>{nh}<div style="height:12px"></div>{line_util_html(r)}'
        tags = f'<span class="tag">{"송전제약" if r["network"] else "단일모선"}</span>'
        if len(r["aidc_P"]):
            tags += f'<span class="tag">AIDC {_esc(r["aidc_mode"])}</span>'
        cards += (f'<div class="scard"><h3>{_esc(r["label"])} <span class="delta {cls}">{d:+.2f}% '
                  f'(${r["cost"]-base["cost"]:+,.0f})</span>{tags}</h3>'
                  f'<p class="chg">{_esc(r.get("change",""))}</p><ul class="notes">{li}</ul>'
                  f'<div class="legend"><span><span class="dot" style="background:var(--good)"></span>새로 켜짐</span>'
                  f'<span><span class="dot" style="background:var(--bad)"></span>꺼짐</span>'
                  f'<span><span class="dot" style="background:var(--same)"></span>그대로 운전</span></div>'
                  f'{diff_html(base, r)}{extra}</div>')

    data = {"labels": labels, "cost": [round(r["cost"], 0) for r in results],
            "gen": [round(r["gen_cost"], 0) for r in results], "nsec": [round(r["cost"] - r["gen_cost"], 0) for r in results],
            "gens": [{"name": g, "color": col[g], "data": [round(float(r["P"].loc[g].sum()), 1) for r in results]} for g in order],
            "T": list(base["D"].index), "D0": [round(float(x), 1) for x in base["D"].values],
            "aidc": [{"name": r["label"], "data": [round(float(x), 1) for x in r["aidc_P"].sum().values]} for r in aidc_rs],
            "aidc_avg": float(aidc_rs[0]["aidc"]["p_avg"].sum()) if aidc_rs else None}
    aidc_sec = "" if not aidc_rs else """
<section><h2>AIDC 부하 패턴 비교</h2><p class="sub">세 모델 모두 일 사용량은 같지만, 수요반응은 피크·혼잡 시간을 피해 학습을 옮깁니다. 회색 막대 = 기존 계통수요(우축).</p>
<div class="chart"><canvas id="c3"></canvas></div></section>"""
    body = f"""
<header><p class="scn">시나리오 {len(results)-1}개 · Base 대비</p><h1>민감도 분석 리포트</h1>
<div class="scroll"><table><tr><th>시나리오</th><th>변경 내용</th><th>총 운영비용</th><th>Base 대비</th><th>발전비용</th><th>미공급(MWh)</th>{'<th>혼잡(선로·h)</th>' if any_net else ''}<th>운전 (기·h)</th><th>기동</th><th>예비력부족(MW·h)</th></tr>{trs}</table></div>
{merit_strip(gens)}</header>
<section class="two"><div><h2>총 운영비용</h2><p class="sub">= 발전비용 + 미공급 비용(VOLL × 부하차단량)</p><div class="chart sm"><canvas id="c1"></canvas></div></div>
<div><h2>발전기별 하루 발전량</h2><p class="sub">어떤 발전기가 일을 더 하고 덜 하게 됐는지 (재급전)</p><div class="chart sm"><canvas id="c2"></canvas></div></div></section>
{aidc_sec}
<section><h2>시나리오별 변화</h2><p class="sub">Base와 비교해서 켜지고 꺼진 칸만 색으로 표시했습니다.</p>{cards}</section>
<footer>Pyomo + HiGHS · 각 시나리오는 run_scenarios.py 의 SCENARIOS 에서 수정할 수 있습니다.</footer>
</div><script>{JS_COMMON}{JS_NET if any_net else ''}
{net_js}
const D={json.dumps(data, ensure_ascii=False)};
if(window.Chart){{
const lo=Math.min(...D.gen)*0.9;
new Chart(document.getElementById('c1'),{{type:'bar',data:{{labels:D.labels,datasets:[
{{label:'발전비용',data:D.gen,backgroundColor:D.gen.map((c,i)=>i==0?'#93A3AE':'#1F8A8A'),borderRadius:0,stack:'c'}},
{{label:'미공급 비용',data:D.nsec,backgroundColor:'#D64545',borderRadius:4,stack:'c'}}]}},
options:{{maintainAspectRatio:false,plugins:{{legend:{{position:'bottom'}},tooltip:{{callbacks:{{label:c=>c.dataset.label+': $'+c.parsed.y.toLocaleString()}}}}}},
scales:{{x:{{stacked:true,grid:{{display:false}}}},y:{{stacked:true,min:lo,ticks:{{callback:v=>'$'+(v/1000).toFixed(0)+'k'}}}}}}}}}});
new Chart(document.getElementById('c2'),{{type:'bar',data:{{labels:D.labels,datasets:D.gens.map(g=>({{label:g.name,data:g.data,backgroundColor:g.color,borderWidth:0}}))}},
options:{{maintainAspectRatio:false,plugins:{{legend:{{position:'bottom'}}}},scales:{{x:{{stacked:true,grid:{{display:false}}}},y:{{stacked:true,title:{{display:true,text:'MWh'}}}}}}}}}});
const AC=['#6B7A86','#1F4E79','#E07B1A','#2E9E6B','#8E44AD'];
if(D.aidc.length)new Chart(document.getElementById('c3'),{{data:{{labels:D.T,datasets:[
...D.aidc.map((s,i)=>({{type:'line',label:s.name,data:s.data,stepped:'middle',borderColor:AC[i%AC.length],borderWidth:2.4,pointRadius:0,yAxisID:'y',order:0}})),
{{type:'line',label:'평균부하',data:D.T.map(()=>D.aidc_avg),borderColor:css('--muted'),borderDash:[6,4],borderWidth:1.2,pointRadius:0,yAxisID:'y',order:1}},
{{type:'bar',label:'기존 계통수요 (우축)',data:D.D0,backgroundColor:css('--off'),yAxisID:'y2',order:2,barPercentage:1,categoryPercentage:1}}]}},
options:{{maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{position:'bottom'}}}},
scales:{{x:{{title:{{display:true,text:'시간 (h)'}},grid:{{display:false}}}},y:{{title:{{display:true,text:'AIDC (MW)'}},beginAtZero:true}},
y2:{{position:'right',title:{{display:true,text:'계통수요 (MW)'}},beginAtZero:true,grid:{{display:false}}}}}}}}}});
}} else {{document.querySelectorAll('canvas').forEach(c=>{{c.parentElement.style.height='auto';c.parentElement.innerHTML='<p class=sub>그래프를 보려면 인터넷 연결이 필요합니다 (Chart.js). 아래 표와 PNG 그림은 그대로 볼 수 있습니다.</p>';}});}}
</script></body></html>"""
    page = HEAD.replace("__TITLE__", "UC 시나리오 비교").replace("__CSS__", CSS) + body
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path
