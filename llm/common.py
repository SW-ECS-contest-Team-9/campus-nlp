"""방식 C 공용: 프롬프트(입력 문장 + 꾸러미 장소 일부), 제한 출력용 JSON 스키마, 이름→key 해석.
모델은 장소 key 를 쓰지 않는다. 목록 안의 이름만 고르고(스키마 enum 으로 강제), key 는 이 코드가 꾸러미에서 찾는다.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = json.loads((ROOT / 'data' / 'package.bin').read_text(encoding='utf-8'))
TOP_K_PLACES = 8

SYSTEM = (
    '너는 캠퍼스 길찾기 요청을 조건 JSON 으로 바꾼다. 길은 만들지 않는다.\n'
    '- 장소는 아래 목록의 이름만 쓴다. 목록에 없으면 dest 를 null 로 두고 unsupported 에 {"text":그 장소,"reason":"지도에 그 장소가 아직 없음"}.\n'
    '- 같은 말이 여러 장소에 맞으면 clarify 에 짧은 질문.\n'
    '- mandatory: 계단을 못 쓰는 사정(계단 없이, 휠체어, 유모차, 목발, 다리 다침)이면 "avoidStairs". 휠체어면 "wheelchairNeeded" 도.\n'
    '- "계단으로", "계단 괜찮아"면 mandatory 는 비운다.\n'
    '- preferences: 짐·피곤 → "fewerStairs", 실내로·추움 → "indoor".\n'
    '- 지붕(비)·조용함·붐빔·경치·그늘·오르막·조명·흡연 은 지도에 자료가 없으므로 preferences 에 넣지 말고 unsupported 에 reason "지도에 그 정보가 아직 없음".\n'
    '- 휠체어면 unsupported 에 {"text":"휠체어","reason":"휠체어 통행 가능 여부가 지도에 아직 없음"} 도 넣는다.\n'
    '- mode: 엘리베이터 언급 → preferElevator, 계단 피하기/짐 → avoidStairs, 그 외 shortest.\n'
    '- floor 는 "3F", "B1" 형식. 출발지를 말하지 않았으면 origin.current=true.'
)


def _clean(name):
    return re.sub(r'\(.*?\)', '', name.split('=')[0]).split(':')[0].strip()


def place_names():
    """(표시 이름, placeKey, buildingKey). 표시 이름이 겹치면 원래 이름 사용."""
    out = []
    for p in PKG['places']:
        out.append((p['name'], p['key'], p['buildingKey']))
    return out


def _bigrams(s):
    s = re.sub(r'\s+', '', s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def places_subset(text, k=TOP_K_PLACES):
    """간단한 검색(RAG 축소판): 글자 2-gram 겹침으로 장소 상위 k 개."""
    q = _bigrams(text)
    scored = sorted(place_names(), key=lambda p: -len(q & _bigrams(p[0])))
    return [p for p in scored[:k] if q & _bigrams(p[0])]


def build_prompt(text):
    buildings = [b['name'] + (' (별칭: ' + ', '.join(b['aliases']) + ')' if b['aliases'] else '') for b in PKG['buildings']]
    places = [p[0] for p in places_subset(text)]
    ctx = '건물: ' + ' | '.join(buildings) + '\n장소: ' + (' | '.join(places) if places else '(없음)')
    return ctx, places


def name_enum(places):
    return [b['name'] for b in PKG['buildings']] + places


def json_schema(places):
    names = name_enum(places)
    tgt = {'type': 'object', 'properties': {'name': {'enum': names + [None]}, 'floor': {'type': ['string', 'null']}}, 'required': ['name', 'floor']}
    return {
        'type': 'object',
        'properties': {
            'dest': tgt,
            'origin': {'type': 'object', 'properties': {'current': {'type': 'boolean'}, 'name': {'enum': names + [None]}, 'floor': {'type': ['string', 'null']}}, 'required': ['current', 'name', 'floor']},
            'waypoints': {'type': 'array', 'items': {'enum': names}, 'maxItems': 3},
            'mode': {'enum': ['shortest', 'avoidStairs', 'preferElevator']},
            'mandatory': {'type': 'array', 'items': {'enum': ['avoidStairs', 'wheelchairNeeded']}, 'maxItems': 2},
            'preferences': {'type': 'array', 'items': {'enum': ['indoor', 'fewerStairs']}, 'maxItems': 2},
            'timeLimitMin': {'type': ['integer', 'null']},
            'unsupported': {'type': 'array', 'items': {'type': 'object', 'properties': {'text': {'type': 'string'}, 'reason': {'type': 'string'}}, 'required': ['text', 'reason']}, 'maxItems': 4},
            'clarify': {'type': ['string', 'null']},
        },
        'required': ['dest', 'origin', 'waypoints', 'mode', 'mandatory', 'preferences', 'timeLimitMin', 'unsupported', 'clarify'],
    }


def _lookup(name, floor):
    t = {'text': name, 'placeKey': None, 'buildingKey': None, 'floorKey': None, 'candidates': []}
    if not name:
        return t
    for b in PKG['buildings']:
        if b['name'] == name:
            t['buildingKey'] = b['key']
    for p in PKG['places']:
        if p['name'] == name:
            t['placeKey'], t['buildingKey'] = p['key'], p['buildingKey']
    if floor and t['buildingKey']:
        code = str(floor).upper().replace('층', 'F')
        for f in PKG['floors']:
            if f['buildingKey'] == t['buildingKey'] and f['code'] == code:
                t['floorKey'] = f['key']
    return t


def to_route_request(o):
    """모델 출력(이름) → 스키마 v1(key). 해석 못 한 것은 버리지 않고 unsupported/재확인으로 남긴다."""
    unsupported = list(o.get('unsupported') or [])
    d = (o.get('dest') or {})
    dest = _lookup(d.get('name'), d.get('floor'))
    if d.get('floor') and dest['buildingKey'] and not dest['floorKey']:
        unsupported.append({'text': str(d.get('floor')), 'reason': '지도에 그 층이 없음'})
    og = o.get('origin') or {}
    origin = {**_lookup(None if og.get('current') else og.get('name'), og.get('floor')), 'useCurrentLocation': bool(og.get('current', True)) or not og.get('name')}
    clar = o.get('clarify')
    if not dest['text'] and not clar:
        clar = '어디로 갈까요?'
    return {
        'v': 1, 'destination': dest, 'origin': origin,
        'waypoints': [_lookup(w, None) for w in (o.get('waypoints') or [])],
        'mode': o.get('mode', 'shortest'), 'mandatory': o.get('mandatory') or [], 'preferences': o.get('preferences') or [],
        'timeLimitMin': o.get('timeLimitMin'), 'unsupported': unsupported,
        'needsClarification': {'question': clar} if clar else None,
    }


def target_output(g):
    """gold → 모델이 내야 할 출력(이름 기반). 미세조정 자료용."""
    def nm(t):
        if t.get('placeKey'):
            return next(p['name'] for p in PKG['places'] if p['key'] == t['placeKey'])
        if t.get('buildingKey'):
            return next(b['name'] for b in PKG['buildings'] if b['key'] == t['buildingKey'])
        return None

    def fl(t):
        return t['floorKey'].split(':')[-1] if t.get('floorKey') else None
    reasons = {'place': '지도에 그 장소가 아직 없음', 'floor': '지도에 그 층이 없음', 'entrance': '지도에 그 입구 번호가 없음', 'wheelchair': '휠체어 통행 가능 여부가 지도에 아직 없음'}
    labels = {'covered': '비·지붕', 'quiet': '조용한 길', 'crowd': '사람 적은 길', 'scenic': '경치', 'shade': '그늘', 'slope': '오르막', 'lighting': '밝은 길', 'smoking': '흡연', 'amenity': '편의시설', 'place': '장소', 'floor': '층', 'entrance': '입구', 'wheelchair': '휠체어'}
    go = g['origin']
    return {
        'dest': {'name': nm(g['destination']), 'floor': fl(g['destination'])},
        'origin': {'current': go['useCurrentLocation'], 'name': None if go['useCurrentLocation'] else nm(go), 'floor': fl(go)},
        'waypoints': [nm(w) for w in g['waypoints']],
        'mode': g['mode'], 'mandatory': g['mandatory'], 'preferences': g['preferences'], 'timeLimitMin': g['timeLimitMin'],
        'unsupported': [{'text': labels[u], 'reason': reasons.get(u, '지도에 그 정보가 아직 없음')} for u in g['unsupported']],
        'clarify': '어느 곳인가요?' if g['needsClarification'] else None,
    }


def load_gold(split=None):
    rows = [json.loads(l) for l in (ROOT / 'eval' / 'gold.jsonl').read_text(encoding='utf-8').splitlines()]
    return [r for r in rows if split in (None, 'all') or r['split'] == split]
