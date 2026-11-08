# 송전제약·AI 데이터센터 수요반응을 고려한 발전기 기동정지계획(UC) 최적화

발전기 기동정지 + DC 조류 송전제약 + AI 데이터센터 수요반응을 한 MILP 모델로 풀고,
시나리오 9종을 자동 비교·해설하는 프로그램입니다. (Python · Pyomo · HiGHS)

## 실행
```
pip install -r requirements.txt
python run_scenarios.py uc_input_week6.xlsx --all
```

## 핵심 결과
- 수요반응 모델은 솔버가 스스로 18–22시(수요 피크)를 학습 휴지로 선택 → 정전 0 MWh, 하루 운영비 −59,685 $
- 송전 용량 −20% 시 비용 +70%, 데이터센터 입지는 발전단지 옆이 최적

![계통도](network_18h.png)
![AIDC 패턴](aidc_pattern.png)
