import { useCallback, useState } from 'react';
import { usePreferences } from '../../app/Preferences';
import { TUTORIAL_IDS } from './tutorialAdapter';
import './tutorial.css';

export const TUTORIAL_PROGRESS_KEY='flowtracer:tutorial:v1:progress';
export const TUTORIAL_STEPS=['radar','source','collection','signal','memory','opportunity','notification'] as const;
export type TutorialStep=typeof TUTORIAL_STEPS[number];
export type TutorialEvent=
 |{type:'radar.created';session:string;radarId:string}|{type:'source.bound';session:string;radarId:string;sourceId:string}
 |{type:'collection.succeeded';session:string;runId:string;sourceId:string;createdCount:number}|{type:'bookmark.created';session:string;documentId:string}
 |{type:'memory.searched';session:string;documentId:string}|{type:'bookmark.updated';session:string;bookmarkId:string}
 |{type:'opportunity.payloadViewed';session:string;opportunityId:string}|{type:'notification.read';session:string;notificationId:string};
export type TutorialProgress={version:1;session:string;index:number;completed:TutorialStep[];skipped:TutorialStep[];memorySearched:boolean;active:boolean};
const initial=(session:string):TutorialProgress=>({version:1,session,index:0,completed:[],skipped:[],memorySearched:false,active:true});
const validSteps=(value:unknown):value is TutorialStep[]=>Array.isArray(value)&&value.every(step=>TUTORIAL_STEPS.includes(step));
export const decodeTutorialProgress=(value:unknown,session:string):TutorialProgress=>{
 if(!value||typeof value!=='object')return initial(session);const item=value as Partial<TutorialProgress>;
 const index=item.index;
 if(item.version!==1||item.session!==session||typeof index!=='number'||!Number.isInteger(index)||index<0||index>TUTORIAL_STEPS.length||!validSteps(item.completed)||!validSteps(item.skipped)||typeof item.memorySearched!=='boolean'||typeof item.active!=='boolean')return initial(session);
 const completed=new Set(item.completed),skipped=new Set(item.skipped);
 if(completed.size!==item.completed.length||skipped.size!==item.skipped.length||item.completed.some(step=>skipped.has(step))||completed.size+skipped.size!==index)return initial(session);
 if(TUTORIAL_STEPS.some((step,position)=>position<index?!completed.has(step)&&!skipped.has(step):completed.has(step)||skipped.has(step)))return initial(session);
 if(item.completed.some((step,index)=>step!==TUTORIAL_STEPS.filter(value=>completed.has(value))[index])||item.skipped.some((step,index)=>step!==TUTORIAL_STEPS.filter(value=>skipped.has(value))[index]))return initial(session);
 if(item.memorySearched&&index!==4)return initial(session);
 return item as TutorialProgress;
};
const read=(session:string):TutorialProgress=>{try{return decodeTutorialProgress(JSON.parse(localStorage.getItem(TUTORIAL_PROGRESS_KEY)??'null'),session);}catch{return initial(session);}};
const expected=(step:TutorialStep,event:TutorialEvent,state:TutorialProgress)=>{
 if(step==='radar')return event.type==='radar.created'&&event.radarId===TUTORIAL_IDS.radar;
 if(step==='source')return event.type==='source.bound'&&event.radarId===TUTORIAL_IDS.radar&&event.sourceId===TUTORIAL_IDS.source;
 if(step==='collection')return event.type==='collection.succeeded'&&event.runId.length>0&&event.sourceId===TUTORIAL_IDS.source&&event.createdCount>0;
 if(step==='signal')return event.type==='bookmark.created'&&event.documentId===TUTORIAL_IDS.document;
 if(step==='memory')return event.type==='bookmark.updated'&&event.bookmarkId===TUTORIAL_IDS.bookmark&&state.memorySearched;
 if(step==='opportunity')return event.type==='opportunity.payloadViewed'&&event.opportunityId===TUTORIAL_IDS.opportunity;
 return event.type==='notification.read'&&event.notificationId===TUTORIAL_IDS.notification;
};
export function reduceTutorial(state:TutorialProgress,event:TutorialEvent):TutorialProgress{
 if(event.session!==state.session)return state;
 const step=TUTORIAL_STEPS[state.index];if(!step)return state;
 if(step==='memory'&&event.type==='memory.searched'&&event.documentId===TUTORIAL_IDS.document)return{...state,memorySearched:true};
 if(!expected(step,event,state))return state;
 return{...state,index:state.index+1,completed:[...state.completed,step],memorySearched:false};
}
export function useTutorial(session:string){
 const[progress,setProgress]=useState<TutorialProgress>(()=>read(session));
 const persist=useCallback((next:TutorialProgress)=>{setProgress(next);try{localStorage.setItem(TUTORIAL_PROGRESS_KEY,JSON.stringify(next));}catch{/* optional */}},[]);
 const event=useCallback((value:TutorialEvent)=>setProgress(current=>{const next=reduceTutorial(current,value);if(next!==current)try{localStorage.setItem(TUTORIAL_PROGRESS_KEY,JSON.stringify(next));}catch{/* optional */}return next;}),[]);
 const skip=useCallback(()=>setProgress(current=>{const step=TUTORIAL_STEPS[current.index];if(!step)return current;const next={...current,index:current.index+1,skipped:[...current.skipped,step],memorySearched:false};try{localStorage.setItem(TUTORIAL_PROGRESS_KEY,JSON.stringify(next));}catch{/* optional */}return next;}),[]);
 const restart=useCallback((nextSession=session)=>persist(initial(nextSession)),[persist,session]);
 const resume=useCallback(()=>persist({...progress,active:true}),[persist,progress]);
 const deactivate=useCallback(()=>persist({...progress,active:false}),[persist,progress]);
 return{progress,event,skip,restart,resume,deactivate};
}

const copy:Record<TutorialStep,[string,string,string,string]>={
 radar:['创建练习 Radar','Create a practice Radar','点右上角＋，填写真实表单并提交。','Use the top-right +, complete the real form, and submit.'],
 source:['绑定练习来源','Bind a practice source','打开刚创建的行星，再进入“来源与采集”，创建并绑定来源。','Open the new planet, then Sources and collection; create and bind a source.'],
 collection:['完成一次采集','Complete one collection','点击“手动采集”，等待同一运行显示 succeeded 且新建 1。','Choose Collect now and wait for the same run to show succeeded and created 1.'],
 signal:['收藏信号','Bookmark the signal','进入“信号”，打开练习信号详情并点“加入记忆”。','Open Signals, open the practice detail, and choose Add to Memory.'],
 memory:['检索并写备注','Search and save a note','进入“记忆”，搜索练习信号；随后编辑该收藏备注并保存。','Open Memory, search for the practice signal, then edit and save its bookmark note.'],
 opportunity:['查看只读载荷','Review the read-only payload','进入“机会”，打开练习机会并查看只读行动载荷。','Open Opportunities, open the practice item, and review its read-only action payload.'],
 notification:['标记通知已读','Mark the notification read','进入“设置”的通知区域，对练习通知点“标为已读”。','In Settings notifications, mark the practice notification read.'],
};
export function TutorialCoachmark({progress,onSkip,onExit,onRestart}:{progress:TutorialProgress;onSkip:()=>void;onExit:()=>void;onRestart:()=>void}){
 const{t}=usePreferences();const step=TUTORIAL_STEPS[progress.index];const done=!step;
 return <aside className="tutorial-coachmark" aria-live="polite" data-testid="tutorial-coachmark">
  <span className="eyebrow">{t('交互练习 · 示例数据','GUIDED PRACTICE · SAMPLE DATA')}</span>
  {done?<><h2>{t('练习完成','Practice complete')}</h2><p>{t(`完成 ${progress.completed.length} 步，跳过 ${progress.skipped.length} 步。`,`Completed ${progress.completed.length}; skipped ${progress.skipped.length}.`)}</p><div className="tutorial-actions"><button className="text-button" onClick={onRestart}>{t('重新练习','Restart')}</button><button className="text-button" onClick={onExit}>{t('返回真实连接','Return to sign-in')}</button></div></>:<><small>{progress.index+1} / {TUTORIAL_STEPS.length}</small><h2>{t(copy[step][0],copy[step][1])}</h2><p>{t(copy[step][2],copy[step][3])}</p>{step==='memory'&&progress.memorySearched&&<p className="tutorial-success">{t('检索完成；现在保存一条备注。','Search complete; now save a note.')}</p>}<div className="tutorial-actions"><button className="text-button" onClick={onSkip}>{t('跳过此步','Skip step')}</button><button className="text-button" onClick={onExit}>{t('退出并保留进度','Exit and save')}</button></div></>}
 </aside>;
}
