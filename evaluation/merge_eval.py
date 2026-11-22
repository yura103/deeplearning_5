"""③ 1등만 vs 후보 합치기: 알레르기 경고를 몇 번 놓치나 (담당: 서준영)

입력  convnext_test_top5.csv  notebooks/06이 만든 파일. Food-101 시험 사진마다 ConvNeXt 상위 5개 음식과 확률
      evaluation/정답지.csv   사람이 확인한 정답 (음식 × 19항목, 1 = 보통 들어감)
출력  evaluation/합치기_결과.md, evaluation/합치기_결과.csv

정답지 음식 중 Food-101 시험 사진이 있는 것만 쓴다. 사진 한 장마다 19항목을 모두 판정해서
(사진, 항목) 칸 하나하나를 정답과 비교한다. 비교하는 방식은 4가지다.
  정답 음식을 알 때 : 사진 AI가 100% 맞혔다고 치면 (표·룰 자체의 오차만 남음)
  1등만             : 사진 AI 1등 음식만 믿음
  우리 방식         : knowledge/judge.analyze 그대로 (1등 확률로 1등만 / 상위 3개 합치기 / 2단계).
                      2단계 CLIP 검색은 사진이 필요해서 넣지 않음 → 2단계는 '확인 필요'
  항상 합치기       : 언제나 상위 3개 합치기

실행 (저장소 루트):  python -m evaluation.merge_eval <convnext_test_top5.csv 경로>
"""
import csv
import sys
from collections import Counter
from pathlib import Path

from knowledge.judge import CAUTION, CHECK, MIN_RECIPES, T_KNOWN, T_ONE, analyze, judge, merge
from knowledge.lookup import ALLERGENS, row

HERE = Path(__file__).parent
ANSWER, OUT_MD, OUT_CSV = HERE / '정답지.csv', HERE / '합치기_결과.md', HERE / '합치기_결과.csv'
K = 3  # 합치는 후보 수 (judge.analyze와 같음)

# (정답, 판정) → 칸 종류
KIND = {1: {'주의': '맞음', '확인 필요': '약하게', '정보 부족': '약하게', '해당 없음': '놓침'},
        0: {'주의': '괜한 주의', '확인 필요': '괜한 확인', '정보 부족': '맞음', '해당 없음': '맞음'}}
COLS = ['놓침', '약하게', '괜한 주의', '괜한 확인']


def verdicts(foods):
    """음식 이름들 → {항목: 단계}. 여러 개면 judge.merge로 '가장 위험한 쪽'으로 합친다."""
    rows = [r for c in foods if (r := row(c))]
    if not rows:
        return {a: '확인 필요' for a in ALLERGENS}  # 표에 없는 음식 = 2단계 자리 (analyze와 같게)
    return judge(merge(rows), ALLERGENS)['verdict']


POLICIES = {
    '정답 음식을 알 때': lambda p: verdicts([p['true']]),
    '1등만': lambda p: verdicts([p['cands'][0][0]]),
    '우리 방식': lambda p: analyze(p['cands'][:K], ALLERGENS)['verdict'],
    '항상 합치기': lambda p: verdicts([c for c, _ in p['cands'][:K]]),
}


def load(pred_path):
    with open(ANSWER, encoding='utf-8-sig') as f:
        sheet = {r['class']: {a: int(r[a]) for a in ALLERGENS} for r in csv.DictReader(f)}
    with open(pred_path, encoding='utf-8-sig') as f:
        preds = [dict(true=r['true'], cands=[(r[f'c{k}'], float(r[f'p{k}'])) for k in range(1, 6)])
                 for r in csv.DictReader(f)]
    preds = [p for p in preds if p['true'] in sheet]
    assert preds, '정답지 음식의 시험 사진이 하나도 없음 (예측 파일·정답지 확인)'
    return sheet, preds


def score(sheet, preds):
    """방식마다 칸 종류 개수 + 1등이 틀린 사진만 따로 + 놓침이 생긴 (실제 → 1등, 항목) 개수
    + 놓침 원인 (정답 음식을 알아도 놓치는 칸이면 '표·룰 탓', 아니면 '사진 AI 탓')."""
    oracle = [POLICIES['정답 음식을 알 때'](p) for p in preds]
    res = {}
    for name, fn in POLICIES.items():
        all_, wrong, why, cause = Counter(), Counter(), Counter(), Counter()
        for p, o in zip(preds, oracle):
            v, top1 = fn(p), p['cands'][0][0]
            for a in ALLERGENS:
                k = KIND[sheet[p['true']][a]][v[a]]
                all_[k] += 1
                if top1 != p['true']:
                    wrong[k] += 1
                if k == '놓침':
                    why[(p['true'], top1 if name != '정답 음식을 알 때' else p['true'], a)] += 1
                    cause['표·룰 탓' if o[a] == '해당 없음' else '사진 AI 탓'] += 1
        res[name] = dict(all=all_, wrong=wrong, why=why, cause=cause)
    return res


def pct(a, b):
    return f'{a / b:.1%}' if b else '-'


def table(res, part, pos, neg):
    lines = ['| 방식 | 놓침 ↓ | 약하게 | 괜한 주의 ↓ | 괜한 확인 |', '|---|---|---|---|---|']
    for name, r in res.items():
        c = r[part]
        lines.append(f"| {name} | **{c['놓침']}** ({pct(c['놓침'], pos)}) | {c['약하게']} ({pct(c['약하게'], pos)}) "
                     f"| {c['괜한 주의']} ({pct(c['괜한 주의'], neg)}) | {c['괜한 확인']} ({pct(c['괜한 확인'], neg)}) |")
    return lines


def main(pred_path):
    sheet, preds = load(pred_path)
    foods = sorted({p['true'] for p in preds})
    wrong = [p for p in preds if p['cands'][0][0] != p['true']]
    pos = sum(sum(sheet[p['true']].values()) for p in preds)
    neg = len(preds) * len(ALLERGENS) - pos
    wpos = sum(sum(sheet[p['true']].values()) for p in wrong)
    wneg = len(wrong) * len(ALLERGENS) - wpos
    route = Counter(analyze(p['cands'][:K], ALLERGENS)['route'] for p in preds)
    res = score(sheet, preds)

    md = [
        '# ③ 1등만 vs 후보 합치기 결과',
        '',
        '> 자동 생성 파일. `python -m evaluation.merge_eval <convnext_test_top5.csv>`로 다시 만든다. 읽는 법은 맨 아래.',
        '',
        f'- 사진: Food-101 시험 사진 중 정답지 음식 {len(foods)}종, **{len(preds):,}장** (사진 AI 1등이 틀린 사진 {len(wrong):,}장, {pct(len(wrong), len(preds))})',
        f'- 칸: 사진 × 19항목 = {len(preds) * len(ALLERGENS):,}칸. 정답 1(들어감) {pos:,}칸, 정답 0 {neg:,}칸',
        f'- 기준 (`knowledge/judge.py`): 주의 ≥{CAUTION}, 확인 필요 ≥{CHECK}, 레시피 {MIN_RECIPES}개 미만이면 정보 부족, '
        f'1등 확률 ≥{T_ONE}이면 1등만 · ≥{T_KNOWN}이면 상위 {K}개 합치기 · 그 아래는 2단계',
        '- 우리 방식이 간 길: ' + ', '.join(f'{k} {v:,}장' for k, v in sorted(route.items())),
        '',
        '## 전체 사진',
        *table(res, 'all', pos, neg),
        '',
        '## 놓침을 원인별로',
        '- **표·룰 탓**: 정답 음식을 알아도 놓치는 칸이다. 레시피 통계표나 재료 규칙을 고쳐야 줄어든다. '
        '이번 정답지에서는 ' + (', '.join(f'{t} {a}' for (t, _, a) in res['정답 음식을 알 때']['why']) or '없음') + '.',
        '- **사진 AI 탓**: 음식을 잘못 봐서 놓친 칸이다. **합치기가 줄이려는 것이 이것이다.**',
        '',
        '| 방식 | 놓침 | 표·룰 탓 | 사진 AI 탓 ↓ |',
        '|---|---|---|---|',
        *[f"| {name} | {r['all']['놓침']} | {r['cause']['표·룰 탓']} | **{r['cause']['사진 AI 탓']}** |"
          for name, r in res.items()],
        '',
        '(합친 후보 중에 그 항목이 높은 음식이 있으면 표·룰 탓 칸도 우연히 잡힌다. 그래서 합치는 방식은 표·룰 탓이 '
        f"{res['정답 음식을 알 때']['all']['놓침']}보다 작다.)",
        '',
        f'## 사진 AI 1등이 틀린 사진만 ({len(wrong):,}장)',
        '합치기는 1등이 틀렸을 때 효과가 난다. 1등이 맞은 사진에서는 "1등만"과 "우리 방식"이 대부분 같다.',
        '',
        *table(res, 'wrong', wpos, wneg),
        '',
        '## 놓침이 어디서 났나 (많은 순 10개)',
    ]
    for name in ('1등만', '우리 방식'):
        md += ['', f'**{name}**', '', '| 실제 음식 | 사진 AI 1등 | 항목 | 놓친 사진 수 |', '|---|---|---|---|']
        md += [f'| {t} | {p} | {a} | {n} |' for (t, p, a), n in res[name]['why'].most_common(10)] or ['| (없음) | | | |']
    md += [
        '',
        '## 읽는 법',
        '| 칸 종류 | 정답 | 앱 판정 | 뜻 |',
        '|---|---|---|---|',
        '| **놓침** | 1 (들어감) | 해당 없음 | 위험한데 "괜찮다"고 함. **제일 나쁨, 줄여야 하는 숫자** |',
        '| 약하게 | 1 | 확인 필요 · 정보 부족 | 경고는 했지만 약하게 |',
        '| **괜한 주의** | 0 (안 들어감) | 주의 | 괜히 겁줌. 많으면 사람들이 경고를 무시함 |',
        '| 괜한 확인 | 0 | 확인 필요 | 괜히 확인하라고 함 (주의보다는 덜 나쁨) |',
        '',
        '- 놓침·약하게 비율은 정답 1인 칸 수로, 괜한 주의·괜한 확인 비율은 정답 0인 칸 수로 나눈 것이다.',
        '- "정답 음식을 알 때" 줄은 사진 AI가 완벽해도 남는 오차다 (레시피 통계표·룰 자체의 오차).',
        '  나머지 줄과의 차이가 **사진 AI가 음식을 잘못 봐서 생긴 오차**다.',
        '- 2단계(1등 확률이 낮음)로 간 사진은 이 채점에서 모든 항목을 "확인 필요"로 둔다. 그래서 놓침이 0이 되고 "괜한 확인"이 늘어난다.',
        '  실제 앱은 2단계에서 CLIP 검색(`knowledge/search.py`)으로 판정하는데, 사진과 검색 목록이 있어야 해서 이 채점에는 넣지 않았다.',
        '- 정답지에 정답 1이 없는 고등어·복숭아·잣은 놓침을 잴 수 없고 괜한 주의만 잴 수 있다.',
        '',
    ]
    OUT_MD.write_text('\n'.join(md), encoding='utf-8')

    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['사진', '방식', *COLS, '정답1_칸', '정답0_칸', '놓침_표룰탓', '놓침_사진AI탓'])
        for part, label, p_, n_ in (('all', '전체', pos, neg), ('wrong', '1등 틀림', wpos, wneg)):
            for name, r in res.items():
                cause = [r['cause']['표·룰 탓'], r['cause']['사진 AI 탓']] if part == 'all' else ['', '']
                w.writerow([label, name, *(r[part][k] for k in COLS), p_, n_, *cause])
    print('\n'.join(table(res, 'all', pos, neg)))
    print(f'\n저장 → {OUT_MD.name}, {OUT_CSV.name}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('사용법: python -m evaluation.merge_eval <convnext_test_top5.csv 경로>')
    main(sys.argv[1])
