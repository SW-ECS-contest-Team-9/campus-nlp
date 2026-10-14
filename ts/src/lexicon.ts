// 꾸러미에서 장소 사전을 만든다. 장소를 지어내지 않는다: 모든 목표는 꾸러미 key.
import type { Candidate, MapPackage, PkgPlace } from './types';

export interface LexEntry { surface: string; kind: 'building' | 'place'; targets: Candidate[]; namePrefix: string | null }
export interface Lexicon { entries: LexEntry[]; unknownPlaces: { surface: string; label: string }[] }

const sq = (s: string) => s.toLowerCase().replace(/\s+/g, '');

// 일반어 → 꾸러미 장소 고르기(이름·분류 조건). 결과가 0이면 사전에 넣지 않는다.
const FACILITY: [string[], (p: PkgPlace) => boolean][] = [
  [['편의점', '매점'], p => p.category === 'facility' && p.name.indexOf('편의점') >= 0],
  [['라운지', '휴게실'], p => p.name.indexOf('라운지') >= 0],
  [['주차장'], p => p.category === 'parking'],
  [['제1주차장', '하단주차장', 'p2'], p => p.name.indexOf('하단 주차장') >= 0],
  [['지하1층주차장', '운동장지하1층주차장', '운동장지하주차장1층'], p => p.name.indexOf('운동장 지하 1층 주차장') >= 0],
  [['지하2층주차장', '운동장지하2층주차장', '운동장지하주차장2층'], p => p.name.indexOf('운동장 지하 2층 주차장') >= 0],
  [['p1'], p => p.name.indexOf('P1') >= 0],
  [['버스정류장', '정류장', '버스타는곳', '정거장'], p => p.category === 'bus_stop'],
  [['1164번', '1164번버스', '1164'], p => p.name.indexOf('1164') >= 0],
  [['2115번', '2115번버스', '2115'], p => p.name.indexOf('2115') >= 0],
  [['정문'], p => p.name.indexOf('정문') >= 0],
  [['후문', '서문', '서문주차장'], p => p.name.indexOf('서문(후문)') >= 0],
  [['분수광장', '분수대'], p => p.name.indexOf('분수 광장') >= 0],
  [['연결통로', '구름다리'], p => p.name.indexOf('연결통로') >= 0],
  [['본관한림관연결통로', '본관연결통로'], p => p.name.indexOf('본관–한림관') >= 0],
  [['한림관은주1관연결통로', '은주관연결통로'], p => p.name.indexOf('한림관–은주1관') >= 0],
  [['지하통로', '지하도'], p => p.name.indexOf('지하통로') >= 0],
  [['뒷문'], p => p.name.indexOf('뒷문') >= 0],
];

// 지도에 아직 없는 장소 일반어(목적지로 말하면 "없음"이라고 답한다)
const UNKNOWN = ['도서관', '학생식당', '학식', '식당', '카페', '화장실', '프린터', '행정실', '학과사무실', '보건실', '체육관', '강당', '헬스장', '은행', 'atm', '우체국', '스터디룸', '열람실'];

export function buildLexicon(pkg: MapPackage): Lexicon {
  const map = new Map<string, LexEntry>();
  const add = (surface: string, kind: LexEntry['kind'], t: Candidate, namePrefix: string | null = null) => {
    const s = sq(surface);
    if (s.length < 2) return;
    const e = map.get(s);
    if (!e) { map.set(s, { surface: s, kind, targets: [t], namePrefix }); return; }
    if (!e.targets.some(x => x.placeKey === t.placeKey && x.buildingKey === t.buildingKey)) e.targets.push(t);
  };
  for (const b of pkg.buildings) {
    const t = { placeKey: null, buildingKey: b.key, name: b.name };
    add(b.name, 'building', t);
    const stem = sq(b.name).replace(/관$/, '');
    if (stem.length >= 2 && stem !== sq(b.name)) add(stem, 'building', t);
    for (const a of b.aliases) {
      // "은주1관" 같은 별칭만. "문예관 저층부" 같은 설명형 별칭은 건물 이름과 같게 취급
      add(a, 'building', t, /^[가-힣]+\d관$/.test(a) ? sq(a) : null);
    }
  }
  for (const p of pkg.places) {
    const t = { placeKey: p.key, buildingKey: p.buildingKey, name: p.name };
    const head = p.name.split('=')[0].replace(/\(.*?\)/g, '').replace(/:.*/, '');
    if (p.category !== 'entrance' || /지하통로/.test(p.name) === false) add(head, 'place', t);
    for (const a of p.aliases) add(a, 'place', t);
    const en = /^(\S+)\s*입구\((\d)\)/.exec(p.name);
    if (en) { add(en[1] + '입구' + en[2], 'place', t); add(en[1] + en[2] + '번입구', 'place', t); add(en[1] + '입구' + en[2] + '번', 'place', t); }
  }
  for (const [words, pick] of FACILITY) {
    const hits = pkg.places.filter(pick);
    for (const w of words) for (const p of hits) add(w, 'place', { placeKey: p.key, buildingKey: p.buildingKey, name: p.name });
  }
  const entries = Array.from(map.values()).sort((a, b) => b.surface.length - a.surface.length);
  return { entries, unknownPlaces: UNKNOWN.map(u => ({ surface: u, label: u })) };
}
