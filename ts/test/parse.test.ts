import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { parseRouteRequest } from '../src/parse';
import type { MapPackage } from '../src/types';

const pkg: MapPackage = JSON.parse(readFileSync(new URL('../../data/package.bin', import.meta.url), 'utf8'));
const p = (t: string) => parseRouteRequest(t, pkg);

describe('parseRouteRequest', () => {
  it('건물 + 층', () => {
    const r = p('북악관 3층 가는 길');
    expect(r.destination.buildingKey).toBe('b:북악관');
    expect(r.destination.floorKey).toBe('f:북악관:3F');
    expect(r.origin.useCurrentLocation).toBe(true);
  });
  it('지하 층 표기 B1/지하 1층', () => {
    expect(p('유담관 B1').destination.floorKey).toBe('f:유담관:B1');
    expect(p('유담관 지하 1층').destination.floorKey).toBe('f:유담관:B1');
  });
  it('없는 층(4층)은 unsupported, 지어내지 않음', () => {
    const r = p('북악관 4층');
    expect(r.destination.floorKey).toBeNull();
    expect(r.unsupported.some(u => u.reason.indexOf('층') >= 0)).toBe(true);
  });
  it('출발지/목적지', () => {
    const r = p('청운관에서 한림관까지 계단 없이');
    expect(r.origin.buildingKey).toBe('b:청운관');
    expect(r.destination.buildingKey).toBe('b:한림관');
    expect(r.mandatory).toEqual(['avoidStairs']);
    expect(r.mode).toBe('avoidStairs');
  });
  it('계단 허용(함정): 계단으로 빨리 → 필수 조건 없음, 빠른 길', () => {
    const r = p('계단으로 빨리 혜인관');
    expect(r.mandatory).toEqual([]);
    expect(r.mode).toBe('fastest');
  });
  it('휠체어 → 필수 + accessible, 정보 없음으로 돌려보내지 않음', () => {
    const r = p('휠체어로 유담관');
    expect(r.mandatory).toEqual(['avoidStairs', 'wheelchairNeeded']);
    expect(r.mode).toBe('accessible');
    expect(r.unsupported).toEqual([]);
  });
  it('비는 rainProtected, 조용함·붐빔은 unsupported, preferences 에 넣지 않음', () => {
    const r = p('비 오고 조용하고 사람 적은 길로 청운관');
    expect(r.preferences).toEqual([]);
    expect(r.mode).toBe('rainProtected');
    expect(r.unsupported.length).toBe(2);
    expect(r.unsupported[0].reason).toContain('지도에 그 정보가 아직 없음');
  });
  it('모호한 장소 → 재확인', () => {
    const r = p('정문 어떻게 가');
    expect(r.destination.candidates.length).toBe(2);
    expect(r.needsClarification).not.toBeNull();
  });
  it('지도에 없는 장소 → 지어내지 않음', () => {
    const r = p('도서관 가고 싶어');
    expect(r.destination.placeKey).toBeNull();
    expect(r.needsClarification).not.toBeNull();
  });
  it('모든 장소 key 가 꾸러미에 있음', () => {
    const keys = new Set(pkg.places.map(x => x.key));
    for (const t of ['편의점', '후문', '1164번 정류장', '은주1관 2번 입구', '분수광장']) {
      const k = p(t).destination.placeKey;
      expect(k && keys.has(k)).toBe(true);
    }
  });
  it('짧은 이름이 단어 가운데서 잡히지 않음(가서 문예관 ≠ 서문)', () => {
    expect(p('계단으로 올라가서 문예관').destination.buildingKey).toBe('b:문예관');
  });
});

describe('경로 방식 7가지', () => {
  const m = (t: string) => { const r = p(t); return [r.mode, r.secondaryModes, r.mandatory] as const; };
  it('조건 없으면 shortest, 보조 방식 없음', () => {
    expect(m('북악관 가는 길')).toEqual(['shortest', [], []]);
  });
  it('빠른 길·급해·늦었어·몇 분 안 → fastest', () => {
    for (const t of ['한림관 빠른 길', '급해 청운관', '수업 늦었어 북악관', '10분 안에 유담관', '서둘러야 돼 본관'])
      expect(p(t).mode).toBe('fastest');
  });
  it('휠체어·유모차 → accessible(필수), 캐리어 무거움 → accessible(선호)', () => {
    expect(m('유모차 끌고 대일관')).toEqual(['accessible', [], ['avoidStairs']]);
    expect(m('캐리어가 무거워서 기숙사')).toEqual(['accessible', [], []]);
    expect(p('캐리어가 무거워서 기숙사').preferences).toEqual(['fewerStairs']);
  });
  it('짐 많아 계단 없이 → avoidStairs 그대로', () => {
    expect(m('짐 많아서 계단 없이 북악관')).toEqual(['avoidStairs', [], ['avoidStairs']]);
  });
  it('비·우산 없음·눈·실내로 → rainProtected, 정보 없음 아님', () => {
    for (const t of ['비 와서 청운관', '우산 없는데 한림관', '눈 와서 본관', '실내로만 가는 길 청운관']) {
      const r = p(t);
      expect(r.mode).toBe('rainProtected');
      expect(r.unsupported).toEqual([]);
    }
  });
  it('밤·어두워·늦게·무서워·밝은 길 → nightSafe', () => {
    for (const t of ['밤에 기숙사 가는 길', '어두워서 본관', '늦게 끝나서 정문까지', '혼자 가기 무서워 유담관', '밝은 길로 기숙사']) {
      const r = p(t);
      expect(r.mode).toBe('nightSafe');
      expect(r.unsupported).toEqual([]);
    }
  });
  it('계단이 무서워는 nightSafe 가 아니라 계단 피하기', () => {
    expect(m('계단이 무서워 북악관')).toEqual(['avoidStairs', [], ['avoidStairs']]);
  });
  it('엘리베이터 → preferElevator, 엘리베이터 말고는 아님', () => {
    expect(p('엘베 타고 문예관 10층').mode).toBe('preferElevator');
    expect(p('엘리베이터 말고 계단으로 청운관').mode).toBe('shortest');
  });
  it('필수 조건 우선: accessible > avoidStairs, 선호 방식은 보조로', () => {
    expect(m('휠체어로 계단 없이 유담관')).toEqual(['accessible', [], ['avoidStairs', 'wheelchairNeeded']]);
    expect(m('휠체어인데 비 와요 유담관')).toEqual(['accessible', ['rainProtected'], ['avoidStairs', 'wheelchairNeeded']]);
    expect(m('엘베로만 가는 길 유담관')).toEqual(['avoidStairs', ['preferElevator'], ['avoidStairs']]);
  });
  it('선호끼리는 하나를 주 방식으로, 나머지는 보조로(nightSafe > rainProtected > accessible > preferElevator > avoidStairs > fastest)', () => {
    expect(m('밤인데 비 오고 급해 기숙사')).toEqual(['nightSafe', ['rainProtected', 'fastest'], []]);
    expect(m('짐 많은데 엘베 타고 대일관 6층')).toEqual(['preferElevator', ['avoidStairs'], []]);
  });
});
