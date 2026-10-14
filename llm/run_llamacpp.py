"""GGUF 모델을 llama.cpp(llama-server)로 돌려 시험 문장 예측을 쓴다. JSON 스키마 제한 출력(문법).
대역(Qwen2.5-1.5B, 무학습 zero-shot)과 Gemma 3 270M(미세조정 후) 둘 다 이 스크립트로 잰다.

사용: python llm/run_llamacpp.py --model models/x.gguf --out results/preds-X.jsonl [--split all] [--threads 6]
"""
import argparse, json, os, pathlib, subprocess, sys, time, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, SYSTEM, build_prompt, json_schema, load_gold, to_route_request  # noqa: E402

LLAMA_DIR = pathlib.Path(os.environ.get('LLAMA_CPP_BIN', r'C:\campus-nlp-vendor\llama-win'))
PORT = int(os.environ.get('LLAMA_PORT', '8091'))


def post(path, body):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def wait_ready(proc):
    for _ in range(300):
        if proc.poll() is not None:
            raise SystemExit('llama-server 종료됨')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise SystemExit('llama-server 시작 실패')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--split', default='all'); ap.add_argument('--threads', type=int, default=6); ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    log = open(ROOT / 'results' / (pathlib.Path(a.out).stem + '.server.log'), 'w')
    proc = subprocess.Popen([str(LLAMA_DIR / 'llama-server.exe'), '-m', a.model, '--port', str(PORT), '-t', str(a.threads), '-c', '4096', '--no-webui', '-np', '1'], stdout=log, stderr=log)
    try:
        wait_ready(proc)
        gold = load_gold(a.split)[: a.limit]
        out, tps = [], []
        for g in gold:
            ctx, places = build_prompt(g['text'])
            body = {
                'messages': [{'role': 'system', 'content': SYSTEM + '\n\n' + ctx}, {'role': 'user', 'content': g['text']}],
                'temperature': 0, 'max_tokens': 300,
                'response_format': {'type': 'json_schema', 'json_schema': {'name': 'route', 'schema': json_schema(places)}},
            }
            t = time.perf_counter()
            r = post('/v1/chat/completions', body)
            ms = (time.perf_counter() - t) * 1000
            raw = r['choices'][0]['message']['content']
            try:
                pred = to_route_request(json.loads(raw))
            except Exception:
                pred = None
            tm = r.get('timings', {})
            if tm.get('predicted_per_second'):
                tps.append(tm['predicted_per_second'])
            out.append({'id': g['id'], 'pred': pred, 'raw': raw, 'ms': ms, 'prompt_n': tm.get('prompt_n'), 'predicted_n': tm.get('predicted_n')})
            print(g['id'], round(ms), raw[:120].replace('\n', ' '), flush=True)
        pathlib.Path(a.out).write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in out), encoding='utf-8')
        meta = {'model': pathlib.Path(a.model).name, 'size_mb': round(pathlib.Path(a.model).stat().st_size / 1e6, 1),
                'gen_tokens_per_s_mean': round(sum(tps) / len(tps), 1) if tps else None, 'threads': a.threads, 'n': len(out)}
        pathlib.Path(a.out).with_suffix('.meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps(meta, ensure_ascii=False))
    finally:
        proc.terminate()


if __name__ == '__main__':
    main()
