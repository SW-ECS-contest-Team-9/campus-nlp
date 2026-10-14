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
  it('계단 허용(함정): 계단으로 빨리 → 필수 조건 없음', () => {
    const r = p('계단으로 빨리 혜인관');
    expect(r.mandatory).toEqual([]);
    expect(r.mode).toBe('shortest');
  });
  it('휠체어 → 필수 + 지도에 없는 부분은 말함', () => {
    const r = p('휠체어로 유담관');
    expect(r.mandatory).toEqual(['avoidStairs', 'wheelchairNeeded']);
    expect(r.unsupported.map(u => u.text)).toContain('휠체어');
  });
  it('지붕·조용함·붐빔은 unsupported, preferences 에 넣지 않음', () => {
    const r = p('비 오고 조용하고 사람 적은 길로 청운관');
    expect(r.preferences).toEqual([]);
    expect(r.unsupported.length).toBe(3);
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
