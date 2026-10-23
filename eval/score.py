"""예측(jsonl: {id, pred, ms}) 을 gold.jsonl 과 비교해 지표를 낸다. 방식 A·LLM 공용.
사용: python eval/score.py preds.jsonl [--split test|dev|all] [--json out.json]
"""
import json, sys, pathlib, statistics, argparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
UNSUP_KW = [  # (범주, 이유 키워드, 문구 키워드)
    ('place', ['장소'], []), ('floor', ['층'], []), ('entrance', ['입구'], []),
    ('wheelchair', [], ['휠체어']), ('covered', [], ['비', '지붕', '우산', '눈']), ('quiet', [], ['조용', '소음']),
    ('crowd', [], ['사람', '붐', '혼잡', '한산']), ('scenic', [], ['경치', '산책', '경관']), ('shade', [], ['그늘']),
    ('slope', [], ['오르막', '언덕', '경사']), ('lighting', [], ['밝', '조명', '가로등', '어두']), ('smoking', [], ['흡연', '담배']),
    ('amenity', [], ['편의시설', '자판기']),
]


def unsup_kinds(items):
    out = set()
    for u in items or []:
        text, reason = str(u.get('text', '')), str(u.get('reason', ''))
        for kind, rkw, tkw in UNSUP_KW:
            if any(k in reason for k in rkw) or any(k in text for k in tkw):
                out.add(kind)
                break
    return out


def keys(t):
    t = t or {}
    return (t.get('placeKey'), t.get('buildingKey'), t.get('floorKey'))


def score(gold, preds):
    n = len(gold)
    m = dict(dest=0, origin=0, mand=0, mode=0, sec=0, pref=0, time=0, viol=0, spurious_stairs=0, unsup_tp=0, unsup_gold=0, unsup_pred=0, clar_tp=0, clar_pred=0, clar_gold=0, parse_fail=0)
    errors = []
    for g in gold:
        p = preds.get(g['id'])
        if not isinstance(p, dict):
            m['parse_fail'] += 1
            p = {}
        pd, gd = p.get('destination') or {}, g['destination']
        clar = bool(p.get('needsClarification'))
        if gd['buildingKey'] or gd['placeKey']:
            ok_dest = keys(pd) == keys(gd)
        else:
            ok_dest = clar and not (pd.get('placeKey') and not pd.get('candidates'))
        m['dest'] += ok_dest
        po, go = p.get('origin') or {}, g['origin']
        if go['useCurrentLocation']:
            ok_o = bool(po.get('useCurrentLocation', False))
        elif go['ambiguous']:
            ok_o = clar
        else:
            ok_o = keys(po) == keys(go)
        m['origin'] += ok_o
        pm, gm = set(p.get('mandatory') or []), set(g['mandatory'])
        m['mand'] += pm == gm
        m['viol'] += not gm <= pm
        m['spurious_stairs'] += g['stairsAllowed'] and 'avoidStairs' in pm
        m['mode'] += p.get('mode') == g['mode']
        m['sec'] += list(p.get('secondaryModes') or []) == list(g.get('secondaryModes') or [])
        m['pref'] += set(p.get('preferences') or []) == set(g['preferences'])
        m['time'] += p.get('timeLimitMin') == g['timeLimitMin']
        gu, pu = set(g['unsupported']), unsup_kinds(p.get('unsupported'))
        m['unsup_gold'] += len(gu); m['unsup_pred'] += len(pu); m['unsup_tp'] += len(gu & pu)
        gc = g['needsClarification']
        m['clar_gold'] += gc; m['clar_pred'] += clar; m['clar_tp'] += gc and clar
        if not (ok_dest and pm == gm and ok_o):
            errors.append({'id': g['id'], 'text': g['text'], 'dest_ok': ok_dest, 'origin_ok': ok_o, 'mand': sorted(pm), 'gold_mand': sorted(gm)})
    r = lambda a, b: round(a / b, 3) if b else None
    return {
        'n': n, 'destination_acc': r(m['dest'], n), 'origin_acc': r(m['origin'], n),
        'mandatory_exact': r(m['mand'], n), 'mandatory_violations': m['viol'], 'spurious_avoidStairs_when_stairs_ok': m['spurious_stairs'],
        'mode_acc': r(m['mode'], n), 'secondary_modes_exact': r(m['sec'], n), 'preferences_exact': r(m['pref'], n), 'time_acc': r(m['time'], n),
        'unsupported_recall': r(m['unsup_tp'], m['unsup_gold']), 'unsupported_precision': r(m['unsup_tp'], m['unsup_pred']),
        'clarification_precision': r(m['clar_tp'], m['clar_pred']), 'clarification_recall': r(m['clar_tp'], m['clar_gold']),
        'parse_fail': m['parse_fail'],
    }, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('preds'); ap.add_argument('--split', default='test'); ap.add_argument('--json'); ap.add_argument('--errors', action='store_true')
    a = ap.parse_args()
    gold = [json.loads(l) for l in (ROOT / 'eval' / 'gold.jsonl').read_text(encoding='utf-8').splitlines()]
    gold = [g for g in gold if a.split == 'all' or g['split'] == a.split]
    rows = [json.loads(l) for l in pathlib.Path(a.preds).read_text(encoding='utf-8').splitlines() if l.strip()]
    preds = {x['id']: x.get('pred') for x in rows}
    ms = [x['ms'] for x in rows if x['id'] in {g['id'] for g in gold} and 'ms' in x]
    res, errs = score(gold, preds)
    if ms:
        ms.sort()
        res['latency_ms_mean'] = round(statistics.mean(ms), 2)
        res['latency_ms_p95'] = round(ms[int(len(ms) * 0.95) - 1], 2)
    res['split'] = a.split
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.errors:
        for e in errs:
            print(json.dumps(e, ensure_ascii=False))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
