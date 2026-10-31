export type AvatarId='sprout'|'fox'|'moon'|'crystal'|'star'|'cloud';
export interface LevelStats {
 stars:1|2|3;bestMoves:number;bestTimeMs:number|null;
 lastMoves?:number;lastTimeMs?:number;plays:number;
 completedAt?:string;lastCompletedAt?:string;
}
export interface UserProfile {
 id:string;username:string;avatar:AvatarId;unlockedLevel:number;
 levelStats:Record<string,LevelStats>;createdAt:string;lastPlayed:string;
}
