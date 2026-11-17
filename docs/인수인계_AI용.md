# 인수인계 (AI가 먼저 읽을 현재 상태) — 2026-11-17 기준

> AI 코딩 도구(Claude Code · Codex · Gemini)가 새 대화를 시작할 때 이 파일 → [`AGENTS.md`](../AGENTS.md)(규칙·함수 모양) → [`진행상황.md`](진행상황.md)(실험 숫자 전체) 순서로 읽는다.
> 이 파일은 "지금 어디까지 왔고 다음에 뭘 해야 하는지"만 적는다. 바뀌면 날짜와 함께 고친다.

## 1. 한 줄
찍먹: 음식 사진 → 분류(ConvNeXt-Base) 또는 레시피 검색(CLIP) → 레시피 100만 개 통계 → 한국 알레르기 19항목 **규칙**으로 🔴주의 / 🟡확인 필요 / ⚪해당 없음 + 영양. LLM은 판정하지 않고 이름·재료 추정, 교차 확인, 설명만 한다.

## 2. 사람과 담당 (원래 분담 기준)
| 사람 | 담당 | 지금 상태 |
|---|---|---|
| 박중현 | 학습 ② CLIP, 2단계 검색, 앱 연결 | 04·04-2·04-3 완료, `search.py`·`crosscheck` 완료, 06(코랩 전체 실행) 1회 성공. 05-2(공정 비교)도 만듦. 04-4 노트북 완성 → 실행 대기 |
| 주한솔 | 학습 ① 분류 모델, 보정, 처음 보는 음식 감지 | ConvNeXt-Base 학습 완료(test 93.37%), `notebooks/05` 실행 완료 (T=0.838). **앱에 반영됨** |
| 김유라 | LLM, 배포 | `llm/` 함수 main에 있음. 배포는 학과 서버 대신 **노트북 + ngrok** 준비 중. 남은 것: 금지어 필터, 이미지 입력 확인 |
| 서준영 | 평가(정답지), 화면, **LLM API 키** | 정답지·FN 비교 **아직 시작 안 함 (가장 큰 공백)**. 키 발급·관리도 준영 담당 |

## 3. 앱 흐름 (코드 기준)
1. `modeling/model.py` `predict` → 상위 3개 (클래스, **보정된** 확률). 보정: logit / temperature (`modeling/calibration.json`의 `model`이 불러온 모델과 같을 때만)
2. `knowledge/judge.py` `analyze`:
   - 1등 ≥ `T_ONE`(0.95) → `1단계-1등`: 표(`food_table.csv`) 비율 한 줄
   - ≥ `T_KNOWN`(0.6) → `1단계-합치기`: 상위 3개 표 비율 중 **가장 위험한 쪽(최대값)**. 검색 목록이 있으면 CLIP 2단계 결과도 합침 → `1단계-합치기+CLIP`
   - 그 아래 → `2단계`: `stage2()`
3. `backend/main.py` `stage2`: LLM `guess_name`(병렬) + `search.search`(기본 CLIP, 레시피 top-30 → 비율) → `search.crosscheck` (LLM 이름이 CLIP 상위 3개와 다르면 그 음식의 근거를 **`확인 필요`(0.5)까지만** 올림)
4. 판정: 비율 ≥0.6 주의, ≥0.2 확인 필요, 레시피 <30개면 정보 부족
5. 응답에 `candidates`, `similar`, `llm_guess`, `explanation`(LLM, 최대 15초) 추가

## 4. 이번에 정한 것 (2026-11-17)
| 결정 | 내용 | 이유 |
|---|---|---|
| 분류 모델 | 한솔 **ConvNeXt-Base** (timm `convnext_base.fb_in22k_ft_in1k`, EMA) | test top-1 93.37% / top-5 99.10% (Tiny 88.8%). CPU 458ms/장, 메모리 문제 없음 |
| `model.py` | 내 버전(종류별 전처리, 보정 가드) + 유라 버전(가중치 모양으로 tiny/small/base/large 판별, `_orig_mod.`/`module.` 접두어 제거) 합침 | 둘 다 장점이라 합침 |
| 보정 | T = 0.838 (T<1: 모델이 **덜** 확신함) → ECE 0.065 → 0.017, NLL 0.307 → 0.259 | 한솔 05 |
| 기준값 | `T_ONE, T_KNOWN = 0.95, 0.6` (한솔 제안은 0.8 / 0.6) | 한솔 05 표 A(검증, 음식 단위로 나눈 처음 보는 음식): T_ONE 0.8이면 처음 보는 음식의 **42.7%가 1단계로 샘** → 엉뚱한 음식 표로 판정. 0.95면 22.8%. 대신 아는 음식 1단계 비율 87.3% → 74.1% (나머지는 합치기+CLIP으로 가서 경고가 조금 늘 뿐 안전). 알레르기 앱은 놓침이 더 위험하므로 0.95. **한솔님과 합의 필요**, 바꾸려면 `judge.py` 한 줄 + `calibration.json` |
| 노트북 05 | 한솔 버전이 공식 `05_분류모델_보정_감지.ipynb`. 내 것은 `05-2_감지_공정비교.ipynb` | 한솔 것이 검증 7,575 / 시험 25,250장 전체, 음식 단위 분리. 05-2는 같은 도메인(레시피 사진끼리) 공정 비교용 |
| 처음 보는 음식 감지 | 확신도(MSP)로 충분, energy가 더 낫지 않음 (AUROC 0.880 vs 0.859) | 한솔 05. 단 이건 Food-101 사진 vs 레시피 사진이라 부풀려졌을 수 있음. 05-2(Tiny, 같은 도메인)에서는 AUROC ≈0.66 → **확신도만으로는 약하다** → 그래서 합치기 구간에도 CLIP을 붙임 |
| 배포 | 유라 노트북 + ngrok | 학과 서버는 외부 공개가 막힘. 사진 버튼(`<input type=file capture>`)은 http에서도 카메라 열림 (https 필수 아님) |

## 5. 확인된 것 / 안 된 것
- ✅ 06 (코랩 CPU, Tiny 모델, LLM 키 없이): 서버·자체 검사·`/analyze` 끝까지 동작. 라멘 → 밀 주의 2.8초
- ❌ 06에서 카오소이(처음 보는 음식) → 치킨 커리 0.61로 착각, CLIP도 세비체로 찾음 → 밀 놓침. 대응으로 합치기+CLIP, 기준값 상향(0.95/0.6)을 넣음. **Base + 새 기준값으로 06 재실행은 아직 안 함** (유라님 배포 후 확인 예정)
- ❓ LLM 경로 (키 필요, 준영 담당): 교차 확인·설명이 실제로 나오는지 미확인
- ❓ `explain`의 '안전' 금지어 필터가 설명을 너무 자주 버릴 가능성 (유라)

## 6. 다음 할 일 (우선순위)
0. ✅ **`notebooks/03-2` 실행 완료, `food_table.csv` 새 규칙으로 교체** (진행상황 13). 앱 서버는 드라이브 `clip_base/index_meta.parquet` 다시 복사할 것. 아래는 원래 메모: `rules.py` 밀 규칙에 phyllo·ladyfingers·pastry·파스타 이름 등 추가(준영 ③에서 baklava·tiramisu 밀 놓침 417칸이 규칙 누락이었음), 우유에 mascarpone·parmesan 등, 알류에 ladyfingers. 결과 `표/food_table_v2.csv` → 깃 `knowledge/food_table.csv`로 반영, `clip_base/index_meta.parquet` 19항목도 갱신(예전 것 `index_meta_v1.parquet`). 그다음 준영 ③ 채점을 새 표 + Base 설정으로 다시
1. **서준영: 알레르기 정답지 20~30종 → 룰 vs LLM 직접 판정의 주의놓침(FN) 비교** — 발표의 핵심 숫자인데 아직 없음
2. 서준영: LLM API 키를 코랩 Secrets / `.env`에 넣어 06 재실행 (Base + 0.95/0.6 + LLM)
3. 박중현: `notebooks/04-4_CLIP_LLM_교차확인_비교.ipynb` **실행** (노트북 완성, 코랩 CPU + LLM 키). 처음 보는 음식 74종×5장 / 아는 음식 101종×2장, 자기 레시피 글은 검색에서 뺌. ① 2단계만: CLIP만 vs CLIP+LLM ② 앱 전체: T_ONE 0.8/0.95 × LLM 끔/켬. 결과 `찍먹_실험기록/표/04-4_*.csv`, LLM 답은 `찍먹_실험기록/llm_cache_04-4/`(이어 돌리기)
4. 김유라: ngrok 배포, 금지어 필터를 단정 표현만 거르게, `python -m llm.check 사진.jpg`로 이미지 입력 확인
5. 주한솔: T_ONE 0.95 vs 0.8 합의

## 7. 지키는 규칙 (요약, 자세한 건 AGENTS.md)
- 레시피 원문·제목(`index_meta.parquet` 포함), 사진, 모델 가중치는 **깃에 안 올림** (재배포 금지)
- API 키·서버 계정은 `.env` / 코랩 Secrets에만. 깃·노션·화면에 출력 금지
- 무거운 실행(학습·검색 목록·앱 전체)은 **코랩**에서. 사용자 PC에서 스크립트 돌리지 않기
- push는 사용자(박중현)가 "push 해"라고 할 때만
- 분류 모델 학습 코드는 한솔 담당 — 다른 사람이 추가하지 않음
- 노트북 결과는 드라이브 `찍먹_실험기록/` (공유, 각자 담당 노트북만 돌릴 것 — 덮어쓰기 주의)

## 8. 파일 지도 (자주 보는 것)
| 파일 | 역할 |
|---|---|
| `modeling/model.py`, `modeling/calibration.json`, `modeling/classes.txt` | 분류 모델 불러오기·보정·예측 |
| `knowledge/judge.py` | 단계 나누기·합치기·판정 (기준값 상수) + 자체 검사 |
| `knowledge/search.py` | CLIP 레시피 검색 + LLM 교차 확인 + 자체 검사 |
| `knowledge/lookup.py`, `rules.py`, `food_table.csv` | 표 한 줄, 재료→19항목 규칙, 175종 비율표 |
| `llm/client.py`, `guess.py`, `explain.py`, `check.py` | LLM 호출(Gemini 기본, `LLM_PROVIDER=groq`면 Qwen), 이름/재료 추정, 설명, 연결 확인 |
| `backend/main.py`, `frontend/index.html` | API·화면 |
| `notebooks/04*` | CLIP 실험·검색 목록 / `05` 보정(한솔) / `05-2` 공정 비교 / `06` 코랩 앱 전체 실행 |
| 드라이브 `찍먹_실험기록/best/convnext_base/best.pt` | 앱 분류 모델 → 로컬 `modeling/weights/best.pt` |
| 드라이브 `찍먹_실험기록/best/clip_base/` | 검색 목록 두 파일 → 로컬 `knowledge/index/` |
