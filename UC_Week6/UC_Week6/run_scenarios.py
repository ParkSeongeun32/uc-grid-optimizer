"""
⑥ run_scenarios.py : 실습 과제 시나리오를 한 번에 돌리고 비교
------------------------------------------------------------
실행:  python run_scenarios.py uc_input.xlsx              (Week5 과제 4개: 수요·예비력·연료비·최소정지)
       python run_scenarios.py uc_input_week6.xlsx        (Week6 S0~S4: 송전제약 · AIDC 평균/고정/수요반응)
       python run_scenarios.py uc_input_week6.xlsx --lab  (Week6 실습 4개: 송전용량·AIDC 위치·규모·DR 유연성)
       python run_scenarios.py uc_input_week6.xlsx --all  (S0~S4 + 실습 4개 모두)
- 엑셀 파일은 건드리지 않고, 아래 SCENARIOS 에 적힌 대로 "복사본"만 바꿔서 풉니다.
- 엑셀에 lines/aidc 시트가 있으면 Week6 세트, 없으면 Week5 세트가 자동으로 선택됩니다.
- 시나리오를 추가/수정하고 싶으면 해당 리스트에 한 줄만 추가하면 됩니다.
결과: results/compare_dashboard.html (비교 리포트) + 시나리오별 엑셀/그림/대시보드
"""
import sys, os, copy, webbrowser
import pandas as pd

from data_io import load_input, preprocess
from main import solve_uc, save_excel, _fmt_hours
from visualize import (plot_results, plot_compare_cost, plot_compare_cost_split, plot_diff, plot_aidc,
                       plot_compare_network, merit_order)
from report import build_dashboard, build_comparison


# ================= Week5 시나리오 (단일모선) =================
def demand_up(raw):            # 수요 10% 증가
    dem = raw["demand"]
    cols = [c for c in dem.columns if c == "demand_MW" or str(c).lower().startswith("bus")]
    dem[cols] = dem[cols] * 1.10

def reserve_up(raw):           # 예비력 0.05 → 0.10
    raw["settings"]["reserve_ratio"] = 0.10

def fuel_up(raw):              # G1 연료비 16.19 → 22
    raw["gens"].loc["G1", "cost_b"] = 22.0

def mindown_up(raw):           # G3·G4 최소정지시간 5 → 10
    raw["gens"].loc[["G3", "G4"], "min_down"] = 10

SCENARIOS_W5 = [
    # (파일용 이름, 화면 표시 이름, 바꾼 내용 설명, 함수)
    ("S0_Base",    "Base",            "엑셀 입력 그대로",                     None),
    ("S1_Demand",  "① 수요 +10%",     "demand_MW 를 모든 시간 10% 증가",      demand_up),
    ("S2_Reserve", "② 예비력 강화",    "reserve_ratio 0.05 → 0.10",            reserve_up),
    ("S3_Fuel",    "③ G1 연료비 상승", "G1 cost_b 16.19 → 22 $/MWh",           fuel_up),
    ("S4_MinDown", "④ G3·G4 최소정지", "G3·G4 min_down 5 → 10 h",              mindown_up),
]


# ================= Week6 시나리오 (송전제약 + AIDC) =================
def _set(network=None, aidc_mode=None):
    def f(raw):
        if network is not None:
            raw["settings"]["network"] = network
        if aidc_mode is not None:
            raw["settings"]["aidc_mode"] = aidc_mode
    return f

SCENARIOS_W6 = [
    ("S0_Single",   "S0 단일모선",     "network=0, AIDC 없음 (Week5 와 동일)",            _set(0, "none")),
    ("S1_Network",  "S1 송전제약",     "network=1 (DC 조류·선로 용량), AIDC 없음",        _set(1, "none")),
    ("S2_AvgLoad",  "S2 AIDC 평균",    "aidc_mode=average (일정 부하, 수요반응 불가)",     _set(1, "average")),
    ("S3_Fixed",    "S3 AIDC 고정",    "aidc_mode=step_fixed (학습/유휴 고정 스케줄)",     _set(1, "step_fixed")),
    ("S4_DR",       "S4 AIDC 수요반응", "aidc_mode=step_dr (학습 시간을 솔버가 결정)",     _set(1, "step_dr")),
]

# ---- 실습 4가지 (모두 S4 수요반응 모델 기준으로 한 가지씩 바꿈) ----
def lab_line(raw):             # 송전 용량: L14 500 → 400
    _set(1, "step_dr")(raw); raw["lines"].loc["L14", "f_max_MW"] = 400

def lab_bus1(raw):             # AIDC 위치: 모선 6 → 1 (발전단지 옆)
    _set(1, "step_dr")(raw); raw["aidc"]["bus"] = 1

def lab_bus4(raw):             # AIDC 위치: 모선 6 → 4 (부하 중심)
    _set(1, "step_dr")(raw); raw["aidc"]["bus"] = 4

def lab_size(raw):             # AIDC 규모: p_idle·p_train × 2
    _set(1, "step_dr")(raw); raw["aidc"][["p_idle", "p_train"]] *= 2

def lab_block(raw):            # DR 유연성: min_block 4 → 8
    _set(1, "step_dr")(raw); raw["aidc"]["min_block"] = 8

SCENARIOS_LAB = [
    ("S4_DR",       "S4 AIDC 수요반응", "기준 (network=1, step_dr)",                       _set(1, "step_dr")),
    ("L1_Line400",  "실습① L14 400MW", "L14 f_max 500 → 400 MW",                           lab_line),
    ("L2_AidcBus1", "실습② AIDC 모선1", "aidc bus 6 → 1 (발전단지 옆)",                     lab_bus1),
    ("L2_AidcBus4", "실습② AIDC 모선4", "aidc bus 6 → 4 (부하 중심)",                       lab_bus4),
    ("L3_Size2x",   "실습③ AIDC ×2",   "p_idle·p_train × 2 (60/210 MW)",                   lab_size),
    ("L4_Block8",   "실습④ 최소연속 8h", "min_block 4 → 8 h (유연성 감소)",                  lab_block),
]
# -------------------------------------------------------------------


def _blocks(hours):
    return _fmt_hours(hours)


def compare_notes(base, r):
    """Base 대비 무엇이 바뀌었는지 자동으로 문장 만들기"""
    notes = []
    d = r["cost"] - base["cost"]
    notes.append(f"총 운영비용 ${base['cost']:,.0f} → ${r['cost']:,.0f} ({d:+,.0f} $, {d/base['cost']*100:+.2f}%)")
    dg = r["gen_cost"] - base["gen_cost"]
    dn = (r["cost"] - r["gen_cost"]) - (base["cost"] - base["gen_cost"])
    if abs(dn) > 0.5:
        notes.append(f"  └ 발전비용 {dg:+,.0f} $, 미공급 비용 {dn:+,.0f} $")
    ub, us, T = base["u"], r["u"], list(base["u"].columns)
    for g in merit_order(base["gens"]):
        on = [t for t in T if us.loc[g, t] and not ub.loc[g, t]]
        off = [t for t in T if ub.loc[g, t] and not us.loc[g, t]]
        if on:
            notes.append(f"{g} 추가 운전: {_blocks(on)} (+{len(on)}h)")
        if off:
            notes.append(f"{g} 운전 중단: {_blocks(off)} (−{len(off)}h)")
    if not any(((us != ub).values).ravel()):
        notes.append("기동정지 상태는 Base와 완전히 같습니다 (출력 배분만 달라짐).")
    # 발전량 이동이 큰 발전기
    dE = (r["P"].sum(axis=1) - base["P"].sum(axis=1)).round(1)
    big = dE[dE.abs() > 1].sort_values()
    if len(big):
        parts = [f"{g} {v:+,.0f}" for g, v in big.items()]
        notes.append("하루 발전량 변화(MWh): " + ", ".join(parts)
                     + (" — 싼 발전기 대신 부하 근처 발전기로 재급전" if r["network"] and not base["network"] else ""))
    # 급전순위 변화
    mo_b, mo_s = merit_order(base["gens"]), merit_order(r["gens"])
    if mo_b != mo_s:
        notes.append("급전순위(싼 순) 변화: " + " > ".join(mo_b) + "  →  " + " > ".join(mo_s))
    # [Week6] 송전 혼잡
    if r["network"]:
        cong = r["line_summary"][r["line_summary"]["혼잡시간(h)"] > 0].sort_values("혼잡시간(h)", ascending=False)
        bc = base["n_cong"] if base["network"] else 0
        if len(cong):
            notes.append(f"송전 혼잡 {r['n_cong']} 선로·h (Base {bc}): " +
                         "; ".join(f"{l} {row['혼잡 시간대']} ({int(row['혼잡시간(h)'])}h)" for l, row in cong.iterrows()))
        else:
            notes.append("송전 혼잡 없음 (모든 선로 용량 이내)")
        if base["network"]:
            du = (r["util"].max(axis=1) - base["util"].max(axis=1)) * 100
            chg = du[du.abs() > 1].sort_values()
            if len(chg):
                notes.append("선로 최대 이용률 변화(%p): " + ", ".join(f"{l} {v:+.0f}" for l, v in chg.items()))
    # [Week6] AIDC
    if len(r["aidc_P"]):
        for a in r["aidc_P"].index:
            idle = [t for t in T if int(r["aidc_x"].loc[a, t]) == 0]
            if r["aidc_mode"] == "average":
                notes.append(f"{a}: 평균부하 {r['aidc_P'].loc[a].iloc[0]:.1f} MW 상시 소비 (피크에도 줄이지 못함)")
            else:
                tag = "고정" if r["aidc_mode"] == "step_fixed" else "수요반응"
                b_idle = ([t for t in T if int(base["aidc_x"].loc[a, t]) == 0]
                          if len(base["aidc_P"]) and a in base["aidc_x"].index and base["aidc_mode"] != "average" else None)
                moved = f" (Base 유휴 {_blocks(b_idle)})" if b_idle is not None and b_idle != idle else ""
                notes.append(f"{a}: 유휴 시간 {_blocks(idle)} [{tag}]{moved}, 일 사용량 {r['aidc_P'].loc[a].sum():,.0f} MWh")
            if r["aidc_mode"] == "step_dr":
                pk = r["D"].idxmax()
                reasons = []
                if pk in idle:
                    reasons.append(f"수요 피크({pk}시)")
                bus = int(r["aidc"].loc[a, "bus"])
                if r["network"]:
                    bl = [l for l in r["lines"].index if bus in (int(r["lines"].loc[l, "from_bus"]), int(r["lines"].loc[l, "to_bus"]))]
                    cl = sorted({l for l in bl for t in idle if r["util"].loc[l, t] >= 0.999})
                    if cl:
                        reasons.append(f"모선{bus} 인접 선로 혼잡({', '.join(cl)})")
                if r["lmp"] is not None:
                    lm = r["lmp"].loc[bus]
                    reasons.append(f"모선{bus} 한계가격 유휴시간 평균 {lm[idle].mean():.1f} vs 학습시간 {lm[[t for t in T if t not in idle]].mean():.1f} $/MWh")
                if reasons:
                    notes.append("  └ 학습을 피한 이유: " + " · ".join(reasons))
    if r["nse"].sum() > 1e-6:
        hrs = r["nse"][r["nse"] > 1e-6].index.tolist()
        where = ""
        if r["network"]:
            nb = r["nse_bus"].sum(axis=1)
            where = " @ " + ", ".join(f"모선{n} {nb[n]:,.1f} MWh" for n in nb.index if nb[n] > 1e-6)
        notes.append(f"⚠ 미공급전력(부하차단) {r['nse'].sum():,.1f} MWh 발생 ({_blocks(hrs)}){where} — 최대 {r['nse'].max():,.1f} MW")
    else:
        notes.append("미공급전력은 발생하지 않았습니다.")
    if r["rshort"].sum() > 1e-6:
        hrs = r["rshort"][r["rshort"] > 1e-6].index.tolist()
        notes.append(f"⚠ 예비력 부족 {r['rshort'].sum():,.1f} MW·h ({_blocks(hrs)}) — 설비가 모자라 예비력을 다 못 채움")
    return notes


def pick_scenarios(raw0, argv):
    week6 = raw0["lines"] is not None and raw0["aidc"] is not None
    if not week6:
        return SCENARIOS_W5, "week5"
    if "--all" in argv:
        return SCENARIOS_W6 + SCENARIOS_LAB[1:], "week6_all"
    if "--lab" in argv:
        return SCENARIOS_LAB, "week6_lab"
    return SCENARIOS_W6, "week6"


def main(path, open_browser=True, argv=()):
    raw0 = load_input(path)
    scenarios, setname = pick_scenarios(raw0, argv)
    out_dir = os.path.join("results", "scenarios")
    os.makedirs(out_dir, exist_ok=True)
    print(f"시나리오 세트: {setname} ({len(scenarios)}개)")
    results = []
    for key, label, change, fn in scenarios:
        print(f"\n===== {label} : {change} =====")
        raw = copy.deepcopy(raw0)
        if fn:
            fn(raw)
        raw["settings"]["scenario"] = key
        d = preprocess(raw)
        res = solve_uc(d, label=label)
        res["change"] = change
        print(f"  상태 {res['status']}, 비용 {res['cost']:,.0f} $ (발전 {res['gen_cost']:,.0f}), 미공급 {res['nse'].sum():.1f} MWh, "
              f"혼잡 {res['n_cong']} 선로·h, {res['seconds']:.1f}s")
        base = os.path.join(out_dir, f"result_{key}")
        save_excel(res, base + ".xlsx")
        plot_results(res, base)
        build_dashboard(res, base + "_dashboard.html")
        results.append(res)

    notes = [[]] + [compare_notes(results[0], r) for r in results[1:]]
    for r, ns in zip(results[1:], notes[1:]):
        print(f"\n[{r['label']}]")
        for s in ns:
            print("  -", s)

    plot_compare_cost(results, os.path.join("results", "compare_cost.png"))
    plot_compare_cost_split(results, os.path.join("results", "compare_cost_split.png"))
    for (key, *_), r in zip(scenarios[1:], results[1:]):
        plot_diff(results[0], r, os.path.join("results", f"compare_diff_{key}.png"))
    # [Week6] AIDC 패턴 비교 그림 / 피크 시간 계통도 나란히
    aidc_rs = [r for r in results if len(r["aidc_P"])]
    if len(aidc_rs) >= 2:
        core = [r for r in aidc_rs if r["label"].startswith("S")] or aidc_rs    # S2~S4 (모델 3종) 우선
        core = core[:4]
        plot_aidc(core[-1], os.path.join("results", "compare_aidc.png"), title="AIDC 부하 모델 비교: 평균 / 고정 스케줄 / 수요반응",
                  others=[(r["label"], r["aidc_P"].sum()) for r in core[:-1]])
        lab = [r for r in aidc_rs if not r["label"].startswith("S")]
        if lab:                                                                  # 실습 시나리오는 따로 한 장
            plot_aidc(lab[-1], os.path.join("results", "compare_aidc_lab.png"), title="AIDC 수요반응 패턴 비교: 실습 시나리오",
                      others=[(r["label"], r["aidc_P"].sum()) for r in ([core[-1]] + lab[:-1])[:6]])
    net_rs = [r for r in results if r["network"]]
    if net_rs:
        pk = int(results[0]["D"].idxmax())
        pair = [r for r in net_rs if r["label"].startswith(("S3", "S4"))]         # 강의처럼 고정 스케줄 vs 수요반응
        plot_compare_network(pair if len(pair) == 2 else net_rs[-2:], pk, os.path.join("results", "compare_network.png"))

    # 비교 요약 엑셀
    rows = [{"시나리오": r["label"], "변경 내용": r["change"], "총비용($)": round(r["cost"]),
             "Base 대비(%)": round((r["cost"] - results[0]["cost"]) / results[0]["cost"] * 100, 3),
             "발전비용($)": round(r["gen_cost"]), "미공급(MWh)": round(r["nse"].sum(), 2),
             "혼잡(선로·h)": r["n_cong"] if r["network"] else None,
             "운전(기·h)": int(r["u"].values.sum()), "기동횟수": int(r["v"].values.sum()),
             "예비력부족(MW·h)": round(r["rshort"].sum(), 2)}
            for r in results]
    with pd.ExcelWriter(os.path.join("results", "compare_summary.xlsx")) as w:
        pd.DataFrame(rows).to_excel(w, sheet_name="summary", index=False)
        pd.DataFrame({r["label"]: r["u"].sum(axis=1) for r in results}).to_excel(w, sheet_name="운전시간(h)")
        pd.DataFrame({r["label"]: r["P"].sum(axis=1).round(1) for r in results}).to_excel(w, sheet_name="발전량(MWh)")
        if net_rs:
            pd.DataFrame({r["label"]: (r["util"].max(axis=1) * 100).round(1) for r in net_rs}).to_excel(w, sheet_name="선로 최대이용률(%)")
            pd.DataFrame({r["label"]: r["line_summary"]["혼잡시간(h)"] for r in net_rs}).to_excel(w, sheet_name="혼잡시간(h)")
        if aidc_rs:
            pd.DataFrame({r["label"]: r["aidc_P"].sum().round(1) for r in aidc_rs}).to_excel(w, sheet_name="AIDC 부하(MW)")
        pd.DataFrame({"해설": [f"[{r['label']}] {s}" for r, ns in zip(results[1:], notes[1:]) for s in ns]})\
            .to_excel(w, sheet_name="자동해설", index=False)

    html = build_comparison(results, notes, os.path.join("results", "compare_dashboard.html"))
    print(f"\n비교 리포트 → {html}")
    if open_browser:
        webbrowser.open("file://" + os.path.abspath(html))
    return results, notes


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "uc_input.xlsx", open_browser="--no-open" not in sys.argv, argv=sys.argv)
