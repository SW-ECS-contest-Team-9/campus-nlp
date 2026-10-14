#!/usr/bin/env bash
# 실제 S21(arm64-v8a)에서 GGUF 속도·메모리 재기. PC 에서 실행(Git Bash), 휴대폰은 USB 디버깅 켜고 연결.
#   bash android/s21_bench.sh models/gemma3-270m-route-Q4_K_M.gguf
# 바이너리: android/bin/llama-bench, llama-completion (NDK 27 로 빌드, arm64-v8a, android-28, 정적 링크)
# 에뮬레이터(Campus_S21, x86_64)에서는 이 arm64 바이너리가 돌지 않는다. 속도는 실기기에서만 의미 있음.
set -euo pipefail
MODEL="${1:?gguf 경로}"
ADB="${ADB:-/c/Users/ssant/AppData/Local/Android/Sdk/platform-tools/adb.exe}"
DIR=/data/local/tmp/campus-nlp
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="$(basename "$MODEL")"
THREADS="${THREADS:-4}"   # Exynos 2100: X1 1 + A78 3 + A55 4. 큰 코어 4개가 보통 가장 빠름. 2·4·6 비교 권장
PROMPT_FILE="$HERE/sample_prompt.txt"

"$ADB" shell mkdir -p $DIR
"$ADB" push "$HERE/bin/llama-bench" "$HERE/bin/llama-completion" $DIR/ >/dev/null
"$ADB" push "$MODEL" $DIR/ >/dev/null
"$ADB" push "$PROMPT_FILE" $DIR/prompt.txt >/dev/null
"$ADB" shell chmod 755 $DIR/llama-bench $DIR/llama-completion
"$ADB" shell getprop ro.product.model
"$ADB" shell getprop ro.soc.model || true

echo "== llama-bench (프롬프트 512 토큰 처리 / 64 토큰 생성), threads=$THREADS"
"$ADB" shell "cd $DIR && ./llama-bench -m $NAME -p 512 -n 64 -t $THREADS"

echo "== 실제 요청 1건(시험 문장 프롬프트, 최대 160 토큰) — 첫 로드 시간·전체 시간·최대 메모리"
"$ADB" shell "cd $DIR && /system/bin/time -v ./llama-completion -m $NAME -t $THREADS -c 2048 -n 160 --temp 0 -f prompt.txt 2>&1 | grep -E 'load time|prompt eval time|eval time|total time|Maximum resident' " || \
"$ADB" shell "cd $DIR && ./llama-completion -m $NAME -t $THREADS -c 2048 -n 160 --temp 0 -f prompt.txt 2>&1 | grep -E 'load time|prompt eval time|eval time|total time'"
echo "== 정리: adb shell rm -r $DIR"
