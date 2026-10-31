export type BiomeId = 'forest' | 'dusk' | 'neon' | 'cavern' | 'celestial';
export type Coord = [row: number, column: number];
export interface BridgeEffect { bridge_id: string; operation: 'TOGGLE' | 'SET_OPEN' | 'SET_CLOSED' }
export type Switch = { id: string; cell: Coord; effects: BridgeEffect[] } & (
  { type: 'SOFT' | 'HEAVY' } | { type: 'SPLIT'; destinations: [Coord, Coord] }
);
export interface Level {
  id: string; biomeId?: BiomeId; grid: string[]; start: Coord; goal: Coord;
  bridges: {id: string; cells: Coord[]; initial_enabled: boolean}[];
  switches: Switch[];
}
export interface CampaignEntry {
  id: string; file: string; title: string; subtitle: string;
  biomeId: BiomeId; chapter: number; chapterLevel: number;
  difficulty: 1 | 2 | 3 | 4 | 5; difficultyLabel: string; mechanics: string[];
}
export interface Campaign { version: 1; levels: CampaignEntry[] }
