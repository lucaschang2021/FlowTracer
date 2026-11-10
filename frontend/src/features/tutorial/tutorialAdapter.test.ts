import{describe,expect,it,vi}from'vitest';
import{createTutorialAdapter,TUTORIAL_IDS}from'./tutorialAdapter';
const storage=()=>{const values=new Map<string,string>();return{get length(){return values.size},clear:()=>values.clear(),getItem:(key:string)=>values.get(key)??null,key:(index:number)=>[...values.keys()][index]??null,removeItem:(key:string)=>{values.delete(key)},setItem:(key:string,value:string)=>{values.set(key,value)}} satisfies Storage;};
async function collected(api:ReturnType<typeof createTutorialAdapter>){await api.createRadar({name:'Practice',goal:'Learn',radarType:'custom'});await api.createSource({name:'Practice feed',sourceType:'rss',url:'https://practice.invalid/rss',pollIntervalMinutes:60,sourceFamily:'generic_web'});await api.bindSource(TUTORIAL_IDS.radar,TUTORIAL_IDS.source);const queued=await api.collectSource(TUTORIAL_IDS.source,'key');await api.collectionRun(queued.runId,TUTORIAL_IDS.source);await api.collectionRun(queued.runId,TUTORIAL_IDS.source);return queued.runId;}
describe('tutorial adapter isolation',()=>{
 it('persists its session before any practice operation',()=>{const store=storage();const first=createTutorialAdapter(store);const session=first.session();expect(createTutorialAdapter(store).session()).toBe(session);});
 it('invalidates an old run when data restarts',async()=>{const api=createTutorialAdapter(storage());const run=await collected(api);const old=api.session();const next=api.reset();expect(next).not.toBe(old);await expect(api.collectionRun(run,TUTORIAL_IDS.source)).rejects.toThrow('identity');});
 it('returns a memory hit only for a related query',async()=>{const api=createTutorialAdapter(storage());await collected(api);expect((await api.searchMemory({query:'unrelated',topK:10,bookmarkedOnly:false})).items).toHaveLength(0);expect((await api.searchMemory({query:'practice signal',topK:10,bookmarkedOnly:false})).items[0]?.documentId).toBe(TUTORIAL_IDS.document);});
 it('requires a non-empty note before completing the bookmark update',async()=>{const api=createTutorialAdapter(storage());await collected(api);await api.createBookmark(TUTORIAL_IDS.document);await expect(api.updateBookmark(TUTORIAL_IDS.bookmark,null)).rejects.toThrow('note');await expect(api.updateBookmark(TUTORIAL_IDS.bookmark,'  learned  ')).resolves.toMatchObject({note:'learned'});});
 it('leaves a newly collected notification unread after marking an empty list read',async()=>{
  const store=storage();
  const api=createTutorialAdapter(store);
  const writes=vi.spyOn(store,'setItem');
  const query={page:1,pageSize:10,status:null,priority:null};
  expect((await api.notifications(query)).items).toEqual([]);
  await expect(api.readAllNotifications()).resolves.toMatchObject({updatedCount:0,updatedIds:[]});
  const writesWhileEmpty=writes.mock.calls.length;

  await collected(api);

  expect((await api.notifications(query)).items).toEqual([
   expect.objectContaining({id:TUTORIAL_IDS.notification,status:'unread',readAt:null}),
  ]);
  expect(writesWhileEmpty).toBe(0);
 });
});
