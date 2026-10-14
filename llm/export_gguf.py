"""미세조정 결과(HF) → GGUF F16 → Q8_0, Q4_K_M. llama.rn(Android arm64-v8a) 이 그대로 읽는다.
convert_hf_to_gguf.py 는 llama.cpp 원본(C:\\campus-nlp-vendor\\llama.cpp), llama-quantize 는 공식 Windows 배포본.
"""
import os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'llm' / 'out' / 'gemma-ft'
DST = ROOT / 'models'
LLAMA_SRC = pathlib.Path(os.environ.get('LLAMA_CPP_SRC', r'C:\campus-nlp-vendor\llama.cpp'))
LLAMA_BIN = pathlib.Path(os.environ.get('LLAMA_CPP_BIN', r'C:\campus-nlp-vendor\llama-win'))
NAME = os.environ.get('GGUF_NAME', 'gemma3-270m-route')


def run(cmd):
    print('>', ' '.join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True)


def main():
    DST.mkdir(exist_ok=True)
    f16 = DST / f'{NAME}-F16.gguf'
    run([sys.executable, LLAMA_SRC / 'convert_hf_to_gguf.py', SRC, '--outtype', 'f16', '--outfile', f16])
    for q in ('Q8_0', 'Q4_K_M'):
        run([LLAMA_BIN / 'llama-quantize.exe', f16, DST / f'{NAME}-{q}.gguf', q])
    for p in sorted(DST.glob(f'{NAME}-*.gguf')):
        print(p.name, round(p.stat().st_size / 1e6, 1), 'MB')


if __name__ == '__main__':
    main()
