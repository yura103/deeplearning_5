# AGENTS.md — AI 코딩 도구용 안내 (Claude Code · Codex · Gemini 공통)

> **먼저 [`docs/인수인계_AI용.md`](docs/인수인계_AI용.md)를 읽는다** (지금 상태·결정·다음 할 일).

사람용 설명은 `README.md`, `docs/진행상황.md`. 이 파일은 **AI가 작업 전에 읽는 규칙·구조·데이터 형식**이다.
팀원별 할 일과 완료 기준은 `docs/역할분담.md`. 사용자가 자기 이름을 말하면 그 사람 부분만 작업한다.

## 프로젝트 한 줄
찍먹: 음식 사진 → 무슨 음식(분류/CLIP) → 레시피 통계로 알레르기 19항목 비율 → **룰**로 🔴주의/🟡확인 필요/⚪해당 없음. FastAPI + HTML 한 장.

## 절대 규칙
1. **판정은 `knowledge/judge.py`의 규칙만 한다.** LLM은 이름 추정·재료 추정·설명만. LLM 출력으로 단계를 바꾸지 않는다 (교차 확인 실패 시 `확인 필요`로 올리는 것만 허용).
2. 어떤 화면·문장에서도 **"안전하다"고 말하지 않는다.** 레시피 30개 미만은 `정보 부족`, LLM 추정은 `추정` 표시.
3. **데이터는 깃에 올리지 않는다** (재배포 금지): `1M_Final.csv`, 레시피 원문(`*.parquet`), 사진, 모델 가중치(`*.pt`). 깃에는 요약표(`food_table.csv`)만. `.gitignore`가 막고 있지만 새 확장자를 만들면 확인할 것.
4. **비밀값(API 키, 학과 서버 계정)은 `.env`에만.** 코드·노트북·커밋·출력에 쓰지 않는다. 읽을 때는 `os.environ`.
5. 함수 모양(이름·입력·출력)은 아래 "연결 지점"을 지킨다. 바꿔야 하면 그 함수를 쓰는 담당자와 먼저 맞춘다.
6. 무거운 계산(1M_Final 처리, 학습, 사진 전체 처리)은 **Colab/학과 서버**에서. 노트북으로 만든다.
7. `main`에 바로 올리지 않는다. 브랜치 → PR.

## 폴더
| 경로 | 내용 | 담당 |
|---|---|---|
| `backend/main.py` | `POST /analyze`(사진+알레르기→JSON), `GET /allergens`, `frontend/` 제공 | 김유라 |
| `frontend/index.html` | 알레르기 선택(localStorage) → 사진 → 결과 카드 | 서준영 |
| `knowledge/rules.py` | 재료 → 19항목 규칙 (`allergen_flags`, `ingredients_text`, `match`) | (완료, 고칠 때 팀 공유) |
| `knowledge/build_table.py` | 1M_Final → `food_table.csv` (Colab에서 실행) | (완료) |
| `knowledge/lookup.py` | 음식 이름 → 비율 줄 (`row`, `ALLERGENS`) | (완료) |
| `knowledge/judge.py` | 1/2단계 분기 + 판정 (`analyze`) | 박중현(2단계), 주한솔(기준값) |
| `knowledge/search.py` | 2단계: 사진 → 기본 CLIP → 비슷한 레시피 30개 → 비율 줄 (`search`, `available`). 검색 목록은 `knowledge/index/`(깃 제외) | 박중현 |
| `modeling/model.py` | ConvNeXt-Tiny 로드·예측 (`load_model`, `predict`, `TF`) | 주한솔 |
| `llm/` | `guess.py`(이름·재료 추정), `explain.py`(설명) — 지금 빈 함수 | 김유라 |
| `evaluation/` | 알레르기 정답지 + 평가 스크립트 | 서준영 |
| `notebooks/` | 01 EDA, 02 후보 집계, 03 표 확장·사진 수집, 04·04-2 CLIP 실험, 04-3 앱 검색 목록. 새 노트북은 `05_...`부터 | 각자 |

## 실행 · 자체 검사
```bash
pip install -r requirements.txt
python -m knowledge.judge          # 판정 자체 검사 (assert). 판정 코드 고치면 꼭 돌릴 것
python -m knowledge.search         # 검색 합치기 자체 검사 (torch 없이)
uvicorn backend.main:app --reload  # http://localhost:8000 화면, /docs API 시험
```
`modeling/weights/best.pt`가 없으면 `/analyze`는 503 (화면·판정 코드는 가중치 없이도 개발 가능).
`knowledge/index/`(04-3 결과 두 파일)가 없으면 2단계는 `확인 필요`로만 나온다. 있으면 첫 2단계 요청 때 CLIP(약 600MB)을 받아 온다.

## 연결 지점 (함수 모양)
```python
# 분류 (modeling/model.py)
predict(model, pil_img, k=3) -> [(class, prob), ...]        # 확률 높은 순

# 비율 줄: 1단계(lookup.row)와 2단계(search) 모두 이 모양
{'알류': 0.12, ..., '잣': 0.0,          # 19항목, 0~1
 'n_recipes': 1520, 'nutrition': {'kcal': 450.0, 'protein_g':..., 'fat_g':..., 'carbs_g':..., 'fiber_g':..., 'sodium_mg':...},
 'source': '레시피 통계'}              # 2단계는 'CLIP 검색', LLM 재료 추정은 'LLM 추정'

# 판정 (knowledge/judge.py)
analyze(cands, my_allergens, stage2=None, peek=None) -> {   # stage2 = CLIP 검색 + LLM 교차 확인 (애매·처음 보는 음식), peek = CLIP 검색만.
#   1등 확률 ≥T_ONE이어도 peek 결과 1등이 분류 모델이 모르는 음식이고 검색 30개 중 절반 이상이면 합치기+CLIP (judge.clip_says_new, 예: 소바→ramen 0.97)
  'route': '1단계-1등' | '1단계-합치기' | '1단계-합치기+CLIP' | '2단계',   # 합치기(애매함)는 stage2 결과도 같이 합침
  'foods': [...], 'similar': [CLIP이 찾은 비슷한 음식 3개] (없으면 []), 'verdict': {알레르기: '주의'|'확인 필요'|'해당 없음'|'정보 부족'},
  'other_caution': [...], 'n_recipes': int, 'nutrition': {...}, 'source': str}
# backend가 여기에 추가: 'candidates': [{'food','prob'}], 'llm_guess': [{'food','conf'}] (2단계만, 없으면 []),
#                        'explanation': str | None   (LLM 호출은 각각 최대 15초)

# 2단계 검색 (knowledge/search.py) — 학습 안 한 기본 CLIP (04·04-2 결과: 파인튜닝은 주의놓침이 더 나빠서 안 씀)
search(pil_img, k=30) -> (비율 줄, [(class, 유사도 합), ...])   # 비율 줄은 위와 같은 모양, source='CLIP 검색', nutrition={}
crosscheck((비율 줄, foods), guesses, ingredients_of) -> (비율 줄, foods)
  # guess_name 결과가 CLIP 상위 3개와 다르면 LLM 쪽 근거(표 비율 또는 guess_ingredients→룰)를 '확인 필요'(0.5)까지만 반영.
  # 확신 < 0.5·None이면 그대로. backend의 stage2 = search + guess_name(동시) → crosscheck

# LLM (llm/) — 연결 전이면 None 반환, 앱은 None이어도 동작해야 함
guess_name(pil_img) -> [(영어 음식 이름, 0~1)] | None
guess_ingredients(food_name) -> ['flour', 'egg', ...] | None   # 영어 재료 → rules.allergen_flags로 판정
explain(cls, info, question=None) -> str | None              # info = analyze() 결과
```
판정 기준 상수(`CAUTION 0.6`, `CHECK 0.2`, `MIN_RECIPES 30`, `T_ONE 0.95`, `T_KNOWN 0.6`)는 `judge.py` 맨 위. T_ONE·T_KNOWN은 05(Base, 보정 후 확률 기준)로 정함 — 근거는 docs/진행상황.md 12.

## 데이터 (드라이브, 깃 밖)
팀 공유 드라이브 폴더 `26-2 딥러닝`. Colab에서는 `/content/drive/MyDrive/26-2 딥러닝` (바로가기 추가 필요).
한글 폴더명은 NFC 정규화해서 찾는다 → 노트북 04의 `find()` 함수를 그대로 쓰면 된다.

| 경로 (`26-2 딥러닝/` 아래) | 형식 · 열 |
|---|---|
| `data1/1M_Final.csv` | 원본 레시피 100만 개 (1.4GB). 쓰는 열: `title`, `NER`(재료 리스트 문자열 `"['eggs', 'flour']"`), `energy_kcal_per_serving`·`protein_g_per_serving`·`fat_g_per_serving`·`carbs_g_per_serving`·`fiber_g_per_serving`·`sodium_mg_per_serving`, `image1`(사진 URL) |
| `data1/table_recipes.parquet` | 표 175종에 매칭된 레시피만. `recipe_idx`(1M_Final 행 번호), `label`(음식), `title`, `NER`, `kcal`…`sodium_mg`, `image1`. 한 레시피가 두 음식에 걸리면 두 줄 |
| `data1/images/{label}.parquet` | 레시피 사진 (음식당 최대 400, 짧은 변 256px JPEG). `recipe_idx`, `label`, `title`, `image1`, `jpg`(bytes), `md5` |
| `data1/images/_fake_md5.csv` | 같은 그림이 반복된 가짜 사진 md5 → **학습·평가에서 제외** |
| `data1/food-101.tar.gz` | Food-101 (101종 × 1,000장). 풀면 `food-101/images/{class}/{id}.jpg`, `meta/train.txt`·`test.txt` |
| `찍먹_실험기록/best/convnext_base/best.pt` | **앱 분류 모델** (주한솔, timm ConvNeXt-Base, test 93.4%) → 로컬 `modeling/weights/best.pt`. `model.py`가 Tiny/Base를 자동 구분 |
| `찍먹_실험기록/best/convnext_tiny/best.pt` | 처음 모델 (torchvision ConvNeXt-Tiny, test 88.8%), 비교용 |
| `modeling/calibration.json` (깃) | notebooks/05 결과 `{model, temperature, T_ONE, T_KNOWN}`. `model`이 불러온 모델과 같을 때만 보정 |
| `찍먹_실험기록/best/clip_base/` | **앱이 쓰는 검색 목록** (04-3, 기본 CLIP): `index_emb.npy`(레시피 글 벡터 N×512, fp16, 정규화됨), `index_meta.parquet`(`recipe_idx`, `label`, `title`, 19항목 0/1, 같은 순서) → 로컬 `knowledge/index/` |
| `찍먹_실험기록/best/clip/`, `best/clip2/` | 04·04-2 파인튜닝 실험 결과 (앱에서는 안 씀) |
| `찍먹_실험기록/표/` | 실험 결과표 (`food_table.csv`, `clip_결과.csv`, `convnext_vs_clip.csv`, `사진수집_요약.csv`). 새 결과도 여기로 |

깃 안 데이터:
- `knowledge/food_table.csv`: 175행. `class`, 19항목 비율, `kcal, protein_g, fat_g, carbs_g, fiber_g, sodium_mg`(1인분 중앙값), `n_recipes`
- `knowledge/candidates.csv`: 새 음식 후보 74종 (`class, display_ko, aliases`). 분류 모델은 모르고 표에만 있음
- `modeling/classes.txt`: 분류 모델 101종 (순서 = 출력 순서)
- 알레르기 19항목 (한국 표시 기준): 알류 우유 메밀 땅콩 대두 밀 고등어 게 새우 돼지고기 복숭아 토마토 아황산류 호두 닭고기 쇠고기 오징어 조개류 잣

## 사진 수 주의
한식(김밥·떡볶이 등)은 레시피·사진이 10개 미만. 사진 30장 미만 음식은 학습·평가에서 빼고 검색 대상으로만 둔다 (04와 같은 기준).

## 노트북 규칙
- 첫 셀: 드라이브 연결 + `find()` + 깃 clone/pull (`https://github.com/yura103/deeplearning_5`) + `sys.path.insert(0, REPO)` — 04 첫 셀 복사.
- 결과 표는 `찍먹_실험기록/표/`에 csv(`utf-8-sig`), 모델은 `찍먹_실험기록/best/<이름>/`.
- 셀마다 위에 "무엇을, 왜" 한두 줄 (팀원이 읽는다).
