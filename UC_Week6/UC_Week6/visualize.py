"""
④ visualize.py : 결과 그림(PNG) 저장
------------------------------------------------------------
- 발전기 색깔 = "급전순위(메리트오더)" : 싼 발전기는 차가운 청록, 비싼 발전기는 뜨거운 빨강
  → 어느 그림에서든 색만 보고 기저/첨두를 구분할 수 있음
- 발전기 수가 바뀌어도 색이 자동으로 다시 계산됨
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, to_hex, ListedColormap
import numpy as np

MERIT = ["#0B5563", "#1F8A8A", "#5FAE8E", "#C9C35B", "#F0A04B", "#E2603F", "#A62639"]
INK, MUTED, GRID = "#1B2733", "#6B7A86", "#E3E8EB"


def _korean_font():
    for f in ["Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic",
              "Noto Sans CJK KR", "Noto Sans KR"]:
        if any(f == x.name for x in font_manager.fontManager.ttflist):
            return f
    names = sorted({x.name for x in font_manager.fontManager.ttflist}, key=lambda n: "Sans" not in n)
    for n in names:                                 # 그 밖의 한글 폰트 자동 탐색 (고딕 우선)
        if any(k in n for k in ["CJK", "Nanum", "Gothic", "Malgun"]):
            return n
    return None


_f = _korean_font()
if _f:
    plt.rcParams["font.family"] = _f
plt.rcParams.update({"axes.unicode_minus": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.titleweight": "bold",
                     "axes.titlesize": 13, "axes.titlecolor": INK, "figure.dpi": 110})


def text_on(hx, a=1.0):
    """배경색(흰색 위에 투명도 a로 칠한 색)에 잘 보이는 글자색"""
    hx = hx.lstrip("#")
    rgb = [int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    rgb = [a * c + (1 - a) * 1.0 for c in rgb]
    lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return INK if lum > 0.55 else "#FFFFFF"


def merit_order(gens):
    """만출력 평균단가 기준 순위 (싼 순)"""
    avg = (gens["cost_a"] * gens["p_max"] ** 2 + gens["cost_b"] * gens["p_max"] + gens["cost_c"]) / gens["p_max"]
    return list(avg.sort_values().index)


def gen_colors(gens):
    order = merit_order(gens)
    cmap = LinearSegmentedColormap.from_list("merit", MERIT)
    n = len(order)
    return {g: to_hex(cmap(i / max(n - 1, 1))) for i, g in enumerate(order)}


def _clean(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def plot_dispatch(res, path):
    P, D, R, nse = res["P"], res.get("D_total", res["D"]), res["R"], res["nse"]   # D: 수요 (+AIDC)
    has_aidc = len(res.get("aidc_P", [])) > 0
    col = gen_colors(res["gens"])
    T = list(P.columns)
    fig, ax = plt.subplots(figsize=(12, 5.6))
    bottom = np.zeros(len(T))
    for g in merit_order(res["gens"]):          # 싼 발전기부터 아래에 쌓기
        ax.bar(T, P.loc[g].values, bottom=bottom, color=col[g], label=g, width=0.82, edgecolor="white", lw=0.4)
        bottom += P.loc[g].values
    if nse.sum() > 1e-6:
        ax.bar(T, nse.values, bottom=bottom, color="none", edgecolor="#A62639", hatch="///", label="미공급", width=0.82)
    ax.plot(T, D.values, color=INK, lw=2.2, marker="o", ms=4, label="수요+AIDC" if has_aidc else "수요", zorder=5)
    if has_aidc:
        ax.plot(T, res["D"].values, color=MUTED, lw=1.2, ls=":", label="기존 수요", zorder=5)
    ax.plot(T, (D + R).values, color=INK, lw=1.2, ls="--", alpha=0.6, label="수요+예비력", zorder=5)
    pk = D.idxmax()
    ax.annotate(f"피크 {pk}시\n{D[pk]:,.0f} MW", (pk, D[pk]), xytext=(0, 28), textcoords="offset points",
                ha="center", fontsize=9, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED))
    ax.set_xticks(T); ax.set_xlabel("시간 (h)"); ax.set_ylabel("MW")
    ax.set_title(f"발전기별 출력과 수요  ·  {res['label']}", loc="left")
    ax.set_ylim(0, max((D + R).max(), bottom.max()) * 1.15)
    _clean(ax)
    ax.legend(ncol=min(len(P) + 3, 12), loc="upper center", bbox_to_anchor=(0.5, -0.13), frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_heatmap(res, path):
    u, P = res["u"], res["P"]
    order = merit_order(res["gens"])
    u, P = u.loc[order], P.loc[order]
    col = gen_colors(res["gens"])
    T = list(P.columns)
    fig, ax = plt.subplots(figsize=(12, 0.48 * len(order) + 1.4))
    for i, g in enumerate(order):
        pmax = res["gens"].loc[g, "p_max"]
        for j, t in enumerate(T):
            if u.loc[g, t]:
                a = min(1.0, max(0.0, 0.35 + 0.65 * P.loc[g, t] / pmax))
                ax.add_patch(plt.Rectangle((j, i), 0.94, 0.88, color=col[g], alpha=a, lw=0))
                ax.text(j + 0.47, i + 0.46, f"{P.loc[g,t]:.0f}", ha="center", va="center", fontsize=7.3,
                        color=text_on(col[g], a))
            else:
                ax.add_patch(plt.Rectangle((j, i), 0.94, 0.88, color="#EEF1F3", lw=0))
    ax.set_xlim(0, len(T)); ax.set_ylim(len(order), 0)
    ax.set_xticks(np.arange(len(T)) + 0.47, T); ax.set_yticks(np.arange(len(order)) + 0.44, order)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_xlabel("시간 (h)")
    ax.set_title("기동정지 상태와 출력(MW)  ·  색이 진할수록 최대출력에 가까움, 회색 = 정지", loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_cost(res, path):
    b = {k: v for k, v in res["breakdown"].items() if v > 0.5}
    fig, ax = plt.subplots(figsize=(6, 4.2))
    cols = ["#0B5563", "#5FAE8E", "#F0A04B", "#A62639", "#6B7A86"][:len(b)]
    w, _ = ax.pie(b.values(), colors=cols, startangle=90, counterclock=False,
                  wedgeprops=dict(width=0.38, edgecolor="white"))
    ax.text(0, 0.07, f"${res['cost']:,.0f}", ha="center", fontsize=15, weight="bold", color=INK)
    ax.text(0, -0.15, "총 운영비용", ha="center", fontsize=9, color=MUTED)
    ax.legend(w, [f"{k}  {v/res['cost']*100:.1f}%" for k, v in b.items()], loc="center left",
              bbox_to_anchor=(1, 0.5), frameon=False)
    ax.set_title("비용 구성", loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_results(res, out):
    """main.py에서 호출: 그림 3장(+ Week6 송전/AIDC 그림) 저장"""
    plot_dispatch(res, out + "_dispatch.png")
    plot_heatmap(res, out + "_heatmap.png")
    plot_cost(res, out + "_cost.png")
    if res.get("network"):
        plot_line_util(res, out + "_lines.png")
        pk = res["D_total"].idxmax()
        plot_network(res, pk, out + "_network.png")
        if res["lmp"] is not None:
            plot_lmp(res, out + "_lmp.png")
    if len(res.get("aidc_P", [])):
        plot_aidc(res, out + "_aidc.png")


# ---------------- [Week6] 송전제약 ----------------
UTIL_CMAP = LinearSegmentedColormap.from_list("util", ["#2E9E6B", "#C9C35B", "#F0A04B", "#D64545", "#7A1B2E"])


def util_color(u):
    """선로 이용률 → 색 (회색 <80%, 노랑 80~100%, 빨강 100%(혼잡), 진빨강 >100%)"""
    return "#7A1B2E" if u > 1.001 else "#D64545" if u >= 0.999 else "#E0B52E" if u >= 0.8 else "#6B7A86"


def plot_line_util(res, path):
    """선로 x 시간 이용률 히트맵 (강의 결과 ①)"""
    util = res["util"]
    L, T = list(util.index), list(util.columns)
    fig, ax = plt.subplots(figsize=(12, 0.45 * len(L) + 1.6))
    im = ax.imshow(util.values * 100, cmap=UTIL_CMAP, vmin=0, vmax=100, aspect="auto")
    for i, l in enumerate(L):
        for j, t in enumerate(T):
            if util.loc[l, t] >= 0.999:
                ax.plot(j, i, marker="s", ms=4, color="white")
    ax.set_xticks(range(len(T)), T); ax.set_yticks(range(len(L)), L)
    ax.set_xlabel("시간 (h)")
    ax.set_title(f"선로 이용률 |f|/F_max (%)  ·  {res['label']}   (■ = 용량 100% 도달 = 혼잡)", loc="left")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, pad=0.01); cb.set_label("이용률 (%)")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def draw_network(ax, res, t, title=None, show_legend=True):
    """한 시간대의 송전조류 계통도 (화살표 = 방향, 색 = 이용률, 숫자 = MW와 %)"""
    buses, lines, gens = res["buses"], res["lines"], res["gens"]
    flow, util = res["flow"][t], res["util"][t]
    xy = {n: (float(buses.loc[n, "x"]), float(buses.loc[n, "y"])) for n in buses.index}
    for l in lines.index:
        i, j = int(lines.loc[l, "from_bus"]), int(lines.loc[l, "to_bus"])
        f = float(flow[l])
        a, b = (xy[i], xy[j]) if f >= 0 else (xy[j], xy[i])
        c = util_color(float(util[l]))
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color=c, lw=1.5 + 3.5 * min(float(util[l]), 1.2),
                                                        shrinkA=14, shrinkB=14, mutation_scale=14))
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ax.text(mx, my, f"{l}\n{abs(f):,.0f} MW\n({100*float(util[l]):.0f}%)", ha="center", va="center", fontsize=7.5,
                color=c if c != "#6B7A86" else INK, weight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=c, lw=1))
    for n in buses.index:
        gl = [g for g in gens.index if int(gens.loc[g, "bus"]) == n]
        al = [a for a in res["aidc"].index if int(res["aidc"].loc[a, "bus"]) == n] if len(res["aidc"]) else []
        is_gen = len(gl) > 0
        ax.scatter(*xy[n], s=520, marker="s" if is_gen else "o", color="#F3A6A6" if is_gen else "#5B9BD5",
                   edgecolor=INK, lw=1.2, zorder=5)
        ax.text(xy[n][0], xy[n][1], str(n), ha="center", va="center", fontsize=10, weight="bold", zorder=6)
        lab = f"{buses.loc[n,'name']}\n부하 {res['bus_load'].loc[n, t]:,.0f} MW"
        if gl:
            pg = res["P"].loc[gl, t].sum()
            lab += f"\n{'·'.join(gl)} {pg:,.0f} MW"
        if al:
            lab += f"\nAIDC {res['aidc_P'].loc[al, t].sum():,.0f} MW"
        if res["nse_bus"].loc[n, t] > 1e-6:
            lab += f"\n⚠ 부하차단 {res['nse_bus'].loc[n, t]:,.0f} MW"
        ax.text(xy[n][0], xy[n][1] - 0.32, lab, ha="center", va="top", fontsize=7.5, color=MUTED, zorder=6)
    xs, ys = [p[0] for p in xy.values()], [p[1] for p in xy.values()]
    ax.set_xlim(min(xs) - 0.9, max(xs) + 0.9); ax.set_ylim(min(ys) - 1.1, max(ys) + 0.7)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title or f"송전조류 계통도  ·  {res['label']}  ·  {t}시", loc="left")
    if show_legend:
        from matplotlib.lines import Line2D
        h = [Line2D([0], [0], color=c, lw=3, label=s) for c, s in
             [("#6B7A86", "이용률 <80%"), ("#E0B52E", "80–100%"), ("#D64545", "100% (혼잡)"), ("#7A1B2E", ">100% (과부하)")]]
        ax.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=4, frameon=False, fontsize=8)


def plot_network(res, t, path):
    fig, ax = plt.subplots(figsize=(10, 7))
    draw_network(ax, res, t)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_lmp(res, path):
    """모선별 한계가격(LMP) 시간대별 선그래프"""
    lmp = res["lmp"]
    T = list(lmp.columns)
    fig, ax = plt.subplots(figsize=(12, 4.2))
    cmap = plt.get_cmap("tab10")
    for i, n in enumerate(lmp.index):
        ax.step(T, lmp.loc[n].values, where="mid", lw=1.8, color=cmap(i % 10),
                label=f"모선{n} {res['buses'].loc[n,'name']}")
    ax.set_xticks(T); ax.set_xlabel("시간 (h)"); ax.set_ylabel("$/MWh")
    ax.set_title(f"모선별 한계가격 LMP  ·  {res['label']}   (혼잡이 없으면 모든 모선이 같은 값)", loc="left")
    _clean(ax); ax.legend(ncol=min(len(lmp), 6), loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


# ---------------- [Week6] AIDC ----------------
def plot_aidc(res, path, others=None, title=None):
    """AIDC 소비전력 패턴 (좌축) + 기존 계통수요 (우축, 회색)  — 강의 결과 ②
       others: [(label, aidc_P Series), ...]  비교용으로 함께 그릴 패턴"""
    T = list(res["D"].index)
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax2 = ax.twinx()
    ax2.bar(T, res["D"].values, color="#E6EAED", width=1.0, zorder=0, label="기존 계통수요 (우축)")
    ax2.set_ylabel("계통수요 (MW)", color=MUTED); ax2.set_ylim(0, res["D"].max() * 1.15)
    pk = res["D"].idxmax()
    ax2.axvspan(pk - 0.5, pk + 0.5, color="#D64545", alpha=0.08); ax2.text(pk, res["D"].max() * 1.1, "피크", ha="center", fontsize=8, color="#D64545")
    styles = [("#1F4E79", "-"), ("#E07B1A", "-"), ("#2E9E6B", "-"), ("#8E44AD", "--"), ("#C9A227", "--"), ("#A62639", ":"), ("#0B5563", ":")]
    series = (others or []) + [(res["label"], res["aidc_P"].sum())]
    for k, (lab, s) in enumerate(series):
        c, ls = styles[k % len(styles)]
        ax.step(T, s.values, where="mid", lw=2.6 - 0.25 * k, color=c, ls=ls, label=f"{lab} (일 {s.sum():,.0f} MWh)", zorder=3 + k)
    if len(res["aidc"]):
        ax.axhline(res["aidc"]["p_avg"].sum(), color=MUTED, ls="--", lw=1.4, label=f"평균부하 {res['aidc']['p_avg'].sum():.1f} MW", zorder=2)
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    ax.set_xticks(T); ax.set_xlabel("시간 (h)"); ax.set_ylabel("AIDC 소비전력 (MW)")
    ax.set_ylim(0, max(res["aidc_P"].values.max() if len(res["aidc_P"]) else 1, 1) * 1.25)
    ax.set_title(title or f"AI 데이터센터 소비전력과 계통수요  ·  {res['label']}  ({res['aidc_mode']})", loc="left")
    for s_ in ["top"]:
        ax.spines[s_].set_visible(False); ax2.spines[s_].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_compare_cost_split(results, path):
    """시나리오별 총비용 = 발전비용 + 미공급 비용(VOLL) 누적 막대 (강의 결과 ③)"""
    labels = [r["label"] for r in results]
    gen = [r["gen_cost"] / 1000 for r in results]
    nse = [(r["cost"] - r["gen_cost"]) / 1000 for r in results]
    fig, ax = plt.subplots(figsize=(max(10, 1.3 * len(results)), 4.8))
    labels = [l.replace(" ", "\n", 1) if len(l) > 8 else l for l in labels]
    ax.bar(labels, gen, color=["#B9C2C8" if not r["network"] else "#1F8A8A" for r in results], width=0.6, label="발전비용")
    ax.bar(labels, nse, bottom=gen, color="#D64545", width=0.6, label="미공급 비용 (VOLL)")
    for i, r in enumerate(results):
        ax.text(i, r["cost"] / 1000, f"{r['cost']/1000:,.0f}", ha="center", va="bottom", fontsize=9, color=INK)
    lo = min(gen) * 0.9
    ax.set_ylim(lo, max(r["cost"] for r in results) / 1000 * 1.08); ax.set_ylabel("총 운영비용 (천 $)")
    ax.set_title("시나리오별 총 운영비용 (발전비용 + 미공급 비용)", loc="left"); _clean(ax)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_compare_network(results, t, path):
    """여러 시나리오의 같은 시간대 계통도를 나란히"""
    k = len(results)
    fig, axes = plt.subplots(1, k, figsize=(8 * k, 7))
    axes = [axes] if k == 1 else list(axes)
    for ax, r in zip(axes, results):
        draw_network(ax, r, t, title=f"{r['label']}  ·  {t}시", show_legend=(ax is axes[0]))
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


# ---------------- 시나리오 비교용 ----------------
def plot_compare_cost(results, path):
    labels = [r["label"].replace(" ", "\n", 1) if len(r["label"]) > 8 else r["label"] for r in results]
    costs = [r["cost"] for r in results]
    base = costs[0]
    fig, ax = plt.subplots(figsize=(max(10, 1.3 * len(results)), 4.6))
    colors = ["#6B7A86"] + ["#A62639" if c > base else "#1F8A8A" for c in costs[1:]]
    bars = ax.bar(labels, costs, color=colors, width=0.6)
    for b_, c in zip(bars, costs):
        d = (c - base) / base * 100
        txt = f"${c:,.0f}" + ("" if b_ is bars[0] else f"\n({d:+.1f}%)")
        ax.text(b_.get_x() + b_.get_width() / 2, c, txt, ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_ylim(0, max(costs) * 1.2); ax.set_ylabel("$/일")
    ax.set_title("시나리오별 총 운영비용", loc="left"); _clean(ax)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_diff(base, res, path):
    """Base 대비 기동정지 변화: 초록=새로 켜짐, 빨강=꺼짐, 회색=둘 다 운전"""
    order = merit_order(base["gens"])
    ub, us = base["u"].loc[order], res["u"].loc[order]
    T = list(ub.columns)
    fig, ax = plt.subplots(figsize=(12, 0.42 * len(order) + 1.5))
    for i, g in enumerate(order):
        for j, t in enumerate(T):
            a, b = ub.loc[g, t], us.loc[g, t]
            c, txt = ("#C9D3D9", "") if a and b else ("#2E9E6B", "+") if b and not a else \
                     ("#D64545", "−") if a and not b else ("#F5F7F8", "")
            ax.add_patch(plt.Rectangle((j, i), 0.94, 0.88, color=c, lw=0))
            if txt:
                ax.text(j + 0.47, i + 0.46, txt, ha="center", va="center", color="white", fontsize=11, weight="bold")
    ax.set_xlim(0, len(T)); ax.set_ylim(len(order), 0)
    ax.set_xticks(np.arange(len(T)) + 0.47, T); ax.set_yticks(np.arange(len(order)) + 0.44, order)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0); ax.set_xlabel("시간 (h)")
    ax.set_title(f"Base 대비 기동정지 변화 · {res['label']}   (＋ 새로 켜짐 / − 꺼짐 / 회색 = 그대로 운전)", loc="left")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
