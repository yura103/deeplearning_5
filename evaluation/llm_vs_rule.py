"""② 우리 방식 vs 그냥 AI: 알레르기 경고를 몇 번 놓치나 (담당: 서준영)

  우리 방식 : 레시피 통계표 + 룰. knowledge.lookup.row(음식) → knowledge.judge.judge (앱과 같음)
  그냥 AI   : AI에게 재료를 물음. llm.guess.guess_ingredients(음식 이름) → 재료 목록 → 같은 룰
              (knowledge.rules.allergen_flags)로 항목을 찾는다. 들어 있으면 '주의', 없으면 '해당 없음'.
              AI의 답(재료)만 다르고 재료 → 항목 규칙은 똑같다. 그래서 차이는 '재료를 어디서 얻나'에서만 난다.
  정답      : evaluation/정답지.csv 28종 × 19항목 (사람 확인 완료)

- 사진은 쓰지 않고 음식 이름으로만 비교한다. 사진 AI 오차는 ③(merge_eval)에서 따로 쟀다.
- AI 답은 물을 때마다 다를 수 있다. 그래서 --runs번 묻고, 회차마다 답이 달라진 칸 수도 센다.
- AI 답은 전부 evaluation/llm_답변.csv에 남긴다 (사람이 볼 수 있게, 같은 답으로 다시 채점할 수 있게).
  저장된 답이 있으면 다시 묻지 않는다. 새로 물으려면 --again.
- 유라님 함수가 아직 None을 돌려주면(연결 전) 그렇다고 알리고 끝난다.

실행 (저장소 루트):  python -m evaluation.llm_vs_rule [--runs 3] [--again]
출력: evaluation/LLM비교_결과.md, evaluation/LLM비교_결과.csv, evaluation/llm_답변.csv
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from evaluation.merge_eval import COLS, KIND
from knowledge.judge import CAUTION, CHECK, MIN_RECIPES, judge
from knowledge.lookup import ALLERGENS, row
from knowledge.rules import allergen_flags
from llm import guess

HERE = Path(__file__).parent
ANSWER = HERE / '정답지.csv'
ASKED, OUT_MD, OUT_CSV = HERE / 'llm_답변.csv', HERE / 'LLM비교_결과.md', HERE / 'LLM비교_결과.csv'
SEP = ' ; '  # llm_답변.csv에서 재료 구분


def load_sheet():
    with open(ANSWER, encoding='utf-8-sig') as f:
        return {r['class']: {a: int(r[a]) for a in ALLERGENS} for r in csv.DictReader(f)}


def ask(foods, runs, again):
    """{(회차, 음식): [재료] 또는 None}. 저장된 답을 먼저 쓰고, 모자란 것만 유라님 함수로 묻는다."""
    got = {}
    if ASKED.exists() and not again:
        with open(ASKED, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                got[(int(r['run']), r['class'])] = r['ingredients'].split(SEP) if r['ok'] == '1' else None
    todo = [(k, c) for k in range(1, runs + 1) for c in foods if (k, c) not in got]
    for n, (k, c) in enumerate(todo, 1):
        ans = guess.guess_ingredients(c.replace('_', ' '))
        got[(k, c)] = [str(x).strip() for x in ans if str(x).strip()] or None if ans else None
        print(f'\r물어보는 중 {n}/{len(todo)}', end='', flush=True)
    if todo:
        print()
    if not any(got.values()):  # 저장 안 함: 연결 전 빈 답을 남기지 않게
        sys.exit('llm.guess.guess_ingredients가 모든 음식에 None을 돌려줍니다 (유라님 연결 전). 연결되면 다시 실행하세요.')
    keep = {(k, c): v for (k, c), v in got.items() if k <= runs and c in foods}
    with open(ASKED, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['run', 'class', 'ok', 'ingredients'])
        for (k, c), v in sorted(keep.items(), key=lambda x: (x[0][0], foods.index(x[0][1]))):
            w.writerow([k, c, int(v is not None), SEP.join(v or [])])
    return keep


def ai_verdicts(ingredients):
    """재료 목록 → {항목: '주의' | '해당 없음'} (앱의 재료 → 항목 규칙 그대로)."""
    text = pd.Series([' , '.join(ingredients).lower()])
    flags = allergen_flags(text).iloc[0]
    return {a: '주의' if flags[a] else '해당 없음' for a in ALLERGENS}


def count(sheet, verdicts):
    """{음식: {항목: 단계}} → 칸 종류 개수, 놓친 칸 목록."""
    c, missed = Counter(), []
    for food, v in verdicts.items():
        for a in ALLERGENS:
            k = KIND[sheet[food][a]][v[a]]
            c[k] += 1
            if k == '놓침':
                missed.append((food, a))
    return c, missed


def pct(a, b):
    return f'{a / b:.1%}' if b else '-'


def main(runs, again):
    sheet = load_sheet()
    foods = list(sheet)
    answers = ask(foods, runs, again)

    ours = {f: judge(row(f), ALLERGENS)['verdict'] for f in foods}
    results = [('우리 방식 (레시피 통계 + 룰)', ours, len(foods))]
    ai_runs = {}
    for k in range(1, runs + 1):
        v = {f: ai_verdicts(answers[(k, f)]) for f in foods if answers.get((k, f))}
        ai_runs[k] = v
        results.append((f'그냥 AI {k}회차', v, len(v)))

    md = [
        '# ② 우리 방식 vs 그냥 AI 결과',
        '',
        '> 자동 생성 파일. `python -m evaluation.llm_vs_rule`로 다시 만든다. AI 답 원문은 `llm_답변.csv`.',
        '',
        f'- 음식: 정답지 {len(foods)}종 × 19항목. 음식 이름으로만 비교한다 (사진 AI 오차는 ③에서 따로).',
        f'- 우리 방식 기준 (`knowledge/judge.py`): 주의 ≥{CAUTION}, 확인 필요 ≥{CHECK}, 레시피 {MIN_RECIPES}개 미만이면 정보 부족',
        '- 그냥 AI: `llm.guess.guess_ingredients(음식 이름)`이 말한 재료를 같은 룰(`rules.allergen_flags`)로 읽는다. '
        '들어 있으면 주의, 없으면 해당 없음 (AI는 "확인 필요"를 내지 않는다).',
        '',
        '| 방식 | 답한 음식 | 놓침 ↓ | 약하게 | 괜한 주의 ↓ | 괜한 확인 |',
        '|---|---|---|---|---|---|',
    ]
    rows_csv, missed_by = [], {}
    for name, v, n in results:
        c, missed = count(sheet, v)
        pos = sum(sum(sheet[f].values()) for f in v)
        neg = len(v) * len(ALLERGENS) - pos
        missed_by[name] = missed
        md.append(f"| {name} | {n}/{len(foods)} | **{c['놓침']}** ({pct(c['놓침'], pos)}) | {c['약하게']} ({pct(c['약하게'], pos)}) "
                  f"| {c['괜한 주의']} ({pct(c['괜한 주의'], neg)}) | {c['괜한 확인']} ({pct(c['괜한 확인'], neg)}) |")
        rows_csv.append([name, n, *(c[k] for k in COLS), pos, neg])

    # 회차마다 AI 답이 달라진 칸 (같은 음식·항목인데 주의 ↔ 해당 없음이 바뀜)
    common = [f for f in foods if all(f in v for v in ai_runs.values())]
    flip = [(f, a) for f in common for a in ALLERGENS if len({v[f][a] for v in ai_runs.values()}) > 1]
    md += ['', f'- AI가 {runs}번 답하는 동안 판정이 바뀐 칸: **{len(flip)}칸** (두 번 이상 다 답한 음식 {len(common)}종 기준)'
           + (': ' + ', '.join(f'{f} {a}' for f, a in flip[:15]) + (' …' if len(flip) > 15 else '') if flip else '')]

    md += ['', '## 놓친 칸 (정답 1인데 해당 없음)']
    for name, missed in missed_by.items():
        md.append(f'- **{name}** ({len(missed)}칸): ' + (', '.join(f'{f} {a}' for f, a in missed) or '없음'))
    md += [
        '',
        '## 읽는 법',
        '- 놓침: 정답 1(보통 들어감)인데 "해당 없음". 위험한데 괜찮다고 한 것. **제일 나쁨.**',
        '- 괜한 주의: 정답 0인데 "주의". 많으면 사람들이 경고를 무시한다.',
        '- 놓침·약하게 비율은 정답 1인 칸 수로, 괜한 주의·괜한 확인 비율은 정답 0인 칸 수로 나눈 것이다.',
        '- 그냥 AI가 답하지 못한 음식(None)은 그 회차에서 뺐다. "답한 음식" 칸을 같이 볼 것.',
        '',
    ]
    OUT_MD.write_text('\n'.join(md), encoding='utf-8')
    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['방식', '답한_음식', *COLS, '정답1_칸', '정답0_칸'])
        w.writerows(rows_csv)
    print('\n'.join(md[8:10 + len(results)]))
    print(f'저장 → {OUT_MD.name}, {OUT_CSV.name}, {ASKED.name}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='② 우리 방식 vs 그냥 AI')
    p.add_argument('--runs', type=int, default=3, help='AI에게 몇 번 물을지 (기본 3)')
    p.add_argument('--again', action='store_true', help='저장된 답을 버리고 새로 물음')
    a = p.parse_args()
    main(a.runs, a.again)
