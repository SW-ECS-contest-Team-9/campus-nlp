"""results/*-test.json 을 모아 비교표(results/COMPARE.md)를 만든다."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / 'results'
ROWS = [
    ('A 규칙(TS)', 'A-test.json', None),
    ('대역 Qwen2.5-0.5B Q4_K_M zero-shot', 'standin-qwen0.5b-test.json', 'preds-standin-qwen0.5b.meta.json'),
    ('Gemma 3 270M 미세조정 Q8_0', 'gemma3-270m-route-Q8_0-test.json', 'preds-gemma3-270m-route-Q8_0.meta.json'),
    ('Gemma 3 270M 미세조정 Q4_K_M', 'gemma3-270m-route-Q4_K_M-test.json', 'preds-gemma3-270m-route-Q4_K_M.meta.json'),
]
COLS = ['destination_acc', 'origin_acc', 'mandatory_exact', 'mandatory_violations', 'spurious_avoidStairs_when_stairs_ok', 'unsupported_recall',
        'clarification_precision', 'clarification_recall', 'parse_fail', 'latency_ms_mean']


def main():
    lines = ['| 방식 | ' + ' | '.join(COLS) + ' | 크기 MB | 생성 tok/s(PC) |', '|' + '---|' * (len(COLS) + 3)]
    for label, f, meta in ROWS:
        p = RES / f
        if not p.exists():
            lines.append(f'| {label} | ' + ' | '.join(['대기'] * len(COLS)) + ' | | |')
            continue
        r = json.loads(p.read_text(encoding='utf-8'))
        m = json.loads((RES / meta).read_text(encoding='utf-8')) if meta and (RES / meta).exists() else {}
        lines.append(f'| {label} | ' + ' | '.join(str(r.get(c)) for c in COLS) + f" | {m.get('size_mb', '0.05(코드)')} | {m.get('gen_tokens_per_s_mean', '-')} |")
    (RES / 'COMPARE.md').write_text('# 시험셋(test) 비교 — SYNTHETIC 문장\n\n' + '\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
