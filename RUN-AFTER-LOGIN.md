# Gemma 3 270M 실험 — 사용자가 할 일

작성: Claude (2026-10-15)

이 PC 의 Hugging Face 캐시에는 Gemma 가 없고(`C:\Users\ssant\.cache\huggingface\hub` 확인), 로그인 토큰도 없다.
`google/gemma-3-270m-it` 는 게이트 모델이다(API 표시 `gated: manual`). 약관 동의와 로그인은 사용자 본인이 해야 한다. 비공식 사본은 쓰지 않는다.

## 1. 약관 동의 (브라우저, 본인 계정)
1. https://huggingface.co/google/gemma-3-270m-it 를 연다.
2. 로그인 → "Acknowledge license / Agree and access repository" 에서 Gemma 이용 약관을 읽고 동의.
3. 페이지에 접근 허용이 표시될 때까지 기다린다(`manual` 이라 승인에 시간이 걸릴 수 있음).

## 2. 토큰 만들기와 로그인 (PowerShell)
1. https://huggingface.co/settings/tokens 에서 **Read** 권한 토큰 생성.
2. 아래 실행 후 토큰 붙여넣기(토큰은 어디에도 적지 않는다):
```powershell
C:\campus-nlp\.venv\Scripts\hf.exe auth login
C:\campus-nlp\.venv\Scripts\hf.exe auth whoami
```

## 3. 실험 전체 실행 (명령 하나)
```powershell
cd C:\campus-nlp; .venv\Scripts\python.exe llm\run_all.py
```
하는 일: 학습 자료 생성 → `google/gemma-3-270m-it` 내려받기(약 540 MB) → CPU 전체 미세조정(2 에폭, 추정 30~90 분)
→ GGUF F16 / Q8_0 / Q4_K_M (`models\`) → 시험셋 152 문장 평가(JSON 스키마 제한 출력) → PC 속도(llama-bench) → `results\COMPARE.md` 비교표.
LoRA 로 하려면 끝에 `--lora`.

## 4. 실제 S21 속도 (선택)
휴대폰 USB 디버깅 켜고 연결 후 Git Bash:
```bash
bash /c/campus-nlp/android/s21_bench.sh /c/campus-nlp/models/gemma3-270m-route-Q4_K_M.gguf
THREADS=2 bash /c/campus-nlp/android/s21_bench.sh /c/campus-nlp/models/gemma3-270m-route-Q4_K_M.gguf
```
`android/bin/` 의 arm64 실행 파일(llama.cpp 소스 529ac89, NDK 27)이 `/data/local/tmp/campus-nlp` 에 올라가 돈다. 끝나면 `adb shell rm -r /data/local/tmp/campus-nlp`.

## 참고
- 흐름 점검은 이미 했다: 게이트 없는 무작위 소형 Gemma3(`hf-internal-testing/tiny-random-Gemma3ForCausalLM`)로 학습→GGUF→평가가 끝까지 돈다(점수 의미 없음).
