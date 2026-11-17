# ② 우리 방식 vs 그냥 AI 결과

> 자동 생성 파일. `python -m evaluation.llm_vs_rule`로 다시 만든다. AI 답 원문은 `llm_답변.csv`.

- 음식: 정답지 28종 × 19항목. 음식 이름으로만 비교한다 (사진 AI 오차는 ③에서 따로).
- 우리 방식 기준 (`knowledge/judge.py`): 주의 ≥0.6, 확인 필요 ≥0.2, 레시피 30개 미만이면 정보 부족
- 그냥 AI: `llm.guess.guess_ingredients(음식 이름)`이 말한 재료를 같은 룰(`rules.allergen_flags`)로 읽는다. 들어 있으면 주의, 없으면 해당 없음 (AI는 "확인 필요"를 내지 않는다).

| 방식 | 답한 음식 | 놓침 ↓ | 약하게 | 괜한 주의 ↓ | 괜한 확인 |
|---|---|---|---|---|---|
| 우리 방식 (레시피 통계 + 룰) | 28/28 | **2** (2.2%) | 32 (34.8%) | 0 (0.0%) | 28 (6.4%) |
| 그냥 AI 1회차 | 25/28 | **7** (8.5%) | 0 (0.0%) | 26 (6.6%) | 0 (0.0%) |
| 그냥 AI 2회차 | 26/28 | **7** (8.2%) | 0 (0.0%) | 26 (6.4%) | 0 (0.0%) |
| 그냥 AI 3회차 | 26/28 | **7** (8.2%) | 0 (0.0%) | 26 (6.4%) | 0 (0.0%) |

- AI가 3번 답하는 동안 판정이 바뀐 칸: **0칸** (두 번 이상 다 답한 음식 25종 기준)

## 놓친 칸 (정답 1인데 해당 없음)
- **우리 방식 (레시피 통계 + 룰)** (2칸): tiramisu 밀, baklava 밀
- **그냥 AI 1회차** (7칸): pad_thai 밀, fried_rice 돼지고기, spaghetti_carbonara 우유, spaghetti_carbonara 돼지고기, tiramisu 밀, baklava 밀, paella 돼지고기
- **그냥 AI 2회차** (7칸): pad_thai 밀, fried_rice 돼지고기, spaghetti_carbonara 우유, spaghetti_carbonara 돼지고기, tiramisu 밀, baklava 밀, paella 돼지고기
- **그냥 AI 3회차** (7칸): pad_thai 밀, fried_rice 돼지고기, spaghetti_carbonara 우유, spaghetti_carbonara 돼지고기, tiramisu 밀, baklava 밀, paella 돼지고기

## 읽는 법
- 놓침: 정답 1(보통 들어감)인데 "해당 없음". 위험한데 괜찮다고 한 것. **제일 나쁨.**
- 괜한 주의: 정답 0인데 "주의". 많으면 사람들이 경고를 무시한다.
- 놓침·약하게 비율은 정답 1인 칸 수로, 괜한 주의·괜한 확인 비율은 정답 0인 칸 수로 나눈 것이다.
- 그냥 AI가 답하지 못한 음식(None)은 그 회차에서 뺐다. "답한 음식" 칸을 같이 볼 것.
