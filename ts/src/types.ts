// 지도 꾸러미(schemaVersion 1)에서 이 모듈이 쓰는 부분만.
export interface PkgBuilding { key: string; name: string; aliases: string[] }
export interface PkgFloor { key: string; buildingKey: string; code: string }
export interface PkgPlace { key: string; name: string; aliases: string[]; buildingKey: string | null; floorKey: string | null; category: string }
export interface MapPackage { schemaVersion: number; buildings: PkgBuilding[]; floors: PkgFloor[]; places: PkgPlace[] }

export type Mode = 'shortest' | 'avoidStairs' | 'preferElevator';
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
  mode: Mode;
  mandatory: Mandatory[];
  preferences: Preference[];   // 지도에 자료가 있는 선호만. 자료 없는 것은 unsupported 로
  timeLimitMin: number | null;
  unsupported: { text: string; reason: string }[];
  needsClarification: { question: string } | null;
}
