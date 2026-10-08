import {fullscreenElement,fullscreenEvents,requestFullscreen,exitFullscreen} from './fullscreen';
import {useEffect,useRef,useState} from 'react';
import type {EmitEvent} from './useProctoring';

export function useExam(enabled:boolean,active:boolean,emit:EmitEvent,strict=true,terminate?:(type:'tab_switch'|'fullscreen_exit')=>Promise<void>){
  const [violated,setViolated]=useState(false);
  const [blocked,setBlocked]=useState(true),[message,setMessage]=useState('');
  const [fullscreen,setFullscreen]=useState(false),[focused,setFocused]=useState(true);
  const callback=useRef(emit);callback.current=emit;
  const tracking=useRef(active);tracking.current=active;
  useEffect(()=>{
    if(!enabled)return;
    const away=new Map<string,{id:string;start:number}>();
    let lastFull=!!fullscreenElement(),lastKeyboard=0,departed=false,terminated=false;
    const send=(event:Parameters<EmitEvent>[0])=>void callback.current(event).catch(()=>{});
    const end=(type:'tab_switch'|'fullscreen_exit')=>{if(strict&&tracking.current&&!terminated){terminated=true;setViolated(true);void terminate?.(type).catch(()=>{setMessage('Unable to record the violation. Keep this page open while connection is restored.');});}};
    const interval=(type:string,lost:boolean)=>{
      const prior=away.get(type);
      if(lost&&!prior&&tracking.current){const item={id:crypto.randomUUID(),start:performance.now()};away.set(type,item);send({id:item.id,type});}
      if(!lost&&prior){send({id:prior.id,type,duration:(performance.now()-prior.start)/1000});away.delete(type);}
    };
    const check=()=>{const full=!!fullscreenElement(),focus=!document.hidden&&document.hasFocus();
      if(tracking.current&&(!full||!focus))departed=true;
      if(departed&&full&&focus){send({type:'screen_returned'});departed=false;}
      setFullscreen(full);setFocused(focus);setBlocked(!full||!focus);
      if(!full||!focus)setMessage(strict?'Return to this window and restore fullscreen to continue.':'Please maximize your browser and avoid switching tabs. Practice can continue without fullscreen.');
      else setMessage('Interview resumed in fullscreen.');
    };
    const visibility=()=>{interval('tab_switch',document.hidden);if(document.hidden&&tracking.current){setMessage('Leaving the interview tab has been detected.');end('tab_switch');}check();};
    const blur=()=>{interval('window_blur',true);if(tracking.current)end('tab_switch');check();};
    const focus=()=>{interval('window_blur',false);check();};
    const full=()=>{const now=!!fullscreenElement();if(lastFull&&!now&&tracking.current){send({type:'fullscreen_exit'});setMessage('Please return to fullscreen mode.');end('fullscreen_exit');}lastFull=now;check();};
    const attempt=(type:string)=>{setMessage('Copy, paste, cut and right-click are disabled during the interview.');send({type});};
    const clipboard=(event:Event)=>{if(!tracking.current||!strict)return;event.preventDefault();if(performance.now()-lastKeyboard>300)attempt(event.type==='contextmenu'?'context_menu':`${event.type}_attempt`);};
    const keyboard=(event:KeyboardEvent)=>{if(!strict||!tracking.current||!(event.ctrlKey||event.metaKey))return;const type=({c:'copy_attempt',v:'paste_attempt',x:'cut_attempt'} as Record<string,string>)[event.key.toLowerCase()];if(type){event.preventDefault();lastKeyboard=performance.now();attempt(type);}};
    const drop=(event:Event)=>{if(strict&&tracking.current){event.preventDefault();attempt('paste_attempt');}};
    const leave=(event:BeforeUnloadEvent)=>{if(tracking.current){event.preventDefault();event.returnValue='';}};
    document.addEventListener('visibilitychange',visibility);fullscreenEvents.forEach(event=>document.addEventListener(event,full));
    window.addEventListener('blur',blur);window.addEventListener('focus',focus);window.addEventListener('beforeunload',leave);
    document.addEventListener('keydown',keyboard);document.addEventListener('drop',drop);document.addEventListener('dragstart',drop);
    for(const type of ['copy','cut','paste','contextmenu'])document.addEventListener(type,clipboard);
    document.body.classList.add('exam-active');check();
    return()=>{document.body.classList.remove('exam-active');document.removeEventListener('visibilitychange',visibility);fullscreenEvents.forEach(event=>document.removeEventListener(event,full));window.removeEventListener('blur',blur);window.removeEventListener('focus',focus);window.removeEventListener('beforeunload',leave);document.removeEventListener('keydown',keyboard);document.removeEventListener('drop',drop);document.removeEventListener('dragstart',drop);for(const type of ['copy','cut','paste','contextmenu'])document.removeEventListener(type,clipboard);};
  },[enabled]);
  const enter=async()=>{try{await requestFullscreen();setFullscreen(!!fullscreenElement());setBlocked(document.hidden||!document.hasFocus());setMessage('Fullscreen interview active.');}catch(error){setMessage(strict?(error as Error).message:'Please maximize your browser and avoid switching tabs. Practice can continue without fullscreen.');if(strict)throw error;}};
  const finish=()=>{tracking.current=false;return exitFullscreen();};
  return {blocked:enabled&&strict&&blocked,message,enter,finish,fullscreen,focused,violated};
}
