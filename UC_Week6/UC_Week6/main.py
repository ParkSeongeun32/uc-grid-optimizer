"""
③ main.py : 입력 → 모델 → 솔버 → 결과 정리 → 저장(엑셀/그림/대시보드)
------------------------------------------------------------
실행:  python main.py uc_input.xlsx            (Week5 단일모선)
       python main.py uc_input_week6.xlsx      (Week6 송전제약 + AIDC)
       python main.py uc_input.xlsx --no-open  (브라우저 자동열기 끄기)
엑셀 값만 바꾸고 다시 실행하면 결과가 자동으로 바뀝니다.
"""
import sys, time, os, webbrowser
import pandas as pd
import pyomo.environ as pyo

from data_io import load_input, preprocess
from uc_model import build_uc_model

MIP_GAP = 1e-4        # 최적성 갭 0.01 %
TIME_LIMIT = 300      # 최대 풀이시간(초)
CONGEST = 0.999       # 선로 이용률이 이 값 이상이면 "혼잡"으로 셈


def _solve(model):
    solver = pyo.SolverFactory("appsi_highs")     # 이름만 바꾸면 솔버 교체 가능
    solver.config.mip_gap = MIP_GAP
    solver.config.time_limit = TIME_LIMIT
    try:
        res = solver.solve(model)               # 최적해를 찾으면 변수에 값이 자동으로 들어감
        return str(res.solver.termination_condition)
    except Exception as e:                      # infeasible 등으로 해를 못 불러온 경우
        print("[알림] 솔버 메시지:", str(e).splitlines()[0][:120])
        return "infeasible"


def _blocks(row, value):
    """[1,1,0,0,1] 같은 행에서 value가 연속된 구간 → [(시작, 끝), ...]"""
    out, start, T = [], None, list(row.index)
    for i, t in enumerate(T):
        if row[t] == value and start is None:
            start = t
        if start is not None and (row[t] != value or i == len(T) - 1):
            end = t if row[t] == value else T[i - 1]
            out.append((start, end))
            start = None
    return out


def _fmt_blocks(bl):
    return ", ".join(f"{a}시" if a == b else f"{a}–{b}시" for a, b in bl)


def _fmt_hours(hours):
    """[3,4,5,10] → '3–5시, 10시'"""
    hours = sorted(hours)
    if not hours:
        return ""
    s = pd.Series(1, index=hours).reindex(range(hours[0], hours[-1] + 1), fill_value=0)
    return _fmt_blocks(_blocks(s, 1))


def compute_lmp(model, d):
    """기동정지(u,v,w)와 AIDC 학습상태(x,y)를 고정한 LP의 수급균형 쌍대값
       = 시간대별(모선별) 한계가격.  단일모선이면 SMP, 송전제약이면 모선별 LMP."""
    try:
        m = model.clone()
        for var in (m.u, m.v, m.w, m.x, m.y):
            for i in var:
                val = round(pyo.value(var[i]))
                var[i].domain = pyo.Reals
                var[i].fix(val)
        m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
        s = pyo.SolverFactory("appsi_highs")
        r = s.solve(m)
        if str(r.solver.termination_condition) != "optimal":
            return None
        if d["network"]:
            return pd.DataFrame([[abs(m.dual[m.balance[n, t]]) for t in d["T"]] for n in d["N"]],
                                index=d["N"], columns=d["T"])          # 모선 x 시간
        n0 = d["N"][0]
        return pd.DataFrame([[abs(m.dual[m.balance[t]]) for t in d["T"]]], index=[n0], columns=d["T"])
    except Exception as e:  # 한계가격은 부가 기능 → 실패해도 전체 결과는 정상 출력
        print("[참고] 한계가격 계산 생략:", e)
        return None


def solve_uc(d, label=None):
    """전처리된 데이터 d를 받아 UC를 풀고 결과 dict를 반환"""
    label = label or d["scenario"]
    model = build_uc_model(d)
    nv, nc = model.nvariables(), model.nconstraints()
    t0 = time.time()
    cond = _solve(model)
    reserve_short_used = False
    if cond not in ("optimal", "maxTimeLimit"):
        # 예비력을 도저히 못 맞추는 경우 → 예비력 부족을 허용(패널티)하고 다시 풀기
        print(f"[알림] '{label}' 기본 모델 풀이 실패({cond}) → 예비력 부족 허용 모드로 재시도")
        model = build_uc_model(d, allow_reserve_short=True)
        cond = _solve(model)
        reserve_short_used = True
        if cond not in ("optimal", "maxTimeLimit"):
            raise RuntimeError(f"솔버가 해를 찾지 못했습니다: {cond}")
    sec = time.time() - t0

    G, T, N, L, A, gens = d["G"], d["T"], d["N"], d["L"], d["A"], d["gens"]
    val = lambda var, rows: pd.DataFrame([[pyo.value(var[i, t]) for t in T] for i in rows], index=rows, columns=T)
    u = val(model.u, G).round().astype(int)                        # 기동정지 상태
    P = (u.mul(gens["p_min"], axis=0) + val(model.p, G)).clip(lower=0)   # 실제 출력 (MW)
    r = val(model.r, G).clip(lower=0)
    v = val(model.v, G).round().astype(int)
    nse_bus = val(model.nse, N).clip(lower=0)                      # 모선별 미공급 (MW)
    nse = nse_bus.sum()                                            # 계통 전체 미공급 (MW)
    rshort = pd.Series({t: max(0.0, pyo.value(model.rshort[t])) for t in T})
    D, R = pd.Series(d["D"]), pd.Series(d["R"])

    # ---- [Week6] 선로조류·이용률, 모선별 수요, AIDC ----
    flow = val(model.f, L) if L else pd.DataFrame(columns=T)       # MW (+: from→to)
    fmax = d["lines"]["f_max_MW"] if L else pd.Series(dtype=float)
    util = flow.abs().div(fmax, axis=0) if L else pd.DataFrame(columns=T)   # 0~1
    Dn = pd.DataFrame([[d["Dn"][n, t] for t in T] for n in N], index=N, columns=T)
    aidc_P = pd.DataFrame([[pyo.value(model.P_aidc[a, t]) for t in T] for a in A], index=A, columns=T)
    aidc_x = (pd.DataFrame([[d["fixed_x"][a, t] if d["aidc_mode"] == "step_fixed" else
                             (round(pyo.value(model.x[a, t])) if d["aidc_mode"] == "step_dr" else 1)
                             for t in T] for a in A], index=A, columns=T).astype(int)
              if A else pd.DataFrame(columns=T))
    bus_load = Dn.copy()
    for a in A:
        bus_load.loc[int(d["aidc"].loc[a, "bus"])] += aidc_P.loc[a]
    D_total = bus_load.sum()                                       # 수요 + AIDC (MW)
    n_cong = int((util >= CONGEST).values.sum()) if L else 0       # 혼잡 (선로·h)

    # 수급균형 검증: 수요(+AIDC) = 발전량 + 미공급전력
    check = pd.DataFrame({"demand": D, "aidc": aidc_P.sum() if A else 0.0, "generation": P.sum(), "nse": nse,
                          "reserve_req": R, "reserve": r.sum(), "reserve_short": rshort})
    check["mismatch"] = check["demand"] + check["aidc"] - check["generation"] - check["nse"]

    # 비용 분해
    A_, F, K = model._A, model._F, list(model.K)
    noload = sum(A_[g] * u.loc[g, t] for g in G for t in T)
    energy = sum(F[g, k] * pyo.value(model.dl[g, k, t]) for g in G for k in K for t in T)
    start = sum(gens.loc[g, "startup_cost"] * v.loc[g, t] for g in G for t in T)
    wv = val(model.w, G).round()
    shut = sum(gens.loc[g, "shutdown_cost"] * wv.loc[g, t] for g in G for t in T)
    nsec = d["voll"] * nse.sum()
    rsc = d["voll"] * 0.5 * rshort.sum()
    breakdown = {"무부하비용": noload, "연료비(출력)": energy, "기동비용": start + shut,
                 "미공급 비용": nsec, "예비력 부족 패널티": rsc}
    gen_cost = noload + energy + start + shut                      # 발전비용 (미공급 제외)

    # 발전기별 요약
    rows = []
    nT = len(T)
    for g in G:
        hrs = int(u.loc[g].sum())
        e = float(P.loc[g].sum())
        gcost = (sum(A_[g] * u.loc[g, t] for t in T)
                 + sum(F[g, k] * pyo.value(model.dl[g, k, t]) for k in K for t in T)
                 + gens.loc[g, "startup_cost"] * v.loc[g].sum())
        role = ("미운전" if hrs == 0 else "기저" if hrs == nT else
                "중간" if hrs >= nT * 0.5 else "첨두")
        rows.append({"발전기": g, "모선": int(gens.loc[g, "bus"]), "역할": role, "운전시간(h)": hrs,
                     "기동횟수": int(v.loc[g].sum()), "발전량(MWh)": round(e, 1),
                     "이용률(%)": round(100 * e / (gens.loc[g, "p_max"] * nT), 1),
                     "비용($)": round(gcost, 0),
                     "평균단가($/MWh)": round(gcost / e, 2) if e > 0 else None})
    gsum = pd.DataFrame(rows).set_index("발전기")

    # 선로별 요약
    lrows = []
    for l in L:
        hrs = [t for t in T if util.loc[l, t] >= CONGEST]
        lrows.append({"선로": l, "from": int(d["lines"].loc[l, "from_bus"]), "to": int(d["lines"].loc[l, "to_bus"]),
                      "용량(MW)": fmax[l], "최대조류(MW)": round(flow.loc[l].abs().max(), 1),
                      "최대이용률(%)": round(100 * util.loc[l].max(), 1), "혼잡시간(h)": len(hrs),
                      "혼잡 시간대": _fmt_hours(hrs)})
    lsum = pd.DataFrame(lrows).set_index("선로") if L else pd.DataFrame()

    lmp = compute_lmp(model, d)
    smp = lmp.loc[N[0]] if (lmp is not None and not d["network"]) else None   # 단일모선: 계통 SMP

    # 자동 해설 (발표 때 그대로 쓰기 좋게)
    ins = []
    base = gsum.index[gsum["역할"] == "기저"].tolist()
    if base:
        ins.append(f"{', '.join(base)} 은(는) 24시간 내내 운전합니다 (기저 역할 — 끄고 다시 켜는 것보다 계속 켜두는 편이 쌈).")
    for g in G:
        hrs = int(u.loc[g].sum())
        if 0 < hrs < nT:
            on, off = _blocks(u.loc[g], 1), _blocks(u.loc[g], 0)
            mid_off = [(a, b) for a, b in off if a != T[0] and b != T[-1]]
            if mid_off and hrs >= nT * 0.5:
                ins.append(f"{g} 은(는) {_fmt_blocks(mid_off)}에 잠시 정지했다가 다시 기동합니다 "
                           f"(최소정지시간 {int(gens.loc[g,'min_down'])}h).")
            elif hrs < nT * 0.5:
                ins.append(f"{g} 은(는) {_fmt_blocks(on)}에만 운전하는 첨두 발전기입니다.")
    off_all = gsum.index[gsum["역할"] == "미운전"].tolist()
    if off_all:
        ins.append(f"{', '.join(off_all)} 은(는) 하루 동안 한 번도 켜지지 않았습니다.")
    pk = D_total.idxmax()
    ins.append(f"수요 피크는 {pk}시 {D_total[pk]:,.0f} MW{'(AIDC 포함)' if A else ''}이며, 이때 {int(u[pk].sum())}기가 운전합니다.")
    if nse.sum() > 1e-6:
        hrs = nse[nse > 1e-6].index.tolist()
        where = ""
        if d["network"]:
            nb = nse_bus.sum(axis=1)
            where = " — 모선 " + ", ".join(f"{n}({d['buses'].loc[n,'name']}) {nb[n]:,.1f} MWh" for n in N if nb[n] > 1e-6)
        ins.append(f"⚠ 미공급전력(부하차단) 발생: {nse.sum():,.1f} MWh ({_fmt_hours(hrs)}){where}.")
    else:
        ins.append("모든 시간대에 수요를 100% 공급했습니다 (미공급전력 0 MW).")
    if rshort.sum() > 1e-6:
        ins.append(f"⚠ 예비력 부족: 총 {rshort.sum():,.1f} MW·h — 예비력 요구량을 다 채우지 못했습니다.")
    # [Week6] 송전 혼잡 해설
    if d["network"]:
        cong = lsum[lsum["혼잡시간(h)"] > 0].sort_values("혼잡시간(h)", ascending=False)
        if len(cong):
            parts = [f"{l}(모선{int(r_['from'])}→{int(r_['to'])}) {r_['혼잡 시간대']} {int(r_['혼잡시간(h)'])}h" for l, r_ in cong.iterrows()]
            ins.append(f"송전 혼잡(이용률 100%) 선로: {'; '.join(parts)} — 총 {n_cong} 선로·h.")
            ins.append("혼잡 = 싼 전력을 보낼 선로가 막혀 부하 근처의 비싼 발전기를 더 돌려야 함 → 운영비용 증가(재급전).")
        else:
            ins.append("송전제약을 고려했지만 용량에 도달한 선로는 없습니다 (혼잡 없음).")
        hot = util.max(axis=1).sort_values(ascending=False)
        ins.append("선로 최대 이용률: " + ", ".join(f"{l} {100*hot[l]:.0f}%" for l in hot.index[:4]) + ".")
    # [Week6] AIDC 해설
    if A:
        for a in A:
            ai = d["aidc"].loc[a]
            bn = f"모선 {int(ai['bus'])}({d['buses'].loc[int(ai['bus']),'name']})"
            e = aidc_P.loc[a].sum()
            if d["aidc_mode"] == "average":
                ins.append(f"{a}: {bn}에 평균부하 {ai['p_avg']:.1f} MW 를 24시간 일정하게 소비합니다 (일 사용량 {e:,.0f} MWh). "
                           f"피크 시간에도 줄이지 못하므로 수요반응 효과가 없습니다.")
            else:
                idle = [t for t in T if aidc_x.loc[a, t] == 0]
                how = "고정 스케줄(입력)" if d["aidc_mode"] == "step_fixed" else "수요반응(솔버가 결정)"
                ins.append(f"{a}: {bn}, 학습 {ai['p_train']:.0f} MW / 유휴 {ai['p_idle']:.0f} MW, "
                           f"유휴 시간 {_fmt_hours(idle)} ({len(idle)}h) — {how}, 일 사용량 {e:,.0f} MWh.")
                if d["aidc_mode"] == "step_dr":
                    why = []
                    top = D.sort_values(ascending=False).index[:len(idle)].tolist()
                    if set(idle) & set(top):
                        why.append("수요 피크")
                    if d["network"] and L:
                        bus_lines = [l for l in L if int(ai["bus"]) in (int(d["lines"].loc[l, "from_bus"]), int(d["lines"].loc[l, "to_bus"]))]
                        if any(util.loc[l, t] >= CONGEST for l in bus_lines for t in idle):
                            why.append(f"{bn} 유입 선로 혼잡")
                    if lmp is not None:
                        lm = lmp.loc[int(ai["bus"])]
                        if lm[idle].mean() > lm.mean():
                            why.append("한계가격이 높은 시간")
                    if why:
                        ins.append(f"→ 학습을 피한 시간대는 {' + '.join(why)}과 겹칩니다: 비싸고 혼잡한 시간을 피해 학습을 옮긴 것이 수요반응의 효과입니다.")
    if lmp is not None:
        if d["network"]:
            spread = (lmp.max(axis=0) - lmp.min(axis=0))
            tmax = spread.idxmax()
            hi, lo = lmp[tmax].idxmax(), lmp[tmax].idxmin()
            ins.append(f"모선별 한계가격(LMP)은 {lmp.values.min():.2f} ~ {lmp.values.max():.2f} $/MWh. "
                       f"모선 간 가격차가 가장 큰 시간은 {tmax}시 (모선{hi} {lmp.loc[hi,tmax]:.1f} vs 모선{lo} {lmp.loc[lo,tmax]:.1f} $/MWh)"
                       f"{' — 혼잡이 없으면 모든 모선 가격이 같습니다.' if spread.max() < 0.01 else ' — 혼잡 때문에 모선마다 가격이 갈립니다.'}")
        else:
            ins.append(f"한계가격(SMP 근사)은 {smp.min():.2f} ~ {smp.max():.2f} $/MWh, 최고는 {smp.idxmax()}시입니다.")

    out = {"label": label, "scenario": d["scenario"], "status": cond, "seconds": sec,
           "nvars": nv, "ncons": nc, "cost": pyo.value(model.obj), "gen_cost": gen_cost,
           "u": u, "P": P, "r": r, "v": v, "nse": nse, "nse_bus": nse_bus, "rshort": rshort,
           "D": D, "R": R, "D_total": D_total, "Dn": Dn, "bus_load": bus_load, "check": check,
           "breakdown": breakdown, "gen_summary": gsum, "line_summary": lsum,
           "flow": flow, "util": util, "n_cong": n_cong, "lmp": lmp, "smp": smp,
           "aidc_P": aidc_P, "aidc_x": aidc_x, "insights": ins,
           "gens": gens, "buses": d["buses"], "lines": d["lines"], "aidc": d["aidc"],
           "network": d["network"], "aidc_mode": d["aidc_mode"], "s_base": d["s_base"],
           "reserve_ratio": d["reserve_ratio"], "reserve_short_mode": reserve_short_used}
    return out


def save_excel(res, path):
    """결과 엑셀: 요약 / 기동정지 / 출력 / 수급검증 / 발전기요약 / [Week6] 선로조류·이용률·LMP·AIDC"""
    items = [("시나리오", res["label"]), ("풀이 상태", res["status"]),
             ("송전제약", "고려(DC 조류)" if res["network"] else "단일모선"), ("AIDC 모델", res["aidc_mode"]),
             ("총 운영비용($)", round(res["cost"], 0)), ("발전비용($)", round(res["gen_cost"], 0)),
             ("풀이시간(s)", round(res["seconds"], 2)), ("총 발전량(MWh)", round(res["P"].values.sum(), 1)),
             ("미공급전력(MWh)", round(res["nse"].sum(), 2)), ("혼잡(선로·h)", res["n_cong"]),
             ("총 기동횟수", int(res["v"].values.sum())),
             ("평균 발전단가($/MWh)", round(res["cost"] / max(res["P"].values.sum(), 1e-9), 2))]
    summary = pd.DataFrame(items, columns=["항목", "값"])
    with pd.ExcelWriter(path) as w:
        summary.to_excel(w, sheet_name="summary", index=False)
        res["u"].to_excel(w, sheet_name="commitment_u")
        res["P"].round(2).to_excel(w, sheet_name="power_MW")
        res["check"].round(2).to_excel(w, sheet_name="balance_check")
        res["gen_summary"].to_excel(w, sheet_name="generator_summary")
        pd.DataFrame(list(res["breakdown"].items()), columns=["비용 항목", "$"]).round(0)\
            .to_excel(w, sheet_name="cost_breakdown", index=False)
        if res["network"]:
            res["flow"].round(2).to_excel(w, sheet_name="line_flow_MW")
            (res["util"] * 100).round(1).to_excel(w, sheet_name="line_util_pct")
            res["line_summary"].to_excel(w, sheet_name="line_summary")
            res["nse_bus"].round(2).to_excel(w, sheet_name="nse_bus_MW")
            res["bus_load"].round(2).to_excel(w, sheet_name="bus_load_MW")
        if len(res["aidc_P"]):
            pd.concat({"P_MW": res["aidc_P"].round(2), "x_train": res["aidc_x"]}).to_excel(w, sheet_name="aidc")
        if res["lmp"] is not None:
            res["lmp"].round(2).to_excel(w, sheet_name="lmp" if res["network"] else "smp")


def print_report(res):
    print(f"변수 {res['nvars']}개, 제약 {res['ncons']}개")
    print(f"풀이 상태: {res['status']}, 시간 {res['seconds']:.1f}s")
    print(f"총 운영비용: {res['cost']:,.0f} $  (발전비용 {res['gen_cost']:,.0f} $ + 미공급 {res['breakdown']['미공급 비용']:,.0f} $)")
    print("수급 불일치 최대값(MW):", round(res["check"]["mismatch"].abs().max(), 6))
    if res["network"]:
        print(f"혼잡: {res['n_cong']} 선로·h, 미공급: {res['nse'].sum():,.1f} MWh")
    print("\n[자동 해설]")
    for s in res["insights"]:
        print(" -", s)


def run(path, open_browser=True, outdir="results"):
    from visualize import plot_results
    from report import build_dashboard
    data = preprocess(load_input(path))
    res = solve_uc(data)
    print_report(res)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"result_{data['scenario']}")
    save_excel(res, out + ".xlsx")
    plot_results(res, out)
    html = build_dashboard(res, out + "_dashboard.html")
    print(f"\n저장 완료 → {out}.xlsx / {out}_*.png / {html}")
    if open_browser:
        webbrowser.open("file://" + os.path.abspath(html))
    return res


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args[0] if args else "uc_input.xlsx", open_browser="--no-open" not in sys.argv)
