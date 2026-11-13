import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {querySnapshot} from '../lib/snapshot.mjs';
const observations=JSON.parse(readFileSync(new URL('../../data/public_observations.json',import.meta.url),'utf8'));
test('verified browser sample is limited to X and Instagram and keeps original capture dates',()=>{
 const snapshot={version:1,accounts:observations.accounts,posts:[],opinions:observations.opinions,opinion_sources:[],opinions_truncated:true};
 const all=querySnapshot(snapshot,'/opinions?start=2026-11-11&end=2026-11-13',new Date('2026-11-13T15:00:00Z'));
 assert.equal(all.total,16);
 assert.equal(querySnapshot(snapshot,'/opinions?start=2026-11-11&end=2026-11-13&platform=x').total,1);
 assert.equal(querySnapshot(snapshot,'/opinions?start=2026-11-11&end=2026-11-13&platform=instagram').total,15);
 assert.equal(querySnapshot(snapshot,'/opinions?start=2026-11-13&end=2026-11-13').total,0);
 assert.equal(new Set(all.items.map(o=>o.captured_at)).size,1);
 assert.ok(all.items.every(o=>o.collection_method==='browser_observation'&&o.sentiment==='indeterminado'));
});
