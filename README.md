# 찍먹 🍽️ — 음식 사진 한 장으로 "나한테 위험한지" 알려주는 웹 앱

해외여행에서 처음 보는 음식을 찍으면, 내 알레르기 기준으로 위험한지와 영양 정보를 알려준다.
음식 이름을 몰라도 된다.

👉 **처음 보는 팀원은 [`docs/진행상황.md`](docs/진행상황.md)부터** (쉬운 설명 · 지금까지 한 것 · 다음 할 일)

## 사용자 입장
```
① 내 알레르기 고르기 (예: 땅콩, 새우)
② 음식 사진 찍기
③ 결과:  🔴 새우 주의   ⚪ 땅콩 거의 없음   칼로리 450 · 나트륨 높음
         [왜요?] "보통 새우 육수를 써요..."   [가게에 물어보기] "Does this contain shrimp?"
```

## 우리 내부 흐름
```
사진 ─┬─> [학습 ① 분류 모델 ConvNeXt-Base] 101종 중 후보 3개 + 확신도(보정)
      └─> [학습 ② CLIP] 사진과 비슷한 레시피 30개 (175종 레시피 3만 5천 개에서 검색)  ← 항상 같이 봄
           │
   1등 확신 ≥ 0.95, 그리고 CLIP도 "분류 모델이 모르는 음식"을 강하게 가리키지 않음
           ├─ 예 ──> 1단계-1등        : 그 음식의 표(food_table) 한 줄
   1등 확신 0.6~0.95, 또는 CLIP이 모르는 음식(예: 소바)을 검색 30개 중 절반 이상으로 가리킴
           ├─ 예 ──> 1단계-합치기+CLIP : 후보 3개 표 + CLIP 레시피 비율 중 **가장 위험한 쪽(최댓값)**
   1등 확신 < 0.6 (처음 보는 음식)
           └─ 예 ──> 2단계            : CLIP 레시피 비율 (분류 모델 결과는 안 씀)
                         + LLM 이름 추정으로 교차 확인 (검색과 다르면 그 음식 근거를 '확인 필요'까지만 반영)
           │
   [판정] 같은 규칙(rules.py): 비율 ≥0.6 🔴주의 / ≥0.2 🟡확인 필요 / 그 아래 ⚪해당 없음 (레시피 30개 미만은 정보 부족)
           │
   [설명] LLM이 표·레시피 근거로 쉬운 말 설명
```

**ConvNeXt와 CLIP을 같이 쓰는 방식:** 둘 중 더 믿을 만한 하나를 **고르는 게 아니다**. 아는 음식은 ConvNeXt가 더 정확하니(93% vs CLIP 63%) 기본은 ConvNeXt,
CLIP은 **안전장치**로 항상 같이 본다. 둘이 엇갈리는 위험한 경우(ConvNeXt는 확신하는데 CLIP은 ConvNeXt가 모르는 음식을 가리킴)에는
하나를 고르지 않고 **둘 다 근거로 합쳐서 더 위험한 쪽으로** 판정한다. 알레르기 앱은 놓침이 괜한 경고보다 위험하기 때문.

**학습(딥러닝) 파트는 2개**: ① 분류 모델(ConvNeXt, 아는 음식) ② CLIP 검색기(처음 보는 음식 → 레시피)

**원칙**
- 판정은 항상 같은 규칙(`knowledge/rules.py`)이 한다. LLM은 이름 추정·재료 추정·설명만 한다.
- 1단계와 2단계는 같은 모양의 "알레르기 비율 줄"(19항목 + 레시피 수 + 출처)을 만든다 → 판정 함수 하나로 처리.
- 어떤 화면에서도 "안전하다"고 표시하지 않는다. 레시피 30개 미만은 `정보 부족`, LLM 추정은 `추정` 표시.

## 폴더
| 폴더 | 내용 | 상태 |
|---|---|---|
| `frontend/` | `index.html` 웹 화면: 알레르기 선택(기억됨), 카메라, 결과 카드 (판정 + '어떻게 판단했나요': 사진 AI · 비슷한 레시피 · AI 이름 추정) | 모든 경로 표시 |
| `backend/` | `main.py` FastAPI: `POST /analyze`(사진 + 알레르기 → 판정 JSON), `GET /allergens` | 1·2단계 + LLM 연결 |
| `modeling/` | `model.py` 예측(후보 3개 + 보정 확률), `calibration.json` 보정값, `classes.txt` 101종 목록, `weights/best.pt`(깃 제외, ConvNeXt-Base) | 연결 |
| `knowledge/` | 룰베이스: `rules.py` 규칙, `build_table.py` 표 만들기, `candidates.csv` 새 음식 후보 74종, `food_table.csv` 결과표, `lookup.py` 표 찾기, `judge.py` 판정·1/2단계 분기, `search.py` 2단계 CLIP 검색 | 1·2단계 연결 (2단계는 `knowledge/index/` 필요) |
| `llm/` | `client.py` 호출(Gemini/Groq), `guess.py` 이름·재료 추정, `explain.py` 설명, `check.py` 연결 확인 | 연결 (키는 `.env`) |
| `evaluation/` | `정답지.csv` 28종(사람 확인), ② 규칙 vs AI 직접 판정, ③ 1등만 vs 합치기, 나트륨 기준 | 결과 있음 (`evaluation/README.md`) |
| `AGENTS.md` | AI 코딩 도구용 규칙·데이터 형식·함수 모양 (`CLAUDE.md`가 불러옴) | 있음 |
| `notebooks/` | `01` EDA·전처리(알레르기·나트륨), `02` 새 음식 후보 집계, `03` 표 확장(175종)·사진 수집, `04` 학습 ② CLIP 파인튜닝, `04-2` 파인튜닝 개선 | 04·04-2 완료 (앱은 기본 CLIP) |
| `docs/plan.md` | 단계별 할 일 | 있음 |
| `docs/역할분담.md` | 팀원별 담당 (한솔·중현·유라·준영) | 있음 |

## 데이터 (깃에는 ③만)
| 파일 | 뭐냐 | 위치 |
|---|---|---|
| ① `1M_Final.csv` | 원본 레시피 100만 개 | 드라이브 `26-2 딥러닝/data1/` (재배포 금지) |
| ② `food101_recipes.parquet` | ①에서 Food-101 음식과 겹치는 레시피만 (약 11만 7천 개) — "왜요?" 근거용 | 드라이브 `data1/` (재배포 금지) |
| ③ `food_table.csv` | ②에 알레르기 규칙을 돌린 음식별 요약표 (175행: 101종 + 새 후보 74종, 영양 포함) — 판정용 | `knowledge/` |
| ④ `images/*.parquet` | 레시피 사진을 줄여 모은 것 (음식당 최대 400장) — CLIP·처음 보는 음식 감지 학습용 | 드라이브 `data1/` (재배포 금지) |

## 실행
```bash
pip install -r requirements.txt
# 드라이브 찍먹_실험기록/best/convnext_base/best.pt (한솔 최고 모델) → modeling/weights/best.pt
# 드라이브 찍먹_실험기록/best/clip_base/ 두 파일 → knowledge/index/ (2단계 검색, notebooks/04-3이 만듦)
uvicorn backend.main:app --host 127.0.0.1 --port 8000
# (다른 터미널) 폰·다른 사람이 쓰려면 ngrok으로 공개 주소 열기
ngrok http 8000
```
http://localhost:8000 이 앱 화면, http://localhost:8000/docs 는 API 시험 화면.
폰은 ngrok이 보여주는 `https://...ngrok-free.app` 주소로 접속. 쓸 때만 켜고 끝나면 둘 다 Ctrl+C.
(화면의 사진 버튼은 `<input type="file" capture>`라 http에서도 폰 카메라가 열린다. https가 꼭 필요한 건 실시간 카메라 미리보기(getUserMedia)뿐 — 지금 앱은 안 씀.)
LLM API 키·서버 계정은 `.env`에만 둔다 (gitignore 됨). 절대 커밋하지 않는다.

## 출처
- Food-101 (Bossard et al., ECCV 2014) — 학술 이용
- 1M_Final (Recipe1M+ 파생, Kaggle) — 연구용, 재배포 금지 (깃에는 통계 요약만)
- 알레르기 기준: 「식품 등의 표시·광고에 관한 법률 시행규칙」 [별표 2] 19개 항목
