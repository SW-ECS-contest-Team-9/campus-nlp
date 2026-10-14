# 시험셋(test) 비교 — SYNTHETIC 문장

| 방식 | destination_acc | origin_acc | mandatory_exact | mandatory_violations | spurious_avoidStairs_when_stairs_ok | unsupported_recall | clarification_precision | clarification_recall | parse_fail | latency_ms_mean | 크기 MB | 생성 tok/s(PC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A 규칙(TS) | 1.0 | 1.0 | 1.0 | 0 | 0 | 0.969 | 0.938 | 1.0 | 0 | 0.04 | 0.05(코드) | - |
| 대역 Qwen2.5-0.5B Q4_K_M zero-shot | 0.237 | 0.849 | 0.125 | 9 | 5 | 0.406 | 0.092 | 0.867 | 10 | 4426.19 | 491.4 | 51.4 |
| Gemma 3 270M 미세조정 Q8_0 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | | |
| Gemma 3 270M 미세조정 Q4_K_M | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | 대기 | | |
