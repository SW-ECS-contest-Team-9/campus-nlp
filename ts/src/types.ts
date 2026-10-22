// 지도 꾸러미(schemaVersion 1)에서 이 모듈이 쓰는 부분만.
export interface PkgBuilding { key: string; name: string; aliases: string[] }
export interface PkgFloor { key: string; buildingKey: string; code: string }
export interface PkgPlace { key: string; name: string; aliases: string[]; buildingKey: string | null; floorKey: string | null; category: string }
export interface MapPackage { schemaVersion: number; buildings: PkgBuilding[]; floors: PkgFloor[]; places: PkgPlace[] }

// 경로 방식 7가지(campus-backend mapdata/routing.py MODE_SPEC, GET /v1/route-modes 와 같은 이름)
export type Mode = 'shortest' | 'fastest' | 'avoidStairs' | 'accessible' | 'preferElevator' | 'rainProtected' | 'nightSafe';
export type Mandatory = 'avoidStairs' | 'wheelchairNeeded';
export type Preference = 'indoor' | 'fewerStairs' | 'covered' | 'quiet' | 'lessCrowded';

export interface Candidate { placeKey: string | null; buildingKey: string | null; name: string }
export interface Target {
  text: string | null;
  placeKey: string | null;     // 꾸러미 places.key
  buildingKey: string | null;  // 건물만 정해졌을 때(입구는 경로 엔진이 고름)
  floorKey: string | null;     // "3층" 등이 붙었을 때
  candidates: Candidate[];     // 모호할 때 후보
}
export interface RouteRequest {
  v: 1;
  destination: Target;
  origin: Target & { useCurrentLocation: boolean };
  waypoints: Target[];
  mode: Mode;                  // 주 방식(경로 계산에 넘기는 하나)
  secondaryModes: Mode[];      // 함께 말한 다른 방식(주 방식에 밀린 것, 우선순위 순)
  mandatory: Mandatory[];
  preferences: Preference[];   // 지도에 자료가 있는 선호만. 자료 없는 것은 unsupported 로
  timeLimitMin: number | null;
  unsupported: { text: string; reason: string }[];
  needsClarification: { question: string } | null;
}
