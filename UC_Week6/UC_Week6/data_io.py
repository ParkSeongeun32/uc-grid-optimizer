"""
① data_io.py : 엑셀 읽기 + 전처리
------------------------------------------------------------
- 엑셀을 읽어서 최적화 모델이 바로 쓸 수 있는 dict 형태로 바꿔준다.
- 모델(uc_model.py)은 엑셀 형식을 전혀 몰라도 된다 → "입력 ↔ 모델 분리"
- 엑셀 값만 바꾸면 코드를 고치지 않아도 결과가 바뀐다.

[Week5 엑셀]  generators / demand(demand_MW) / settings            → 단일모선 UC
[Week6 엑셀]  + generators.bus 열, demand(bus1..busN 열),
              + buses / lines / aidc 시트, settings(s_base, network, aidc_mode)
              → 송전제약(DC 조류) + AI 데이터센터 수요반응 UC
두 형식 모두 이 파일 하나로 읽는다 (없는 시트·열은 기본값으로 채움).
"""
import pandas as pd

# generators 시트에 꼭 있어야 하는 열 이름
REQUIRED_GEN_COLS = [
    "name", "p_min", "p_max", "cost_a", "cost_b", "cost_c",
    "startup_cost", "shutdown_cost", "min_up", "min_down",
    "ramp_up", "ramp_down", "startup_cap", "shutdown_cap",
]
# 있으면 쓰고 없으면 "1시 상태를 모델이 결정"(Week6 방식)
INIT_COLS = ["init_status_h", "init_p"]

# settings 시트에 값이 없을 때 쓰는 기본값
DEFAULT_SETTINGS = {
    "scenario": "Base",       # 결과 파일 이름에 사용
    "reserve_ratio": 0.05,    # 예비력 = 수요 x 비율
    "voll": 1000.0,           # 미공급전력 비용 $/MWh
    "n_seg": 1,               # 2차 비용 구간선형화 구간 수
    "s_base": 100.0,          # [Week6] 기준용량 (MVA) : 1 pu = 100 MW
    "network": 0,             # [Week6] 1: 송전제약(DC 조류) 고려, 0: 단일모선
    "aidc_mode": "none",      # [Week6] none / average / step_fixed / step_dr
}
AIDC_MODES = ["none", "average", "step_fixed", "step_dr"]


def _read_opt(xls, sheet):
    """선택 시트: 없으면 None"""
    return pd.read_excel(xls, sheet) if sheet in xls.sheet_names else None


def load_input(path):
    """엑셀 시트를 읽어 dict로 반환 (Week5 3시트 / Week6 6시트 모두 지원)"""
    xls = pd.ExcelFile(path)
    for sh in ["generators", "demand", "settings"]:
        if sh not in xls.sheet_names:
            raise ValueError(f"[입력 오류] 엑셀에 '{sh}' 시트가 없습니다. (현재 시트: {xls.sheet_names})")

    # ---- generators ----
    gens = pd.read_excel(xls, "generators")
    gens.columns = [str(c).strip() for c in gens.columns]
    missing = [c for c in REQUIRED_GEN_COLS if c not in gens.columns]
    if missing:
        raise ValueError(f"[입력 오류] generators 시트에 열이 없습니다: {missing}")
    gens = gens.dropna(subset=["name"])
    gens["name"] = gens["name"].astype(str).str.strip()
    gens = gens.set_index("name")

    # ---- demand : demand_MW 1열(Week5) 또는 bus1, bus2, ... 열(Week6) ----
    demand = pd.read_excel(xls, "demand").dropna(subset=["hour"])
    demand.columns = [str(c).strip() for c in demand.columns]
    demand["hour"] = demand["hour"].astype(int)
    demand = demand.set_index("hour").sort_index()

    # ---- settings ----
    st = pd.read_excel(xls, "settings").dropna(subset=["key"])
    settings = dict(DEFAULT_SETTINGS)
    for _, row in st.iterrows():
        settings[str(row["key"]).strip()] = row["value"]

    # ---- [Week6] buses / lines / aidc (없으면 None) ----
    buses = _read_opt(xls, "buses")
    if buses is not None:
        buses = buses.dropna(subset=["bus"])
        buses["bus"] = buses["bus"].astype(int)
        buses = buses.set_index("bus")
    lines = _read_opt(xls, "lines")
    if lines is not None:
        lines = lines.dropna(subset=["line"])
        lines["line"] = lines["line"].astype(str).str.strip()
        lines = lines.set_index("line")
    aidc = _read_opt(xls, "aidc")
    if aidc is not None:
        aidc = aidc.dropna(subset=["name"])
        aidc["name"] = aidc["name"].astype(str).str.strip()
        aidc = aidc.set_index("name")

    return {"gens": gens, "demand": demand, "settings": settings,
            "buses": buses, "lines": lines, "aidc": aidc}


def _parse_hours(s):
    """'3,4,5,6,7' → [3,4,5,6,7]  (빈 칸이면 [])"""
    if s is None or (isinstance(s, float) and s != s):
        return []
    return [int(float(h)) for h in str(s).replace(";", ",").split(",") if str(h).strip()]


def preprocess(raw):
    """모델 파라미터 계산: 수요, 예비력 요구량, 초기조건, [Week6] 모선·선로·AIDC"""
    gens, st = raw["gens"].copy(), raw["settings"]
    num_cols = [c for c in REQUIRED_GEN_COLS if c != "name"]
    gens[num_cols] = gens[num_cols].astype(float)

    T = list(raw["demand"].index)                      # 시간 집합 [1..24]
    dem = raw["demand"]
    network = int(float(st["network"]))
    s_base = float(st["s_base"])
    aidc_mode = str(st["aidc_mode"]).strip().lower()
    if aidc_mode not in AIDC_MODES:
        raise ValueError(f"[입력 오류] aidc_mode 는 {AIDC_MODES} 중 하나여야 합니다: {aidc_mode}")

    # ---- 모선 집합 N 과 모선별 수요 D_n,t ----
    bus_cols = [c for c in dem.columns if c.lower().startswith("bus")]
    if bus_cols:                                       # Week6: 모선별 수요 열
        N = [int(c[3:]) for c in bus_cols]
        Dn = {(n, t): float(dem.at[t, c]) for n, c in zip(N, bus_cols) for t in T}
        D = dem[bus_cols].astype(float).sum(axis=1)    # 계통 전체 수요 D_t = Σ_n D_n,t
    else:                                              # Week5: 단일 수요 열
        if "demand_MW" not in dem.columns:
            raise ValueError("[입력 오류] demand 시트에 demand_MW 또는 bus1, bus2, ... 열이 필요합니다.")
        N = [1]
        D = dem["demand_MW"].astype(float)
        Dn = {(1, t): float(D[t]) for t in T}
    D.name = "demand_MW"
    R = D * float(st["reserve_ratio"])                 # 예비력 요구량 (MW), 계통 전체 (식 5 그대로)

    # ---- 발전기 접속 모선 (열이 없으면 모두 모선 1) ----
    if "bus" in gens.columns:
        gens["bus"] = gens["bus"].fillna(N[0]).astype(int)
    else:
        gens["bus"] = N[0]

    # ---- 모선 정보 / 선로 ----
    buses = raw["buses"]
    if buses is None:
        buses = pd.DataFrame({"name": [f"모선{n}" for n in N], "x": range(len(N)), "y": 0}, index=N)
    buses = buses.reindex(N)
    buses["name"] = buses["name"].fillna(pd.Series({n: f"모선{n}" for n in N}))
    lines = raw["lines"]
    if network and (lines is None or len(lines) == 0):
        raise ValueError("[입력 오류] network=1 이면 lines 시트(line, from_bus, to_bus, x_pu, f_max_MW)가 필요합니다.")
    if lines is None:
        lines = pd.DataFrame(columns=["from_bus", "to_bus", "x_pu", "f_max_MW"])
    else:
        lines = lines.copy()
        lines[["from_bus", "to_bus"]] = lines[["from_bus", "to_bus"]].astype(int)
        lines[["x_pu", "f_max_MW"]] = lines[["x_pu", "f_max_MW"]].astype(float)
        bad = lines[(~lines["from_bus"].isin(N)) | (~lines["to_bus"].isin(N))].index.tolist()
        if bad:
            raise ValueError(f"[입력 오류] lines 시트의 모선 번호가 demand 시트 모선과 맞지 않습니다: {bad}")

    # ---- AIDC (AI 데이터센터) ----
    aidc = raw["aidc"]
    if aidc_mode != "none" and (aidc is None or len(aidc) == 0):
        raise ValueError("[입력 오류] aidc_mode 가 none 이 아니면 aidc 시트가 필요합니다.")
    if aidc is None or aidc_mode == "none":
        aidc = pd.DataFrame(columns=["bus", "p_idle", "p_train", "train_hours", "min_block", "fixed_idle_hours"])
    else:
        aidc = aidc.copy()
        for c in ["bus", "train_hours", "min_block"]:
            aidc[c] = aidc[c].astype(float).round().astype(int)
        aidc[["p_idle", "p_train"]] = aidc[["p_idle", "p_train"]].astype(float)
        if (aidc["train_hours"] > len(T)).any():
            raise ValueError("[입력 오류] aidc.train_hours 가 계획 기간보다 큽니다.")
    # 평균부하 = 유휴 + (학습시간/전체시간) x (학습 - 유휴)   … 식 (17) 평균 모델
    aidc["p_avg"] = aidc["p_idle"] + aidc["train_hours"] / len(T) * (aidc["p_train"] - aidc["p_idle"])
    fixed_x = {}                                       # 고정 스케줄의 학습상태 x (1: 학습, 0: 유휴)
    for a in aidc.index:
        idle = set(_parse_hours(aidc.at[a, "fixed_idle_hours"]))
        for t in T:
            fixed_x[a, t] = 0 if t in idle else 1
        if aidc_mode == "step_fixed":
            n_train = sum(fixed_x[a, t] for t in T)
            if n_train != int(aidc.at[a, "train_hours"]):
                print(f"[경고] {a}: fixed_idle_hours 로 계산한 학습시간 {n_train}h 가 train_hours {int(aidc.at[a,'train_hours'])}h 와 다릅니다 "
                      f"(고정 스케줄은 fixed_idle_hours 를 따릅니다)")

    # ---- 초기조건 (Morales-España 2013, Appendix A) ----
    free_init = not all(c in gens.columns for c in INIT_COLS) or gens[INIT_COLS].isna().all().all()
    if free_init:                                      # [Week6] 초기조건 없음 → 1시 상태는 모델이 결정
        gens["u0"], gens["TU_R"], gens["TD_R"], gens["p0"] = 0, 0.0, 0.0, 0.0
    else:
        gens[INIT_COLS] = gens[INIT_COLS].astype(float)
        s0 = gens["init_status_h"]                     # +: 운전 h, -: 정지 h
        gens["u0"] = (s0 > 0).astype(int)              # 직전 운전상태
        TU0, TD0 = s0.clip(lower=0), (-s0).clip(lower=0)
        gens["TU_R"] = ((gens["min_up"] - TU0) * gens["u0"]).clip(lower=0)        # 반드시 더 켜둬야 할 시간
        gens["TD_R"] = ((gens["min_down"] - TD0) * (1 - gens["u0"])).clip(lower=0)  # 반드시 더 꺼둬야 할 시간
        gens["p0"] = (gens["init_p"] - gens["p_min"] * gens["u0"]).clip(lower=0)   # 직전 최소출력 초과분

    # ---- 데이터 점검 (실수로 잘못 넣은 값 잡아주기) ----
    warnings = []
    bad = gens[gens["p_min"] > gens["p_max"]].index.tolist()
    if bad:
        raise ValueError(f"[입력 오류] p_min > p_max 인 발전기: {bad}")
    if (D < 0).any():
        raise ValueError("[입력 오류] 수요에 음수가 있습니다.")
    if not gens["bus"].isin(N).all():
        raise ValueError(f"[입력 오류] generators.bus 에 demand 시트에 없는 모선이 있습니다: {sorted(set(gens['bus']) - set(N))}")
    if len(aidc) and not aidc["bus"].isin(N).all():
        raise ValueError(f"[입력 오류] aidc.bus 에 없는 모선이 있습니다: {sorted(set(aidc['bus']) - set(N))}")
    total_load_peak = (D + R).max() + (aidc["p_avg"].sum() if len(aidc) else 0)
    if total_load_peak > gens["p_max"].sum():
        warnings.append(f"최대 수요+예비력({total_load_peak:,.0f} MW)이 총 설비용량({gens['p_max'].sum():,.0f} MW)보다 큽니다 → 미공급/예비력 부족 가능")
    if network:
        for n in N:                                    # 선로가 하나도 안 붙은 모선 (고립)
            if not ((lines["from_bus"] == n) | (lines["to_bus"] == n)).any() and len(N) > 1:
                warnings.append(f"모선 {n} 에 연결된 선로가 없습니다 (고립 모선) → 해당 모선 수요는 미공급 처리됨")
    for w in warnings:
        print("[경고]", w)

    return {
        "G": list(gens.index), "T": T, "N": N, "L": list(lines.index), "A": list(aidc.index),
        "gens": gens, "buses": buses, "lines": lines, "aidc": aidc,
        "D": D.to_dict(), "Dn": Dn, "R": R.to_dict(), "fixed_x": fixed_x,
        "voll": float(st["voll"]), "n_seg": int(st["n_seg"]),
        "reserve_ratio": float(st["reserve_ratio"]),
        "s_base": s_base, "network": network, "aidc_mode": aidc_mode, "free_init": free_init,
        "scenario": str(st["scenario"]), "warnings": warnings,
    }
