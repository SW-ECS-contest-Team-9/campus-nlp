"""utterances.txt(손으로 쓴 주석) → gold.jsonl(스키마 v1 전체). 장소는 꾸러미 이름으로만 찾는다.
SYNTHETIC 자료. dev/test 는 줄 순서 기준 5개 중 2개 dev(고정).
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
pkg = json.loads((ROOT / 'data' / 'package.bin').read_text(encoding='utf-8'))
bmap = {b['name']: b['key'] for b in pkg['buildings']}
floors = {(f['buildingKey'], f['code']): f['key'] for f in pkg['floors']}


def target(ref):
    t = {'text': None, 'placeKey': None, 'buildingKey': None, 'floorKey': None}
    if ref in ('-', None):
        return t, False
    if ref == '?':
        return t, True
    kind, _, rest = ref.partition(':')
    name, _, fl = rest.partition('@')
    t['text'] = name
    if kind == 'B':
        t['buildingKey'] = bmap[name]
    else:
        hits = [p for p in pkg['places'] if name in p['name']]
        assert len(hits) == 1, (ref, [h['name'] for h in hits])
        t['placeKey'], t['buildingKey'] = hits[0]['key'], hits[0]['buildingKey']
    if fl:
        t['floorKey'] = floors[(t['buildingKey'], fl)]
    return t, False


def parse_line(line):
    text, dest, opts = [x.strip() for x in line.split('||')]
    g = {'v': 1, 'text': text}
    d, amb = target(dest)
    g['destination'] = {**d, 'ambiguous': amb}
    o = {'useCurrentLocation': True, 'placeKey': None, 'buildingKey': None, 'floorKey': None, 'ambiguous': False}
    g['waypoints'], g['mandatory'], g['preferences'], g['unsupported'] = [], [], [], []
    g['timeLimitMin'], elev, clar, ok, mode, sec = None, False, False, False, None, []
    for k, v in re.findall(r'(\w+)(?:=(.*?))?(?=\s+(?:[owMptums]=|e(?:\s|$)|c(?:\s|$)|ok(?:\s|$))|$)', opts):
        if k == 'o':
            t, a = target(v)
            o = {**t, 'useCurrentLocation': False, 'ambiguous': a}
        elif k == 'w':
            g['waypoints'].append(target(v)[0])
        elif k == 'M':
            g['mandatory'] = v.split(',')
        elif k == 'p':
            g['preferences'] = v.split(',')
        elif k == 'u':
            g['unsupported'] = v.split(',')
        elif k == 't':
            g['timeLimitMin'] = int(v)
        elif k == 'e':
            elev = True
        elif k == 'c':
            clar = True
        elif k == 'ok':
            ok = True
        elif k == 'm':
            mode = v
        elif k == 's':
            sec = v.split(',')
    g['origin'] = o
    g['mode'] = mode or ('preferElevator' if elev else ('avoidStairs' if ('avoidStairs' in g['mandatory'] or 'fewerStairs' in g['preferences']) else 'shortest'))
    g['secondaryModes'] = sec
    g['needsClarification'] = clar or amb or dest == '-'
    g['stairsAllowed'] = ok
    return g


def main():
    src = (ROOT / 'eval' / 'utterances.txt').read_text(encoding='utf-8').splitlines()
    rows = [parse_line(l) for l in src if l.strip() and not l.startswith('#')]
    for i, r in enumerate(rows):
        r['id'], r['split'] = i, ('dev' if i % 5 in (0, 3) else 'test')
    out = ROOT / 'eval' / 'gold.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(len(rows), 'rows;', sum(r['split'] == 'dev' for r in rows), 'dev')


if __name__ == '__main__':
    sys.exit(main())
