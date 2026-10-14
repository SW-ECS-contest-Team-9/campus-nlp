"""미세조정 자료 만들기: (입력 문장 + 꾸러미 장소 일부) → 이름 기반 JSON.
- dev 금 문장(사람 말투 합성) + 틀 문장 증강(건물·층·조건 조합). test 문장과 같은 문장은 뺀다.
- 출력: llm/out/train.jsonl, llm/out/val.jsonl ({"messages": [...]}).
SYNTHETIC 자료.
"""
import json, random, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PKG, ROOT, SYSTEM, build_prompt, load_gold, target_output  # noqa: E402

random.seed(7)
OUT = ROOT / 'llm' / 'out'
FLOORS = {}
for f in PKG['floors']:
    FLOORS.setdefault(f['buildingKey'], []).append(f['code'])
BUILD = [b for b in PKG['buildings']]

DEST_T = ['{d} 가는 길', '{d} 어떻게 가', '{d}까지 안내해 줘', '{d}로 가자', '{d} 가려면?', '{d} 길 좀', '{d} 어디야', '{d} 빨리']
ORIG_T = ['{o}에서 {d}까지', '{o}에서 {d} 가는 길', '{o}부터 {d}']
COND = [  # (문구, mandatory, preferences, unsupported, elevator)
    ('', [], [], [], False), ('', [], [], [], False), ('', [], [], [], False),
    ('계단 없이', ['avoidStairs'], [], [], False), ('계단 말고', ['avoidStairs'], [], [], False),
    ('유모차 끌고', ['avoidStairs'], [], [], False), ('다리 다쳐서', ['avoidStairs'], [], [], False),
    ('휠체어로', ['avoidStairs', 'wheelchairNeeded'], [], ['wheelchair'], False),
    ('엘베 타고', [], [], [], True), ('엘리베이터로', [], [], [], True),
    ('짐이 많아서', [], ['fewerStairs'], [], False), ('피곤해서', [], ['fewerStairs'], [], False),
    ('실내로', [], ['indoor'], [], False), ('추워서 건물 안으로', [], ['indoor'], [], False),
    ('비 와서', [], [], ['covered'], False), ('조용한 길로', [], [], ['quiet'], False),
    ('사람 적은 길로', [], [], ['crowd'], False), ('그늘로', [], [], ['shade'], False),
    ('계단으로 빨리', [], [], [], False), ('계단 괜찮아', [], [], [], False),
]


def floor_text(code):
    if code.startswith('B'):
        return random.choice(['지하 ' + code[1:] + '층', code, '지하' + code[1:] + '층'])
    return random.choice([code[:-1] + '층', code[:-1] + '층'])


def synth(n):
    rows = []
    for _ in range(n):
        b = random.choice(BUILD)
        name = random.choice([b['name']] + [a for a in b['aliases'] if a.endswith('관')])
        dk = {'placeKey': None, 'buildingKey': b['key'], 'floorKey': None}
        d = name
        if b['key'] in FLOORS and random.random() < 0.4:
            code = random.choice(FLOORS[b['key']])
            d += ' ' + floor_text(code)
            dk['floorKey'] = f'f:{b["name"]}:{code}'
        cond, man, pref, uns, elev = random.choice(COND)
        origin = {'useCurrentLocation': True, 'placeKey': None, 'buildingKey': None, 'floorKey': None, 'ambiguous': False}
        if random.random() < 0.3:
            ob = random.choice([x for x in BUILD if x['key'] != b['key']])
            text = random.choice(ORIG_T).format(o=ob['name'], d=d)
            origin = {**origin, 'useCurrentLocation': False, 'buildingKey': ob['key']}
        else:
            text = random.choice(DEST_T).format(d=d)
        if cond:
            text = cond + ' ' + text if random.random() < 0.5 else text + ' ' + cond
        mode = 'preferElevator' if elev else ('avoidStairs' if ('avoidStairs' in man or 'fewerStairs' in pref) else 'shortest')
        rows.append({'text': text, 'destination': dk, 'origin': origin, 'waypoints': [], 'mandatory': man, 'preferences': pref,
                     'unsupported': uns, 'timeLimitMin': None, 'mode': mode, 'needsClarification': False})
    return rows


def to_msg(g):
    ctx, _ = build_prompt(g['text'])
    return {'messages': [
        {'role': 'system', 'content': SYSTEM + '\n\n' + ctx},
        {'role': 'user', 'content': g['text']},
        {'role': 'assistant', 'content': json.dumps(target_output(g), ensure_ascii=False)},
    ]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    test_texts = {g['text'] for g in load_gold('test')}
    dev = load_gold('dev')
    aug = [r for r in synth(1500) if r['text'] not in test_texts]
    rows = dev * 3 + aug  # 사람 말투 문장을 3배로
    random.shuffle(rows)
    seen = {r['text'] for r in rows} | test_texts
    val = [to_msg(g) for g in synth(200) if g['text'] not in seen][:60]
    (OUT / 'train.jsonl').write_text(''.join(json.dumps(to_msg(g), ensure_ascii=False) + '\n' for g in rows), encoding='utf-8')
    (OUT / 'val.jsonl').write_text(''.join(json.dumps(m, ensure_ascii=False) + '\n' for m in val), encoding='utf-8')
    print('train', len(rows), 'val', len(val))


if __name__ == '__main__':
    main()
