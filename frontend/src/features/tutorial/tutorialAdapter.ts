import type { CollectionQueued,CollectionRun,IntelligenceDetail,IntelligencePage,IntelligenceQuery,RadarCreateInput,RadarRecord,SourceCreateInput,SourcePage,SourceRecord } from '../../api/desktop';
import type { ActionPayload,Bookmark,BookmarkPage,MemorySearchInput,MemorySearchResult,NotificationItem,NotificationPage,NotificationQuery,NotificationReadAll,Opportunity,OpportunityPage,OpportunityQuery } from '../../api/product';

export const TUTORIAL_OWNER='00000000-0000-4000-8000-000000000901';
export const TUTORIAL_IDS={radar:'00000000-0000-4000-8000-000000000911',source:'00000000-0000-4000-8000-000000000912',run:'00000000-0000-4000-8000-000000000913',analysis:'00000000-0000-4000-8000-000000000914',document:'00000000-0000-4000-8000-000000000915',bookmark:'00000000-0000-4000-8000-000000000916',opportunity:'00000000-0000-4000-8000-000000000917',notification:'00000000-0000-4000-8000-000000000918'} as const;
export const TUTORIAL_DATA_KEY='flowtracer:tutorial:v1:data';const now='2026-11-04T12:00:00.000Z';
type State={version:1;session:string;radar:RadarRecord|null;source:SourceRecord|null;bound:boolean;runId:string|null;polls:number;collected:boolean;bookmarked:boolean;note:string|null;notificationRead:boolean};
const makeSession=()=>crypto.randomUUID();
const fresh=(session=makeSession()):State=>({version:1,session,radar:null,source:null,bound:false,runId:null,polls:0,collected:false,bookmarked:false,note:null,notificationRead:false});
const load=(storage:Storage):State=>{try{const value=JSON.parse(storage.getItem(TUTORIAL_DATA_KEY)??'null');return value?.version===1&&typeof value.session==='string'&&typeof value.bound==='boolean'&&typeof value.collected==='boolean'&&typeof value.bookmarked==='boolean'&&typeof value.notificationRead==='boolean'?value:fresh();}catch{return fresh();}};
const signal=():IntelligenceDetail=>({id:TUTORIAL_IDS.analysis,documentId:TUTORIAL_IDS.document,radarId:TUTORIAL_IDS.radar,title:'Guided practice signal',canonicalUrl:'https://practice.invalid/signal',summary:'A traceable local signal created by the guided collection.',category:'tutorial',relevance:92,importance:84,novelty:76,impact:81,radarScore:86.55,recommendation:'must_read',reason:'Matches the practice Radar goal.',status:'completed',errorCode:null,errorMessage:null,pipelineVersion:'tutorial-v1',promptVersion:'tutorial-v1',provider:'local-fixture',model:'none',bookmarked:false,createdAt:now,updatedAt:now,content:'Local tutorial content. No network or account was used.',author:'FlowTracer tutorial',language:'en',wordCount:10});
const opportunity=():Opportunity=>({id:TUTORIAL_IDS.opportunity,sourceId:TUTORIAL_IDS.source,title:'Guided practice research brief',platform:'FlowTracer practice',description:'A labeled local opportunity used only to learn the read-only review flow.',budgetMin:1200,budgetMax:1800,currency:'USD',skills:['research','python'],deadline:'2026-12-01T00:00:00.000Z',publishedAt:now,estimatedEffortHours:12,deliveryType:'fixed',profileVersion:'tutorial-v1',sourceUrl:'https://practice.invalid/opportunity',status:'active',createdAt:now,updatedAt:now,score:{id:'00000000-0000-4000-8000-000000000919',radarId:TUTORIAL_IDS.radar,scoreVersion:'tutorial-v1',hardFilterPassed:true,disqualifiers:[],fit:90,expectedValue:84,completionProbability:88,effortEfficiency:82,timeToDelivery:86,competition:30,ambiguity:18,risk:12,overallScore:86.55,recommendation:'review',reason:'Practice payload for human review only.',scoredAt:now}});

export type TutorialAdapter=ReturnType<typeof createTutorialAdapter>;
export function createTutorialAdapter(storage:Storage=window.localStorage){
 let state=load(storage);const save=()=>{try{storage.setItem(TUTORIAL_DATA_KEY,JSON.stringify(state));}catch{/* optional */}};const collected=()=>{if(!state.collected)throw new Error('Complete the guided collection first.');};
 const bookmark=():Bookmark=>{const item=signal();return{id:TUTORIAL_IDS.bookmark,documentId:item.documentId,note:state.note,title:item.title,canonicalUrl:item.canonicalUrl,analysisId:item.id,radarId:item.radarId,summary:item.summary??null,category:item.category??null,radarScore:item.radarScore??null,recommendation:item.recommendation??null,createdAt:now,updatedAt:now};};
 const notification=():NotificationItem=>({id:TUTORIAL_IDS.notification,kind:'opportunity',analysisId:null,opportunityId:TUTORIAL_IDS.opportunity,title:'Review the guided practice opportunity',content:'A local practice item is ready for human review.',priority:'high',reason:'Tutorial completion step',url:null,status:state.notificationRead?'read':'unread',createdAt:now,readAt:state.notificationRead?now:null});
 save();
 return{
  session(){return state.session;},
  reset(){state=fresh();save();return state.session;},
  radarPage(){return{items:state.radar?[state.radar]:[],page:1,pageSize:100,total:state.radar?1:0};},
  async createRadar(input:RadarCreateInput){const value:RadarRecord={id:TUTORIAL_IDS.radar,name:input.name,goal:input.goal,description:input.description??null,radarType:input.radarType,categories:[],keywords:[],status:'active',notificationThreshold:70};state={...state,radar:value};save();return value;},
  async sources(page=1,pageSize=20):Promise<SourcePage>{const items=state.source?[state.source]:[];return{items,page,pageSize,total:items.length};},
  async radarSources(_radar:string,page=1,pageSize=20):Promise<SourcePage>{const items=state.source&&state.bound?[state.source]:[];return{items,page,pageSize,total:items.length};},
  async createSource(input:SourceCreateInput){const value:SourceRecord={id:TUTORIAL_IDS.source,name:input.name,sourceType:input.sourceType,url:input.url,normalizedUrl:input.url,pollIntervalMinutes:input.pollIntervalMinutes,status:'active',sourceFamily:input.sourceFamily??'generic_web'};state={...state,source:value};save();return value;},
  async bindSource(radar:string,source:string){if(radar!==TUTORIAL_IDS.radar||source!==TUTORIAL_IDS.source)throw new Error('Practice identities do not match.');state={...state,bound:true};save();},
  async unbindSource(_radar:string,source:string){if(source===TUTORIAL_IDS.source){state={...state,bound:false};save();}},
  async collectSource(source:string,_key:string):Promise<CollectionQueued>{if(!state.bound||source!==TUTORIAL_IDS.source)throw new Error('Bind the practice source first.');const runId=crypto.randomUUID();state={...state,runId,polls:0,collected:false};save();return{runId,status:'queued'};},
  async collectionRun(run:string,source:string):Promise<CollectionRun>{if(run!==state.runId||source!==TUTORIAL_IDS.source)throw new Error('Practice run identity does not match.');const polls=state.polls+1,done=polls>=2;state={...state,polls,collected:done};save();return{id:run,sourceId:source,status:done?'succeeded':'running',fetchedCount:done?1:0,createdCount:done?1:0,duplicateCount:0,failedCount:0};},
  async intelligence(_query:IntelligenceQuery):Promise<IntelligencePage>{const items=state.collected?[{...signal(),bookmarked:state.bookmarked}]:[];return{items,page:1,pageSize:10,total:items.length};},
  async intelligenceDetail(id:string,radar:string){collected();if(id!==TUTORIAL_IDS.analysis||radar!==TUTORIAL_IDS.radar)throw new Error('Practice signal identity does not match.');return{...signal(),bookmarked:state.bookmarked};},
  async createBookmark(document:string){collected();if(document!==TUTORIAL_IDS.document)throw new Error('Practice document identity does not match.');state={...state,bookmarked:true};save();return bookmark();},
  async bookmarks(page=1,pageSize=10):Promise<BookmarkPage>{const items=state.bookmarked?[bookmark()]:[];return{items,page,pageSize,total:items.length};},
  async updateBookmark(id:string,note:string|null){if(id!==TUTORIAL_IDS.bookmark||!state.bookmarked)throw new Error('Practice bookmark identity does not match.');const clean=note?.trim();if(!clean)throw new Error('Add a note before saving this tutorial step.');state={...state,note:clean};save();return bookmark();},
  async deleteBookmark(id:string){if(id===TUTORIAL_IDS.bookmark){state={...state,bookmarked:false,note:null};save();}},
  async searchMemory(input:MemorySearchInput):Promise<MemorySearchResult>{collected();const query=input.query.trim().toLowerCase(),matches=query.includes('practice')||query.includes('signal')||query.includes('练习')||query.includes('信号'),visible=matches&&(!input.bookmarkedOnly||state.bookmarked);return{query:input.query,topK:input.topK,items:visible?[{analysisId:TUTORIAL_IDS.analysis,documentId:TUTORIAL_IDS.document,radarId:TUTORIAL_IDS.radar,title:signal().title,canonicalUrl:signal().canonicalUrl,summary:signal().summary??null,category:signal().category??null,radarScore:signal().radarScore??null,recommendation:signal().recommendation??null,excerpt:'Traceable guided-practice memory result.',similarity:1,occurredAt:now,bookmarked:state.bookmarked}]:[]};},
  async opportunities(input:OpportunityQuery):Promise<OpportunityPage>{const items=state.collected?[opportunity()]:[];return{items,page:input.page,pageSize:input.pageSize,total:items.length};},
  async opportunity(id:string){collected();if(id!==TUTORIAL_IDS.opportunity)throw new Error('Practice opportunity identity does not match.');return opportunity();},
  async actionPayload(id:string):Promise<ActionPayload>{if(id!==TUTORIAL_IDS.opportunity)throw new Error('Practice opportunity identity does not match.');return{opportunityId:id,payloadVersion:'tutorial-v1',payload:{action:'review_only',requires_human_approval:true,execution:'disabled'},payloadHash:'tutorial-local-fixture-not-a-production-hash',generatedAt:now};},
  async notifications(input:NotificationQuery):Promise<NotificationPage>{const item=notification(),items=state.collected&&(!input.status||item.status===input.status)&&(!input.priority||item.priority===input.priority)?[item]:[];return{items,page:input.page,pageSize:input.pageSize,total:items.length};},
  async readNotification(id:string){if(id!==TUTORIAL_IDS.notification)throw new Error('Practice notification identity does not match.');state={...state,notificationRead:true};save();return notification();},
  async readAllNotifications():Promise<NotificationReadAll&{updatedIds:string[]}>{
   if(!state.collected)return{updatedCount:0,readAt:now,updatedIds:[]};
   const updatedIds=[TUTORIAL_IDS.notification];
   // An existing read item can still confirm the practice step after resume.
   if(state.notificationRead)return{updatedCount:0,readAt:now,updatedIds};
   state={...state,notificationRead:true};
   save();
   return{updatedCount:1,readAt:now,updatedIds};
  },
 };
}
