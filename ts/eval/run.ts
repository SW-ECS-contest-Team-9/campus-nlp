// 방식 A 를 gold.jsonl 전체에 돌려 예측 파일을 쓴다. 지표는 eval/score.py 가 계산.
import { readFileSync, writeFileSync } from 'fs';
import { performance } from 'perf_hooks';
import { parseRouteRequest } from '../src/parse';
import { buildLexicon } from '../src/lexicon';

const root = new URL('../../', import.meta.url);
const pkg = JSON.parse(readFileSync(new URL('data/package.bin', root), 'utf8'));
const gold = readFileSync(new URL('eval/gold.jsonl', root), 'utf8').trim().split('\n').map(l => JSON.parse(l));
const lex = buildLexicon(pkg);
for (const g of gold.slice(0, 20)) parseRouteRequest(g.text, pkg, lex); // 데우기
const out = gold.map(g => { const t = performance.now(); const pred = parseRouteRequest(g.text, pkg, lex); return JSON.stringify({ id: g.id, pred, ms: performance.now() - t }); });
writeFileSync(new URL('results/preds-A.jsonl', root), out.join('\n') + '\n');
console.log('wrote', out.length);
