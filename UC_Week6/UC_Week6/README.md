# UC 최적화 프로그램 (발전기 기동정지계획 → 송전제약 + AI 데이터센터 수요반응)

엑셀만 바꾸면 → 최적 발전계획 + 그림 + 웹 대시보드가 자동으로 나오는 프로그램입니다.
Week5(단일모선 UC)에 **Week6(송전제약 DC 조류 + AIDC 수요반응)** 을 추가했습니다.
Week5 엑셀(`uc_input.xlsx`)도 예전과 똑같이 그대로 돌아갑니다.

## 1. 설치 (처음 한 번만)
```
pip install -r requirements.txt
```

## 2. 실행
```
python main.py uc_input.xlsx                        # Week5: 단일모선 UC 1개 풀기
python main.py uc_input_week6.xlsx                  # Week6: 송전제약 + AIDC (settings 시트의 network / aidc_mode 대로)
python run_scenarios.py uc_input.xlsx               # Week5 과제 4개 시나리오 비교
python run_scenarios.py uc_input_week6.xlsx         # Week6 S0~S4 비교 (단일모선 / 송전제약 / AIDC 평균·고정·수요반응)
python run_scenarios.py uc_input_week6.xlsx --lab   # Week6 실습 4개 (L14 용량, AIDC 위치, AIDC 규모, DR 유연성)
python run_scenarios.py uc_input_week6.xlsx --all   # S0~S4 + 실습 4개 전부
```
브라우저 자동 열기를 끄려면 끝에 `--no-open` 을 붙이세요.
시나리오 세트는 엑셀에 `lines`·`aidc` 시트가 있으면 Week6, 없으면 Week5 가 자동 선택됩니다.

## 3. 결과물 (results 폴더)
| 파일 | 내용 |
|---|---|
| result_*_dashboard.html | 보기 좋은 결과 리포트 (더블클릭). Week6: 시간 슬라이더 송전조류 계통도, 선로 이용률, AIDC 부하, 모선별 LMP |
| result_*.xlsx | summary / commitment_u / power_MW / balance_check / generator_summary / cost_breakdown / (Week6) line_flow_MW · line_util_pct · line_summary · nse_bus_MW · bus_load_MW · aidc · lmp |
| result_*_dispatch.png, _heatmap.png, _cost.png | 발표용 그림 (Week5 와 동일) |
| result_*_lines.png | (Week6) 선로 × 시간 이용률 히트맵 (■ = 혼잡) |
| result_*_network.png | (Week6) 피크 시간 송전조류 계통도 (화살표 방향, 색 = 이용률) |
| result_*_lmp.png, _aidc.png | (Week6) 모선별 한계가격, AIDC 소비전력 패턴 |
| compare_dashboard.html | 시나리오 비교 리포트 (비용 = 발전비용 + 미공급 비용, AIDC 패턴 비교, 시나리오별 계통도) |
| compare_summary.xlsx, compare_*.png | 비교 표·그림 (compare_cost_split: 발전비/미공급비 누적, compare_aidc: AIDC 패턴, compare_network: 피크 계통도) |

## 4. 엑셀 바꾸는 법
- **generators** 시트: 발전기 1기 = 1행. 행을 추가하면 발전기가 늘어남 (열 이름은 바꾸지 말 것)
  - `bus` 열 (Week6): 접속 모선. 없으면 모두 모선 1
  - `init_status_h`, `init_p` 가 없으면(Week6) 1시의 운전상태·출력은 모델이 결정
- **demand** 시트: `demand_MW` 1열(Week5) 또는 `bus1, bus2, …` 모선별 열(Week6). 행을 늘리면 계획 기간이 늘어남
- **buses** 시트 (Week6): `bus, name, x, y` — 모선 이름과 계통도 좌표
- **lines** 시트 (Week6): `line, from_bus, to_bus, x_pu, f_max_MW` — 선로 리액턴스(pu, S_base 기준)·열용량
- **aidc** 시트 (Week6): `name, bus, p_idle, p_train, train_hours, min_block, fixed_idle_hours`
- **settings** 시트: `reserve_ratio`, `voll`, 필요하면 `scenario`, `n_seg`,
  (Week6) `s_base`(100 MVA), `network`(1: 송전제약 / 0: 단일모선), `aidc_mode`(none / average / step_fixed / step_dr)

## 5. 파일 구성
| 파일 | 하는 일 |
|---|---|
| data_io.py | 엑셀 읽기(Week5·6 모두), 초기조건·모선별 수요·AIDC 파라미터 계산, 입력 오류 검사 |
| uc_model.py | Pyomo 최적화 모델. (4)~(13) Week5 UC + (4')(14)~(16) DC 조류 송전제약 + (17)~(20) AIDC 수요반응 |
| main.py | HiGHS로 풀기, 결과 정리(선로조류·이용률·혼잡·모선별 미공급·LMP·AIDC), 자동 해설, 저장 |
| visualize.py | PNG 그림 (+ 선로 이용률 히트맵, 송전조류 계통도, LMP, AIDC 패턴, 비용 분해 비교) |
| report.py | HTML 대시보드 (+ 시간 슬라이더 계통도, 선로 이용률 표, AIDC 차트, LMP 차트) |
| run_scenarios.py | 시나리오 일괄 실행 (SCENARIOS_W5 / SCENARIOS_W6 / SCENARIOS_LAB 리스트만 고치면 됨) |

## 6. Week6 모델 요약 (강의 식 번호)
- (4′) 모선별 수급균형: Σ발전 − 수요 − AIDC + 미공급 = 나가는 조류 − 들어오는 조류
- (14) DC 조류 f = S_base·(θ_i − θ_j)/x,  (15) |f| ≤ F_max,  (16) θ_ref = 0
- (17) AIDC 소비전력 P = P_idle + x·(P_train − P_idle),  (18) Σ_t x = τ (총 학습시간 보존),
  (19) y ≥ x_t − x_(t−1),  (20) 최소 연속 학습시간 L  — `step_dr` 일 때만 x, y 가 결정변수
- 예비력 (5)는 계통 전체 그대로 (예비력의 송전 가능성은 무시)
- 기동정지·AIDC 학습상태를 고정한 LP의 수급균형 쌍대값 = 모선별 한계가격(LMP). 혼잡이 없으면 모든 모선이 같은 값

### 검증 (강의 Week6 슬라이드와 동일한 결과)
| 시나리오 | 총비용 ($) | 발전비용 ($) | 미공급 (MWh) | 혼잡 (선로·h) |
|---|---|---|---|---|
| S0 단일모선 | 567,638 | 567,638 | 0.0 | 0 |
| S1 송전제약 | 568,422 | 568,422 | 0.0 | 19 |
| S2 AIDC 평균 | 648,038 | 623,712 | 24.3 | 40 |
| S3 AIDC 고정 | 682,717 | 627,141 | 55.6 | 42 |
| S4 AIDC 수요반응 | 623,032 | 623,032 | 0.0 | 40 (유휴 18–22시) |

참고: 대시보드 그래프는 Chart.js를 인터넷에서 불러오므로 인터넷 연결이 필요합니다 (계통도·표는 오프라인에서도 보임).
