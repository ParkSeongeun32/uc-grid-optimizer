"""
② uc_model.py : 최적화 모델 빌드 (Pyomo)
------------------------------------------------------------
Morales-España et al. (2013) "Tight and compact MILP formulation" 기반
  결정변수  u(운전), v(기동), w(정지), p(최소출력 초과분), r(예비력), nse(미공급)
  목적함수  무부하비용 + 구간선형 연료비 + 기동/정지비용 + 미공급 비용
  제약조건  수급균형, 예비력, 논리, 최소운전/정지, 출력상한(기동/정지 능력), 램프

[Week6 추가]  Stott et al. (2009) DC power flow  +  AIDC 수요반응
  집합      N(모선), L(선로), A(AI 데이터센터)
  결정변수  theta(모선 위상각, rad), f(선로조류, MW), nse_n,t(모선별 미공급),
            x(AIDC 학습상태), y(AIDC 학습 시작)
  제약조건  (4') 모선별 수급균형, (14) DC 조류식, (15) 선로 열용량, (16) 기준모선,
            (17) AIDC 소비전력, (18) 총 학습시간 보존, (19) 학습 시작 논리, (20) 최소 연속 학습시간
  network=0 이면 Week5 와 똑같은 단일모선 모델이 된다.
"""
import pyomo.environ as pyo


def build_uc_model(d, allow_reserve_short=False):
    gens, G, T = d["gens"], d["G"], d["T"]
    N, L, A = d["N"], d["L"], d["A"]
    ln, ai = d["lines"], d["aidc"]
    network, mode, Sb = d["network"], d["aidc_mode"], d["s_base"]
    free_init = d.get("free_init", False)       # True: 1시 직전 상태를 모델이 자유롭게 결정
    TT, T1 = T[-1], T[0]
    prev = {t: T[i - 1] for i, t in enumerate(T) if i > 0}   # t-1
    nxt = {t: T[i + 1] for i, t in enumerate(T) if i < len(T) - 1}  # t+1

    def g_(g, col):
        return float(gens.loc[g, col])

    def a_(a, col):
        return float(ai.loc[a, col])

    m = pyo.ConcreteModel(name="UnitCommitment")
    m.G = pyo.Set(initialize=G, ordered=True)
    m.T = pyo.Set(initialize=T, ordered=True)
    m.K = pyo.RangeSet(1, d["n_seg"])
    m.N = pyo.Set(initialize=N, ordered=True)   # 모선
    m.L = pyo.Set(initialize=L, ordered=True)   # 선로
    m.A = pyo.Set(initialize=A, ordered=True)   # AI 데이터센터

    # ---------- 비용 파라미터: C(P) = aP^2 + bP + c ----------
    def cost(g, P):
        return g_(g, "cost_a") * P ** 2 + g_(g, "cost_b") * P + g_(g, "cost_c")
    W = {g: (g_(g, "p_max") - g_(g, "p_min")) / d["n_seg"] for g in G}      # 구간 폭
    A_ = {g: cost(g, g_(g, "p_min")) for g in G}                             # 최소출력 운전 비용
    F = {(g, k): (cost(g, g_(g, "p_min") + k * W[g])
                  - cost(g, g_(g, "p_min") + (k - 1) * W[g])) / W[g] if W[g] > 0 else 0.0
         for g in G for k in m.K}                                            # 구간별 한계비용
    m._A, m._F, m._W = A_, F, W   # 결과 분석에서 다시 쓰려고 저장

    # ---------- 결정변수 ----------
    NN = pyo.NonNegativeReals
    m.u = pyo.Var(m.G, m.T, within=pyo.Binary)    # 운전상태 (1: on)
    m.v = pyo.Var(m.G, m.T, within=pyo.Binary)    # 기동
    m.w = pyo.Var(m.G, m.T, within=pyo.Binary)    # 정지
    m.p = pyo.Var(m.G, m.T, within=NN)            # 최소출력 초과분 (MW)
    m.dl = pyo.Var(m.G, m.K, m.T, within=NN)      # 구간별 출력 (MW)
    m.r = pyo.Var(m.G, m.T, within=NN)            # 예비력 (MW)
    m.nse = pyo.Var(m.N, m.T, within=NN)          # 모선별 미공급전력 (MW)  (단일모선이면 N=[1])
    m.rshort = pyo.Var(m.T, within=NN)            # 예비력 부족분 (기본은 0으로 고정)
    if not allow_reserve_short:
        for t in T:
            m.rshort[t].fix(0)
    rpen = d["voll"] * 0.5   # 예비력 부족 패널티 ($/MW) - 미공급보다는 싸게

    # [Week6] 송전 변수
    m.theta = pyo.Var(m.N, m.T, within=pyo.Reals)   # 모선 위상각 (rad)
    m.f = pyo.Var(m.L, m.T, within=pyo.Reals)       # 선로조류 (MW), 부호 = 방향 (from→to 가 +)
    # [Week6] AIDC 변수
    m.x = pyo.Var(m.A, m.T, within=pyo.Binary)      # 1: 학습, 0: 유휴
    m.y = pyo.Var(m.A, m.T, within=pyo.Binary)      # 학습 시작 (UC 의 v 와 같은 역할)

    # ---------- 목적함수: 총 운영비용 최소화 ----------
    m.obj = pyo.Objective(sense=pyo.minimize, expr=sum(
        A_[g] * m.u[g, t]
        + sum(F[g, k] * m.dl[g, k, t] for k in m.K)
        + g_(g, "startup_cost") * m.v[g, t]
        + g_(g, "shutdown_cost") * m.w[g, t]
        for g in m.G for t in m.T)
        + sum(d["voll"] * m.nse[n, t] for n in m.N for t in m.T)
        + sum(rpen * m.rshort[t] for t in m.T))

    # ---------- 구간선형(PWL) 비용 ----------
    m.seg_sum = pyo.Constraint(m.G, m.T, rule=lambda m, g, t:
        m.p[g, t] == sum(m.dl[g, k, t] for k in m.K))
    m.seg_ub = pyo.Constraint(m.G, m.K, m.T, rule=lambda m, g, k, t:
        m.dl[g, k, t] <= W[g] * m.u[g, t])

    # ================= [Week6] AI 데이터센터 부하 (17)~(20) =================
    def p_aidc(m, a, t):
        """(17) AIDC 소비전력 P_d,t (MW) = P_idle + x (P_train - P_idle)"""
        if mode == "average":                               # 평균(일정)부하: 상수
            return a_(a, "p_avg")
        x = d["fixed_x"][a, t] if mode == "step_fixed" else m.x[a, t]   # 고정 스케줄(입력) / 수요반응(변수)
        return a_(a, "p_idle") + x * (a_(a, "p_train") - a_(a, "p_idle"))
    m.P_aidc = pyo.Expression(m.A, m.T, rule=p_aidc)

    if mode == "step_dr":
        # (18) 하루 총 학습시간 보존: Σ_t x_d,t = τ_d  → 작업량은 그대로, "언제" 할지만 결정
        m.train_hours = pyo.Constraint(m.A, rule=lambda m, a:
            sum(m.x[a, t] for t in m.T) == a_(a, "train_hours"))
        # (19) 학습 시작 논리: y_t >= x_t - x_(t-1)   (전날부터 학습 중: x_0 = 1 가정)
        x_prev = lambda m, a, t: 1 if t == T1 else m.x[a, prev[t]]
        m.start = pyo.Constraint(m.A, m.T, rule=lambda m, a, t:
            m.y[a, t] >= m.x[a, t] - x_prev(m, a, t))
        # (20) 한 번 시작하면 최소 L_d 시간 연속 학습 (UC 최소운전시간과 같은 형태)
        m.min_block = pyo.Constraint(m.A, m.T, rule=lambda m, a, t:
            sum(m.y[a, i] for i in m.T if t - a_(a, "min_block") < i <= t) <= m.x[a, t])
    else:                                                    # 수요반응 없음 → 변수 고정
        for a in A:
            for t in T:
                m.x[a, t].fix(0)
                m.y[a, t].fix(0)

    # ================= 수급균형 =================
    gen_out = lambda m, g, t: g_(g, "p_min") * m.u[g, t] + m.p[g, t]   # 실제 출력 (MW)
    bus_load = lambda m, n, t: d["Dn"][n, t] + sum(m.P_aidc[a, t] for a in m.A if int(ai.loc[a, "bus"]) == n)

    if not network:
        # (4) 단일모선 수급균형 (Week5): 총 발전량 = 수요 + AIDC - 미공급전력
        n0 = N[0]
        m.balance = pyo.Constraint(m.T, rule=lambda m, t:
            sum(gen_out(m, g, t) for g in m.G)
            == sum(bus_load(m, n, t) for n in m.N) - m.nse[n0, t])
        for n in N:                                          # 미공급은 대표 모선 1개에만 기록
            if n != n0:
                for t in T:
                    m.nse[n, t].fix(0)
        for t in T:                                          # 송전 변수는 사용 안 함
            for n in N:
                m.theta[n, t].fix(0)
            for l in L:
                m.f[l, t].fix(0)
        m.nse_ub = pyo.Constraint(m.T, rule=lambda m, t:
            m.nse[n0, t] <= sum(bus_load(m, n, t) for n in m.N))
    else:
        # ===== [Week6] DC 조류 기반 송전제약 =====
        bus_g = {g: int(gens.loc[g, "bus"]) for g in G}
        # (4') 모선별 수급균형: 발전 - 수요 - AIDC + 미공급 = 나가는 조류 - 들어오는 조류
        def node_rule(m, n, t):
            gen = sum(gen_out(m, g, t) for g in m.G if bus_g[g] == n)
            out_f = sum(m.f[l, t] for l in m.L if int(ln.loc[l, "from_bus"]) == n)
            in_f = sum(m.f[l, t] for l in m.L if int(ln.loc[l, "to_bus"]) == n)
            return gen - bus_load(m, n, t) + m.nse[n, t] == out_f - in_f
        m.balance = pyo.Constraint(m.N, m.T, rule=node_rule)
        # (14) DC 선로조류: f_l = S_base (theta_i - theta_j) / x_l
        m.flow = pyo.Constraint(m.L, m.T, rule=lambda m, l, t:
            m.f[l, t] == Sb * (m.theta[int(ln.loc[l, "from_bus"]), t]
                               - m.theta[int(ln.loc[l, "to_bus"]), t]) / float(ln.loc[l, "x_pu"]))
        # (15) 선로 열용량: -F_max <= f_l <= F_max
        m.f_lim = pyo.Constraint(m.L, m.T, rule=lambda m, l, t:
            pyo.inequality(-float(ln.loc[l, "f_max_MW"]), m.f[l, t], float(ln.loc[l, "f_max_MW"])))
        # (16) 기준(slack) 모선 위상각 = 0
        m.ref = pyo.Constraint(m.T, rule=lambda m, t: m.theta[N[0], t] == 0)
        # 미공급은 그 모선의 부하를 넘을 수 없음
        m.nse_ub = pyo.Constraint(m.N, m.T, rule=lambda m, n, t: m.nse[n, t] <= bus_load(m, n, t))

    # (5) 예비력 요구량 (계통 전체 — 단순화: 예비력의 송전 가능성은 무시)
    m.reserve = pyo.Constraint(m.T, rule=lambda m, t:
        sum(m.r[g, t] for g in m.G) + m.rshort[t] >= d["R"][t])

    # (8) 논리 제약: u_t - u_(t-1) = v_t - w_t   (t=1: 초기상태 u0 / 초기조건 없으면 생략)
    def u_prev(m, g, t):
        return g_(g, "u0") if t == T1 else m.u[g, prev[t]]
    def logic_rule(m, g, t):
        if t == T1 and free_init:
            return pyo.Constraint.Skip
        return m.u[g, t] - u_prev(m, g, t) == m.v[g, t] - m.w[g, t]
    m.logic = pyo.Constraint(m.G, m.T, rule=logic_rule)

    # (6)(7) 최소 운전시간 / 최소 정지시간
    m.min_up = pyo.Constraint(m.G, m.T, rule=lambda m, g, t:
        sum(m.v[g, i] for i in m.T if t - g_(g, "min_up") < i <= t) <= m.u[g, t])
    m.min_dn = pyo.Constraint(m.G, m.T, rule=lambda m, g, t:
        sum(m.w[g, i] for i in m.T if t - g_(g, "min_down") < i <= t) <= 1 - m.u[g, t])

    # 초기조건: 시작 시점에 남아 있는 최소 운전/정지시간은 상태 고정
    def init_rule(m, g, t):
        k = t - T1 + 1
        if k <= g_(g, "TU_R"):
            return m.u[g, t] == 1
        if k <= g_(g, "TD_R"):
            return m.u[g, t] == 0
        return pyo.Constraint.Skip
    m.init_fix = pyo.Constraint(m.G, m.T, rule=init_rule)

    # (9)(10)(11) 출력 상한 + 기동/정지 시 출력 능력 (SU, SD)
    w_next = lambda m, g, t: 0 if t == TT else m.w[g, nxt[t]]
    def cap_rule(m, g, t, kind):
        Pmax, Pmin = g_(g, "p_max"), g_(g, "p_min")
        su = (Pmax - g_(g, "startup_cap")) * m.v[g, t]      # 기동 시간대
        sd = (Pmax - g_(g, "shutdown_cap")) * w_next(m, g, t)  # 정지 직전
        lhs, rhs = m.p[g, t] + m.r[g, t], (Pmax - Pmin) * m.u[g, t]
        if g_(g, "min_up") >= 2:          # (11) 하나로 결합 (tight & compact)
            if kind == "sd":
                return pyo.Constraint.Skip
            return lhs <= rhs - su - sd
        if kind == "su":                  # 최소운전 1h 발전기: (9), (10) 따로
            return lhs <= rhs - su
        return lhs <= rhs - sd
    m.cap_su = pyo.Constraint(m.G, m.T, rule=lambda m, g, t: cap_rule(m, g, t, "su"))
    m.cap_sd = pyo.Constraint(m.G, m.T, rule=lambda m, g, t: cap_rule(m, g, t, "sd"))

    # (12)(13) 램프 제약: 직전 출력과의 차이 <= RU, RD   (초기조건 없으면 t=1 생략)
    p_prev = lambda m, g, t: g_(g, "p0") if t == T1 else m.p[g, prev[t]]
    def ramp_up_rule(m, g, t):
        if t == T1 and free_init:
            return pyo.Constraint.Skip
        return m.p[g, t] + m.r[g, t] - p_prev(m, g, t) <= g_(g, "ramp_up")
    def ramp_dn_rule(m, g, t):
        if t == T1 and free_init:
            return pyo.Constraint.Skip
        return p_prev(m, g, t) - m.p[g, t] <= g_(g, "ramp_down")
    m.ramp_up = pyo.Constraint(m.G, m.T, rule=ramp_up_rule)
    m.ramp_dn = pyo.Constraint(m.G, m.T, rule=ramp_dn_rule)
    return m
