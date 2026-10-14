"""google/gemma-3-270m-it 미세조정(CPU). 기본은 전체 미세조정(270M 이라 32 GB RAM 에서 가능), --lora 로 LoRA.
답(assistant) 토큰에만 손실을 건다. 결과: llm/out/gemma-ft (병합된 HF 모델).

전제: Gemma 이용 약관 동의 + `hf auth login` (RUN-AFTER-LOGIN.md).
"""
import argparse, json, math, os, pathlib, random, sys, time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'llm' / 'out'
MODEL_ID = os.environ.get('GEMMA_MODEL_ID', 'google/gemma-3-270m-it')


def encode(tok, msgs, max_len):
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    full = prompt + msgs[-1]['content'] + '<end_of_turn>\n'
    p_ids = tok(prompt, add_special_tokens=False)['input_ids']
    ids = tok(full, add_special_tokens=False)['input_ids'][:max_len]
    labels = [-100] * min(len(p_ids), len(ids)) + ids[len(p_ids):]
    return ids, labels[:len(ids)]


def batches(rows, bs):
    random.shuffle(rows)
    for i in range(0, len(rows), bs):
        chunk = rows[i:i + bs]
        L = max(len(x[0]) for x in chunk)
        ids = torch.full((len(chunk), L), 0, dtype=torch.long)
        lab = torch.full((len(chunk), L), -100, dtype=torch.long)
        att = torch.zeros((len(chunk), L), dtype=torch.long)
        for j, (a, b) in enumerate(chunk):
            ids[j, :len(a)] = torch.tensor(a); lab[j, :len(b)] = torch.tensor(b); att[j, :len(a)] = 1
        yield ids, lab, att


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=float, default=2); ap.add_argument('--bs', type=int, default=8)
    ap.add_argument('--lr', type=float, default=5e-5); ap.add_argument('--lora', action='store_true')
    ap.add_argument('--max-len', type=int, default=1024); ap.add_argument('--threads', type=int, default=6)
    a = ap.parse_args()
    torch.set_num_threads(a.threads); random.seed(0); torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float32, attn_implementation='eager')
    if a.lora:
        from peft import LoraConfig, get_peft_model
        model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'], task_type='CAUSAL_LM'))
        a.lr = max(a.lr, 2e-4)
    load = lambda p: [encode(tok, json.loads(l)['messages'], a.max_len) for l in (OUT / p).read_text(encoding='utf-8').splitlines()]
    train, val = load('train.jsonl'), load('val.jsonl')
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    steps = math.ceil(len(train) / a.bs) * a.epochs
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 30) * max(0.0, 1 - s / steps))
    model.train(); step, t0 = 0, time.time()
    while step < steps:
        for ids, lab, att in batches(train, a.bs):
            loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad(); step += 1
            if step % 10 == 0:
                print(f'step {step}/{int(steps)} loss {loss.item():.4f} {time.time() - t0:.0f}s', flush=True)
            if step >= steps:
                break
    model.eval()
    with torch.no_grad():
        vl = [model(input_ids=ids, attention_mask=att, labels=lab).loss.item() for ids, lab, att in batches(val, a.bs)]
    print('val loss', sum(vl) / len(vl))
    if a.lora:
        model = model.merge_and_unload()
    model.save_pretrained(OUT / 'gemma-ft', safe_serialization=True)
    tok.save_pretrained(OUT / 'gemma-ft')
    (OUT / 'gemma-ft' / 'train_meta.json').write_text(json.dumps({'steps': step, 'val_loss': sum(vl) / len(vl), 'lora': a.lora, 'seconds': time.time() - t0}), encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
