"""룰베이스 규칙 (담당: 룰베이스·LLM). notebooks/01_eda_알레르기_나트륨.ipynb C·D 파트를 그대로 옮김.

1) 음식 이름 → 레시피 매칭: 제목의 'with' 앞부분에 음식 이름이 있으면 후보,
   이름에 없는 '다른 요리 형태' 단어(soup, salad ...)가 붙으면 제외. ("Ramen Noodle Salad"는 ramen 아님)
2) 재료 → 한국 알레르기 표시 19항목: (포함 정규식, 제외 정규식)
   기준: 「식품 등의 표시·광고에 관한 법률 시행규칙」 [별표 2]
"""
import ast
import re

ALIAS = {'gyoza': ['gyoza', 'potsticker', 'pot sticker'], 'cup_cakes': ['cupcake'], 'hamburger': ['hamburger'],
         'french_fries': ['french fries'], 'spring_rolls': ['spring roll'], 'beef_tartare': ['beef tartare', 'steak tartare'],
         'eggs_benedict': ['eggs benedict', 'egg benedict'], 'macarons': ['macaron']}
FORMS = ['soup', 'salad', 'casserole', 'dip', 'sauce', 'stew', 'pie', 'sandwich', 'wrap', 'pizza', 'slaw', 'dressing',
         'chili', 'cake', 'bread', 'pasta', 'burger']

RULES = {  # 한국 알레르기 표시 19항목: (포함, 제외)
    '알류': ('(?<![a-z])eggs?(?![a-z])|mayonnaise|meringue|ladyfinger|savoiardi', ''),
    '우유': ('milk|cream|butter|cheese|yogurt|yoghurt|whey|ghee|custard'
           '|mascarpone|ricotta|mozzarella|parmesan|parmigiano|half-and-half|half and half',
           'coconut milk|almond milk|soy milk|oat milk|rice milk|coconut cream|cream of tartar|peanut butter|almond butter|cocoa butter|nut butter'),
    '메밀': ('buckwheat|soba', ''),
    '땅콩': ('peanut', ''),
    '대두': ('soy|tofu|edamame|miso|tempeh', ''),
    # 2026-11-17 추가 (서준영 정답지 ③: baklava·tiramisu 밀 놓침 = phyllo·ladyfingers 누락): 반죽·과자·파스타 모양 이름
    '밀': ('wheat|flour|bread|pasta|spaghetti|macaroni|couscous|noodle|cracker|panko|semolina|bulgur|soy sauce'
          '|phyllo|(?<![a-z])fill?o(?![a-z])|ladyfinger|savoiardi|pastry|pastries|dough|crust|crouton|biscuit|cookie|graham'
          '|(?<![a-z])cakes?(?![a-z])|tortilla|(?<![a-z])pitas?(?![a-z])|naan|bagel|croissant|wonton|seitan|spelt|farro'
          '|gnocchi|orzo|lasagn|ravioli|tortellini|fettuccin|linguin|penne|rigatoni|fusilli|udon',
          'rice flour|rice noodle|corn flour|cornflour|almond flour|coconut flour|chickpea flour|buckwheat flour|gluten-free|gluten free'
          '|rice cake|corn tortilla|cauliflower crust'),
    '고등어': ('mackerel', ''),
    '게': ('(?<![a-z])crab(?![a-z])|crabmeat|crab meat', ''),
    '새우': ('shrimp|prawn', ''),
    '돼지고기': ('(?<![a-z])(?:pork|bacon|ham)(?![a-z])|sausage|pepperoni|prosciutto|chorizo|pancetta|salami|lard', ''),
    '복숭아': ('peach', ''),
    '토마토': ('tomato|ketchup|salsa|marinara', ''),
    '아황산류': ('sulfite|sulphite|dried apricot|white wine|red wine', ''),
    '호두': ('walnut', ''),
    '닭고기': ('chicken', ''),
    '쇠고기': ('beef|steak|veal|brisket|sirloin|ribeye|short rib', ''),
    '오징어': ('squid|calamari', ''),
    '조개류': ('clam|oyster|mussel|scallop|abalone|shellfish|cockle', ''),
    '잣': ('pine nut|pinenut|pignoli', ''),
}


def rx(words):
    return '(?<![a-z])(?:' + '|'.join(re.escape(w.rstrip('s')) + 's?' for w in words) + ')(?![a-z])'


def match(titles, classes, alias=None):
    """제목 Series → {클래스: (이름만 일치 mask, 규칙 적용 후 mask)}. alias: 추가 별칭 {클래스: [이름...]}"""
    head = titles.fillna('').str.lower().str.split(' with ').str[0]  # 'with' 앞부분이 진짜 요리 이름
    alias = {**ALIAS, **(alias or {})}
    out = {}
    for c in classes:
        words = alias.get(c, [c.replace('_', ' ')])
        toks = {t.rstrip('s') for w in words for t in w.split()}
        bad = [f for f in FORMS if f not in toks]  # 이 음식 이름에 없는 '다른 요리 형태' 단어
        raw = head.str.contains(rx(words), regex=True)
        fin = raw & ~head.str.contains(rx(bad), regex=True)
        if c == 'dumplings':
            fin &= ~head.str.contains('and dumpling', regex=False)  # 미국식 치킨 앤 덤플링 제외
        out[c] = (raw, fin)
    return out


def ingredients_text(ner):
    """NER 칸("['eggs', 'flour']") → 'eggs , flour' (소문자)"""
    try:
        return ' , '.join(ast.literal_eval(ner)).lower()
    except Exception:
        return str(ner).lower()


def allergen_flags(text):
    """재료 문자열 Series → 레시피 × 19항목 True/False 표"""
    import pandas as pd
    return pd.DataFrame({k: (text.str.replace(exc, ' ', regex=True) if exc else text).str.contains(inc, regex=True)
                         for k, (inc, exc) in RULES.items()})


if __name__ == '__main__':  # 자체 검사: python -m knowledge.rules
    import pandas as pd
    t = pd.Series(['phyllo dough , walnuts , butter', 'ladyfingers , mascarpone , espresso', 'filo pastry , honey',
                   'corn tortillas , beef', 'rice cakes , gochujang', 'almond flour , sugar', 'cake flour , eggs',
                   'fillet of sole , lemon', 'pita bread', 'rice noodles , fish sauce', 'puff pastry , apples'])
    f = allergen_flags(t)
    assert f['밀'].tolist() == [True, True, True, False, False, False, True, False, True, False, True], f['밀'].tolist()
    assert f.loc[1, '알류'] and f.loc[1, '우유'] and f.loc[0, '호두']
    print('rules 자체 검사 통과')
