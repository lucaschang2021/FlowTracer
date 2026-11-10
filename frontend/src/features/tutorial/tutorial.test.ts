import{describe,expect,it}from'vitest';
import{decodeTutorialProgress,reduceTutorial,TUTORIAL_STEPS,type TutorialProgress}from'./Tutorial';
import{TUTORIAL_IDS}from'./tutorialAdapter';
const session='session-a';
const start=():TutorialProgress=>({version:1,session,index:0,completed:[],skipped:[],memorySearched:false,active:true});
describe('tutorial progress',()=>{
 it('rejects malformed, incompatible and foreign-session storage',()=>{
  expect(decodeTutorialProgress({version:1,session,index:99,completed:[],skipped:[],memorySearched:false,active:true},session).index).toBe(0);
  expect(decodeTutorialProgress({version:2},session).session).toBe(session);
  expect(decodeTutorialProgress({...start(),session:'old'},session).index).toBe(0);
  expect(decodeTutorialProgress({...start(),index:2,completed:['radar'],skipped:[]},session).index).toBe(0);
  expect(decodeTutorialProgress({...start(),index:1,completed:['source'],skipped:[]},session).index).toBe(0);
  expect(decodeTutorialProgress({...start(),index:1,completed:['radar'],skipped:['radar']},session).index).toBe(0);
 });
 it('preserves a valid inactive resumable state',()=>{const value={...start(),index:2,completed:['radar'] as const,skipped:['source'] as const,active:false};expect(decodeTutorialProgress(value,session)).toEqual(value);});
 it('ignores out-of-order, wrong-id and stale-session successes',()=>{const state=start();expect(reduceTutorial(state,{type:'bookmark.created',session,documentId:TUTORIAL_IDS.document})).toBe(state);expect(reduceTutorial(state,{type:'radar.created',session,radarId:'wrong'})).toBe(state);expect(reduceTutorial(state,{type:'radar.created',session:'old',radarId:TUTORIAL_IDS.radar})).toBe(state);});
 it('advances only the matching successful identity',()=>{const next=reduceTutorial(start(),{type:'radar.created',session,radarId:TUTORIAL_IDS.radar});expect(next.index).toBe(1);expect(next.completed).toEqual(['radar']);});
 it('requires a matching memory hit before the matching note save',()=>{let state={...start(),index:4,completed:TUTORIAL_STEPS.slice(0,4) as TutorialProgress['completed']};state=reduceTutorial(state,{type:'bookmark.updated',session,bookmarkId:TUTORIAL_IDS.bookmark});expect(state.index).toBe(4);state=reduceTutorial(state,{type:'memory.searched',session,documentId:TUTORIAL_IDS.document});expect(state.memorySearched).toBe(true);state=reduceTutorial(state,{type:'bookmark.updated',session,bookmarkId:TUTORIAL_IDS.bookmark});expect(state.index).toBe(5);});
});
