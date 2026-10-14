"""Gemma 3 270M 실험 전체를 한 번에: 자료 → 미세조정 → GGUF(F16/Q8_0/Q4_K_M) → 시험셋 평가 → 속도 → 비교표.
사용(약관 동의·로그인 뒤): .venv\\Scripts\\python llm\\run_all.py
점검용(게이트 없는 작은 무작위 Gemma3 로 흐름만 확인): set GEMMA_MODEL_ID=hf-internal-testing/tiny-random-Gemma3ForCausalLM & ... --dry
"""
import argparse, json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
LLAMA_BIN = pathlib.Path(os.environ.get('LLAMA_CPP_BIN', r'C:\campus-nlp-vendor\llama-win'))


def run(*cmd):
    print('\n>', ' '.join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='흐름 점검: 짧게 학습, 평가 10문장')
    ap.add_argument('--lora', action='store_true')
    a = ap.parse_args()
    name = 'dryrun' if a.dry else 'gemma3-270m-route'
    os.environ['GGUF_NAME'] = name
    run(PY, 'llm/prepare_data.py')
    ft = [PY, 'llm/finetune.py'] + (['--epochs', '0.02'] if a.dry else []) + (['--lora'] if a.lora else [])
    run(*ft)
    run(PY, 'llm/export_gguf.py')
    lim = ['--limit', '10'] if a.dry else []
    for q in ('Q8_0', 'Q4_K_M'):
        model = ROOT / 'models' / f'{name}-{q}.gguf'
        preds = ROOT / 'results' / f'preds-{name}-{q}.jsonl'
        run(PY, 'llm/run_llamacpp.py', '--model', model, '--out', preds, '--split', 'test', *lim)
        run(PY, 'eval/score.py', preds, '--split', 'test', '--json', ROOT / 'results' / f'{name}-{q}-test.json')
        with open(ROOT / 'results' / f'{name}-{q}.bench.txt', 'w', encoding='utf-8') as f:
            subprocess.run([str(LLAMA_BIN / 'llama-bench.exe'), '-m', str(model), '-p', '512', '-n', '64', '-t', '6'], stdout=f, check=True)
    run(PY, 'eval/compare.py')


if __name__ == '__main__':
    main()
