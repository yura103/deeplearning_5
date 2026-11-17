"""백엔드: 사진 + 내 알레르기 → 판정 결과 JSON.

실행 (저장소 루트에서):  uvicorn backend.main:app --reload
앱 화면:                 http://localhost:8000
문서/테스트 화면:        http://localhost:8000/docs
"""
import io
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from knowledge import search
from knowledge.judge import analyze
from knowledge.lookup import ALLERGENS
from llm.explain import explain
from llm.guess import guess_ingredients, guess_name
from modeling.model import WEIGHTS, load_model, predict

MAX_BYTES = 10 * 1024 * 1024  # 폰 사진 넉넉히
EXPLAIN_SECONDS = 15          # 설명(LLM)을 이 이상 기다리지 않음 → explanation None
_POOL = ThreadPoolExecutor(max_workers=4)

app = FastAPI(title='찍먹')


@lru_cache(maxsize=1)
def model():
    """첫 요청 때 한 번만 불러옴 (서버 켜는 속도 유지)."""
    if not WEIGHTS.exists():
        raise HTTPException(503, f'모델 가중치 없음: 드라이브 찍먹_실험기록/best/convnext_base/best.pt (한솔 최고 모델) → {WEIGHTS}')
    return load_model()


@app.on_event('startup')
def warm_up():
    """서버가 켜지면 뒤에서 모델을 미리 불러옴 (06: 첫 2단계 검색이 CLIP 받기·불러오기로 32초). 서버는 기다리지 않고 바로 뜸.
    ponytail: 불러오는 도중 들어온 첫 요청은 한 번 더 불러올 수 있음 (lru_cache에 잠금 없음) — 문제 되면 Lock 추가."""
    if WEIGHTS.exists():
        _POOL.submit(model)
    if search.available():
        _POOL.submit(search._load)


@app.get('/allergens')
def allergens():
    """화면의 알레르기 체크박스 목록 (19개)."""
    return ALLERGENS


@app.post('/analyze')
def analyze_photo(image: UploadFile = File(...), allergens: str = Form('')):
    """allergens: 쉼표로 구분 (예: '밀,땅콩'). async 아님 → 모델 계산이 다른 요청을 막지 않음."""
    data = image.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, '사진이 10MB보다 큼')
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, '사진 파일이 아님')

    mine = [a.strip() for a in allergens.split(',') if a.strip()]
    cands = predict(model(), img)
    guesses, hits = [], []

    def clip():
        """CLIP 검색 (요청마다 한 번만). 1등 확률이 높아도 먼저 봄: 소바→ramen 0.97 같은 착각 확인용 (judge.clip_says_new)"""
        if not hits:
            hits.append(search.search(img))
        return hits[0]

    def stage2():
        """처음 보는 음식·애매한 음식: CLIP 검색 + LLM 이름 추정 → 교차 확인. LLM 실패면 CLIP만."""
        job = _POOL.submit(guess_name, img)
        hit = clip()
        guesses[:] = _wait(job) or []
        return search.crosscheck(hit, guesses, lambda n: _wait(_POOL.submit(guess_ingredients, n)))

    try:
        ok = search.available()  # 검색 목록(knowledge/index/) 있을 때만
        result = analyze(cands, mine, stage2 if ok else None, clip if ok else None)
    except ValueError as e:  # 모르는 알레르기 이름
        raise HTTPException(400, str(e))
    result['candidates'] = [{'food': c, 'prob': round(p, 4)} for c, p in cands]
    result['llm_guess'] = [{'food': n, 'conf': round(c, 2)} for n, c in guesses]
    result['explanation'] = _wait(_POOL.submit(explain, (result['foods'] or [cands[0][0]])[0], result))
    return result


def _wait(job):
    """LLM 결과를 EXPLAIN_SECONDS까지만 기다림. 느리거나 안 되면 None — 판정 결과는 그대로 나간다."""
    try:
        return job.result(timeout=EXPLAIN_SECONDS)
    except Exception:  # 시간 초과·LLM 오류
        return None


# 화면 (frontend/index.html). API 경로보다 뒤에 둬야 /analyze 등을 가리지 않음
app.mount('/', StaticFiles(directory=Path(__file__).parent.parent / 'frontend', html=True), name='frontend')
