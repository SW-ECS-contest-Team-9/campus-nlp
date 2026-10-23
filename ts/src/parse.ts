// 방식 A: 규칙 + 사전. 말 → 경로 조건(JSON). 길은 만들지 않는다.
// Hermes 호환: ES2019 문법만, Intl·normalize·정규식 lookbehind·\p{} 를 쓰지 않는다.
import type { Candidate, Mandatory, MapPackage, Mode, Preference, RouteRequest, Target } from './types';
import { buildLexicon, Lexicon, LexEntry } from './lexicon';

const NO_DATA = '지도에 그 정보가 아직 없음';

// ── 정규화 ─────────────────────────────────────────────
const TYPO: [RegExp, string][] = [
  [/엘레베이터|엘리베이타|엘리베이터|엘베|승강기|엘ㄹ베/g, '엘리베이터'],
  [/게단|개단|계딴/g, '계단'],
  [/휠채어|휠체아|휠췌어/g, '휠체어'],
  [/(북악|청운|한림|혜인|유담|은주|문예|대일|상승|수인)(간|동)/g, '$1관'],
  [/북학관|부각관|북앆관/g, '북악관'],
  [/청원관/g, '청운관'],
  [/기숙사|생활관/g, '외국인생활관'],
  [/외국인외국인생활관/g, '외국인생활관'],
  [/지에스|gs25|지에스25/g, '편의점'],
  [/\bb(\d)/g, '지하$1층'],
  [/(\d+)\s*f\b/g, '$1층'],
];

function spaced(text: string): string {
  let s = text.toLowerCase().replace(/[?!.,~…"'·()\[\]]/g, ' ');
  for (const [re, to] of TYPO) s = s.replace(re, to);
  return s;
}
export function normalize(text: string): string { return spaced(text).replace(/\s+/g, ''); }

// 띄어쓰기로 시작하는 글자 위치(공백 뺀 문자열 기준). 짧은 이름("서문")이 "가서 문예관" 안에서 잘못 잡히는 것을 막는다.
function wordStarts(text: string): Set<number> {
  const set = new Set<number>([0]);
  let idx = 0, prevSpace = true;
  for (const ch of spaced(text)) {
    if (/\s/.test(ch)) { prevSpace = true; continue; }
    if (prevSpace) set.add(idx);
    prevSpace = false; idx++;
  }
  return set;
}

// ── 장소 언급 찾기 ─────────────────────────────────────
interface Mention { start: number; end: number; entry: LexEntry; floorText: string | null; floorCode: string | null; entranceNo: string | null; role: 'dest' | 'origin' | 'waypoint' | 'negated' }

const KO_NUM: Record<string, string> = { 일: '1', 이: '2', 삼: '3', 오: '5', 육: '6', 칠: '7', 팔: '8', 구: '9', 십: '10' };

function findMentions(c: string, lex: Lexicon, starts: Set<number>): Mention[] {
  const out: Mention[] = [];
  let i = 0, prevEnd = -1;
  while (i < c.length) {
    let hit: LexEntry | null = null;
    for (const e of lex.entries) if (c.startsWith(e.surface, i) && (e.surface.length > 2 || starts.has(i) || i === prevEnd)) { hit = e; break; } // 긴 것 먼저 정렬됨
    if (!hit) { i++; continue; }
    const m: Mention = { start: i, end: i + hit.surface.length, entry: hit, floorText: null, floorCode: null, entranceNo: null, role: 'dest' };
    if (hit.kind === 'building') {
      const rest = c.slice(m.end);
      const en = /^의?(?:(\d)번?(?:입구|출입구|문)|(?:입구|출입구)(\d)번?)/.exec(rest);
      if (en) { m.entranceNo = en[1] || en[2]; m.end += en[0].length; }
      else { const g = /^의?(?:입구|출입구|현관|로비|건물|앞)/.exec(rest); if (g) m.end += g[0].length; }
      const fl = /^의?(지하|b)(\d+|[일이삼])층?|^의?(\d+|[일이삼오육칠팔구십])층/.exec(c.slice(m.end));
      if (fl) {
        const n = fl[2] || fl[3];
        const num = KO_NUM[n] || n;
        m.floorCode = fl[1] ? 'B' + num : num + 'F';
        m.floorText = fl[0].replace(/^의/, '');
        m.end += fl[0].length;
      }
    }
    const after = c.slice(m.end);
    const before = c.slice(Math.max(0, m.start - 3), m.start);
    if (/^(?:은|는|이|가)?(?:말고|아니고|아니라|빼고)/.test(after)) m.role = 'negated';
    else if (/^(?:으로|로|에)?(?:거쳐|들러|들렸|들렀|경유|지나서|지나)/.test(after) || /^(?:을|를)?(?:거쳐|들러|경유)/.test(after)) m.role = 'waypoint';
    else if (/^(?:에서|에서부터|부터|서출발|출발)/.test(after) || /^(?:이|가)?(?:근처인데|앞인데|인데|에있는데|에있어)/.test(after)) m.role = 'origin';
    else if (/^(?:에서|서)/.test(after)) m.role = 'origin';
    void before;
    out.push(m);
    i = prevEnd = m.end;
  }
  return out;
}

// "청운관 편의점" 처럼 건물 + 장소가 붙어 있으면 그 건물 안의 장소로 좁힌다. 없으면 지어내지 않고 알린다.
function mergeBuildingPlace(ms: Mention[], unsupported: RouteRequest['unsupported']): Mention[] {
  const out: Mention[] = [];
  for (let k = 0; k < ms.length; k++) {
    const a = ms[k], b = ms[k + 1];
    // "1164번 + 정류장" 처럼 뒤 말이 앞 말을 포함하는 일반 명사면 앞 것으로 합친다
    if (b && a.entry.kind === 'place' && b.entry.kind === 'place' && b.start - a.end <= 1 &&
        a.entry.targets.every(t => b.entry.targets.some(x => x.placeKey === t.placeKey))) {
      out.push({ ...a, end: b.end, role: b.role }); k++; continue;
    }
    if (b && a.entry.kind === 'building' && b.entry.kind === 'place' && b.start - a.end <= 1 && !a.floorCode && !a.entranceNo) {
      const bk = a.entry.targets[0].buildingKey;
      const inB = b.entry.targets.filter(t => t.buildingKey === bk);
      if (inB.length) { out.push({ ...b, start: a.start, entry: { ...b.entry, targets: inB } }); k++; continue; }
      if (b.entry.targets.every(t => t.buildingKey)) { // 다른 건물에만 있는 시설
        unsupported.push({ text: a.entry.surface + ' ' + b.entry.surface, reason: '지도에 그 장소가 아직 없음' });
        out.push({ ...a, role: b.role }); k++; continue;
      }
    }
    out.push(a);
  }
  return out;
}

function cand(e: { placeKey: string | null; buildingKey: string | null; name: string }): Candidate {
  return { placeKey: e.placeKey, buildingKey: e.buildingKey, name: e.name };
}

function emptyTarget(): Target { return { text: null, placeKey: null, buildingKey: null, floorKey: null, candidates: [] }; }

function resolve(m: Mention, c: string, pkg: MapPackage, unsupported: RouteRequest['unsupported']): Target {
  const t = emptyTarget();
  t.text = c.slice(m.start, m.end);
  let cands = m.entry.targets.slice();
  if (m.entranceNo && m.entry.kind === 'building') {
    const bk = m.entry.targets[0].buildingKey;
    const prefix = m.entry.namePrefix; // 은주1관 처럼 별칭으로 들어온 경우
    const hits = pkg.places.filter(p => p.buildingKey === bk && p.category === 'entrance' &&
      p.name.replace(/\s/g, '').indexOf('입구(' + m.entranceNo + ')') >= 0 && (!prefix || p.name.replace(/\s/g, '').indexOf(prefix) === 0));
    if (hits.length) cands = hits.map(p => cand({ placeKey: p.key, buildingKey: p.buildingKey, name: p.name }));
    else unsupported.push({ text: t.text, reason: '지도에 그 입구 번호가 없음' });
  }
  if (cands.length === 1) { t.placeKey = cands[0].placeKey; t.buildingKey = cands[0].buildingKey; }
  else {
    t.candidates = cands;
    const bks = uniq(cands.map(x => x.buildingKey));
    if (bks.length === 1 && bks[0]) t.buildingKey = bks[0];
  }
  if (m.floorCode) {
    const bk = t.buildingKey;
    const f = bk ? pkg.floors.find(x => x.buildingKey === bk && x.code === m.floorCode) : undefined;
    if (f) t.floorKey = f.key;
    else unsupported.push({ text: m.floorText || m.floorCode, reason: '지도에 그 층이 없음' });
  }
  return t;
}

function uniq<T>(a: T[]): T[] { const o: T[] = []; for (const x of a) if (o.indexOf(x) < 0) o.push(x); return o; }

// ── 조건 사전 ─────────────────────────────────────────
const AVOID_STAIRS = /계단(?:ㄴㄴ|노노|x|ㄴ)|계단(?:은|이|을|도)?(?:없이|없는|없게|말고|빼고|피해|피하|안쓰|안타|안올|안내려|안거치|안가|못|싫|힘들|무서|최대한없|은좀|금지|절대)|엘리베이터(?:로)?만|휠체어|유모차|목발|깁스|다리(?:를|가)?(?:다쳐|다쳤|불편|부러)|거동(?:이)?불편|발목(?:을|이)?(?:삐|다쳐|접질)|보행기|전동스쿠터|계단(?:을|은)?(?:못|오를수없|내려갈수없)/;
const STAIRS_OK = /계단(?:으로|이라도|도괜찮|괜찮|상관없|오케이|타고|써도|가능)/;
const FEWER_STAIRS = /짐|캐리어|무거|박스|상자|힘들|피곤|지쳐|무릎|숨차|계단(?:적게|덜|최소|조금|좀덜)/;
const ELEVATOR = /엘리베이터/;
// 바퀴 달린 것: 휠체어·유모차는 필수(accessible), 캐리어는 선호(accessible 이지만 필수 아님)
const WHEELS_HARD = /휠체어|유모차|전동스쿠터/;
const WHEELS_SOFT = /캐리어/;
const FAST = /빨리|빠른|빠르게|급해|급하|급한|서둘|늦었|지각|시간(?:이)?없|얼른|후딱|바빠/;
const RAIN = /비(?:가|와|오|맞|안맞|올)|우산|지붕|눈(?:이)?와|눈(?:이)?오|소나기|장마|폭우/;
const NIGHT = /밤|야간|새벽|어두|어둡|깜깜|캄캄|늦게|늦은|무서|밝은|가로등|불켜/;
// 주 방식 고르는 순서. 필수(accessible > avoidStairs)가 늘 앞서고, 선호끼리는 이 순서.
const SOFT_ORDER: Mode[] = ['nightSafe', 'rainProtected', 'accessible', 'preferElevator', 'avoidStairs', 'fastest'];
const INDOOR = /실내|건물안|건물속|밖으로안|밖에안|안나가|밖에나가기싫|추워|추운|더워|더운|미세먼지/;
const UNSUP: [RegExp, string, string][] = [
  [/조용/, '조용한 길', NO_DATA + '(소음)'],
  [/사람(?:이)?(?:적|없|안많|별로없)|붐비|북적|한산|혼잡|복잡하지않|덜붐|사람많은데|사람많은곳피/, '사람 적은 길', NO_DATA + '(붐빔)'],
  [/경치|예쁜|이쁜|산책|나무|꽃|풍경|분위기/, '경치 좋은 길', NO_DATA + '(경관)'],
  [/그늘|햇빛|햇볕|땡볕/, '그늘', NO_DATA + '(그늘)'],
  [/오르막|언덕|경사(?:없|완만|낮|덜)|비탈/, '오르막 피하기', '오르막만 피하는 경로 방식이 아직 없음'],
  [/흡연|담배/, '흡연 구역', NO_DATA + '(흡연 구역)'],
  [/자판기|정수기|화장실들러|와이파이/, '편의시설 경유', NO_DATA + '(편의시설)'],
];

export function parseRouteRequest(text: string, pkg: MapPackage, lexicon?: Lexicon): RouteRequest {
  const lex = lexicon || buildLexicon(pkg);
  const c = normalize(text);
  const unsupported: RouteRequest['unsupported'] = [];
  const mentions = mergeBuildingPlace(findMentions(c, lex, wordStarts(text)), unsupported);

  // 지도에 없는 장소 이름
  for (const u of lex.unknownPlaces) if (c.indexOf(u.surface) >= 0) unsupported.push({ text: u.label, reason: '지도에 그 장소가 아직 없음' });

  const dests = mentions.filter(m => m.role === 'dest');
  const origins = mentions.filter(m => m.role === 'origin');
  const ways = mentions.filter(m => m.role === 'waypoint');

  const destination = dests.length ? resolve(dests[dests.length - 1], c, pkg, unsupported) : emptyTarget();
  const useCur = /여기|지금위치|현재위치|내위치|지금있는곳|이근처|현위치/.test(c);
  const o = origins.length ? resolve(origins[0], c, pkg, unsupported) : emptyTarget();
  const origin = { ...o, useCurrentLocation: !origins.length };
  if (useCur && !origins.length) origin.text = '현재 위치';
  const waypoints = ways.map(m => resolve(m, c, pkg, unsupported));

  // 조건
  const mandatory: Mandatory[] = [];
  const preferences: Preference[] = [];
  const stairsOk = /계단없이말고/.test(c) || (STAIRS_OK.test(c) && !/계단(?:으로|이라도)?(?:말고|없이|빼고)/.test(c));
  if (!stairsOk && AVOID_STAIRS.test(c)) mandatory.push('avoidStairs');
  if (/휠체어/.test(c)) mandatory.push('wheelchairNeeded');
  if (!stairsOk && mandatory.indexOf('avoidStairs') < 0 && FEWER_STAIRS.test(c)) preferences.push('fewerStairs');
  if (INDOOR.test(c)) preferences.push('indoor');
  for (const [re, label, reason] of UNSUP) if (re.test(c)) unsupported.push({ text: label, reason });

  let timeLimitMin: number | null = null;
  const tm = /(\d+|[일이삼사오육칠팔구십]+)분(?:안|내|이내|만에|밖에|남|뒤|후|까지)/.exec(c);
  if (tm) timeLimitMin = koNum(tm[1]);

  // 방식: 길은 만들지 않고 조건만 고른다. 필수 조건이 있으면 그 방식이 주 방식, 선호는 보조로.
  const hard: Mode | null = !stairsOk && WHEELS_HARD.test(c) ? 'accessible' : mandatory.indexOf('avoidStairs') >= 0 ? 'avoidStairs' : null;
  const soft: Mode[] = [];
  if (NIGHT.test(c.replace(/계단(?:은|이|을|도)?무서/g, ''))) soft.push('nightSafe');
  if (RAIN.test(c) || preferences.indexOf('indoor') >= 0) soft.push('rainProtected');
  if (!stairsOk && WHEELS_SOFT.test(c)) soft.push('accessible');
  if (ELEVATOR.test(c) && !/엘리베이터(?:말고|없이|안|싫|기다리기싫)/.test(c)) soft.push('preferElevator');
  if (preferences.indexOf('fewerStairs') >= 0) soft.push('avoidStairs');
  if (FAST.test(c) || timeLimitMin !== null) soft.push('fastest');
  const modes = SOFT_ORDER.filter(x => soft.indexOf(x) >= 0);
  if (hard) modes.unshift(hard);
  const all = uniq(modes);
  const mode: Mode = all.length ? all[0] : 'shortest';
  const secondaryModes = all.slice(1).filter(x => !(mode === 'accessible' && x === 'avoidStairs'));

  // 재확인
  let needsClarification: RouteRequest['needsClarification'] = null;
  const stairsConflict = mandatory.indexOf('avoidStairs') >= 0 && /계단으로(?:가|올라|내려)/.test(c) && !/휠체어|유모차|목발|깁스/.test(c);
  if (stairsConflict) needsClarification = { question: '계단을 피할까요, 계단으로 갈까요?' };
  else if (!destination.text) {
    needsClarification = { question: unsupported.some(u => u.reason === '지도에 그 장소가 아직 없음') ? '그 장소는 지도에 아직 없습니다. 건물 이름으로 말해 주세요.' : '어디로 갈까요?' };
  } else if (!destination.placeKey && !destination.buildingKey) {
    needsClarification = { question: '"' + destination.text + '"이(가) 여러 곳입니다: ' + destination.candidates.map(x => x.name).join(' / ') + ' 중 어디인가요?' };
  } else if (unsupported.some(u => u.reason === '지도에 그 장소가 아직 없음')) {
    needsClarification = { question: '말한 장소가 지도에 없습니다. ' + destination.text + '(으)로 갈까요?' };
  } else if (!origin.useCurrentLocation && !origin.placeKey && !origin.buildingKey) {
    needsClarification = { question: '출발지 "' + origin.text + '"이(가) 여러 곳입니다: ' + origin.candidates.map(x => x.name).join(' / ') + ' 중 어디인가요?' };
  }

  return { v: 1, destination, origin, waypoints, mode, secondaryModes, mandatory, preferences, timeLimitMin, unsupported, needsClarification };
}

function koNum(s: string): number {
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  const d: Record<string, number> = { 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 칠: 7, 팔: 8, 구: 9 };
  let n = 0, cur = 0;
  for (const ch of s) { if (ch === '십') { n += (cur || 1) * 10; cur = 0; } else cur = d[ch] || 0; }
  return n + cur;
}
