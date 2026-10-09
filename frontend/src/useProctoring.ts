import {useCallback,useEffect,useRef,useState} from 'react';
import {api,json,type Credentials} from './api';

export type ProctorConfig={device_detection_enabled?:boolean;device_result_max_age_ms?:number;gaze_window_seconds?:number;gaze_away_seconds?:number;gaze_review_count?:number;max_fullscreen_exits:number;max_tab_switches:number;device_confidence:number;face_absence_ms:number;multiple_faces_ms:number;max_faces:number;max_multiple_face_violations?:number;device_confirm_frames:number;device_max_gap_ms:number;auto_terminate:boolean;review_score:number;screen_lock_seconds:number;max_violations:number;block_account:boolean};
export type ActivitySummary={activity_score:number;counts:Record<string,number>;review_required:boolean;terminate:boolean;meaning:string;gaze?:{eye_contact_percent:number|null;samples:number}};
export type ProctorEvent={id?:string;type:string;timestamp?:number;duration?:number;score?:number|null;label?:string;box?:Record<string,number>;metadata?:Record<string,string|number|boolean>;gaze_direction?:'center'|'left'|'right'|'up'|'down'|'off_screen';eye_contact_percent?:number;head_pose_angle?:number};
export type EmitEvent=(event:ProctorEvent,snapshot?:Blob)=>Promise<string>;
export function useProctoring(credentials:Credentials,context:{question_id?:string;stage:string}){
  const [config,setConfig]=useState<ProctorConfig|null>(null);
  const [summary,setSummary]=useState<ActivitySummary|null>(null);
  const [status,setStatus]=useState(''),[syncError,setSyncError]=useState('');
  const [security,setSecurity]=useState<{terminated_reason?:string;lock_until?:number;violations?:number;screen_changes?:number;face_warning_count?:number;face_warning_acknowledged?:number;device_warning_count?:number;device_warning_acknowledged?:number}>({});
  const [serverOffset,setServerOffset]=useState(0);
  const current=useRef(context);current.current=context;
  const created=useRef(Date.now()/1000);
  const queue=useRef(new Map<string,{body:unknown;snapshot?:Blob;saved?:string}>());
  const activeFlush=useRef<Promise<void>|null>(null);
  const gazeSocket=useRef<WebSocket|null>(null);
  const gazeSend=useCallback((body:unknown):Promise<{id:string;summary:ActivitySummary;security:typeof security;status:string;server_now:number}>=>new Promise((resolve,reject)=>{
    let socket=gazeSocket.current;
    const timer=setTimeout(()=>{socket?.close();reject(new Error('Gaze stream timeout'));},5000);
    const send=()=>{if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(body));};
    if(!socket||socket.readyState>1){
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/sessions/${credentials.id}/gaze`);gazeSocket.current=socket;
      socket.onopen=()=>{const csrf=document.cookie.split('; ').find(x=>x.startsWith('interview_csrf='))?.split('=').slice(1).join('=');socket!.send(JSON.stringify({token:credentials.token,csrf:decodeURIComponent(csrf||'')}));send();};
    }else send();
    socket.onmessage=e=>{clearTimeout(timer);resolve(JSON.parse(e.data));};
    socket.onerror=socket.onclose=()=>{clearTimeout(timer);reject(new Error('Gaze stream unavailable'));};
  }),[credentials.id,credentials.token]);
  useEffect(()=>()=>{gazeSocket.current?.close();},[]);
  const refresh=useCallback(async()=>{
    const data=await api<{config:ProctorConfig;summary:ActivitySummary;status:string;created:number;security:typeof security;server_now:number}>(`/sessions/${credentials.id}/monitoring`,{},credentials.token);
    setConfig(data.config);setSummary(data.summary);setStatus(data.status);created.current=data.created;setSecurity(data.security);setServerOffset(data.server_now-Date.now()/1000);
  },[credentials.id,credentials.token]);
  const flush=useCallback(async()=>{
    if(activeFlush.current){await activeFlush.current;if(queue.current.size)return flush();return;}
    activeFlush.current=(async()=>{
      try{
        for(const [key,item] of queue.current){
          if(!item.saved){
          const gaze=(item.body as ProctorEvent).type.startsWith('gaze_');
          const data=gaze?await gazeSend(item.body).catch(()=>null):await api<{id:string;summary:ActivitySummary;security:typeof security;status:string;server_now:number}>(`/sessions/${credentials.id}/observations`,json('POST',item.body),credentials.token);
          // A lost supplementary gaze sample must not pause an examination.
          if(!data){queue.current.delete(key);continue;}
          item.saved=data.id;setSummary(data.summary);
          setStatus(data.status);setSecurity(data.security);setServerOffset(data.server_now-Date.now()/1000);
          }
          if(item.snapshot){const form=new FormData();form.append('file',item.snapshot,'event.jpg');await api(`/observations/${item.saved}/snapshot`,{method:'POST',body:form},credentials.token);}
          if(queue.current.get(key)===item)queue.current.delete(key);
        }
        setSyncError('');
      }catch(error){setSyncError('Monitoring events could not be saved. Retrying automatically.');throw error;}
    })().finally(()=>{activeFlush.current=null;});
    await activeFlush.current;
    if(queue.current.size)return flush();
  },[credentials.id,credentials.token,gazeSend]);
  const emit=useCallback<EmitEvent>(async(event,snapshot)=>{
    const id=event.id||crypto.randomUUID();
    if(event.type==='gaze_sample'&&queue.current.size>=30)return id;
    queue.current.set(id,{body:{id,duration:0,timestamp:Math.max(0,Date.now()/1000-created.current),face_coverage:0,object_coverage:0,...current.current,...event},snapshot});
    await flush();
    return `${credentials.id}-${id}`;
  },[credentials.id,flush]);
  const violate=useCallback(async(type:'tab_switch'|'fullscreen_exit'|'device_detected'|'multiple_faces')=>{
    const data=await api<{status:string;security:typeof security}>(`/sessions/${credentials.id}/violation`,json('POST',{type}),credentials.token);
    setStatus(data.status);setSecurity(data.security);
  },[credentials.id,credentials.token]);
  useEffect(()=>{void refresh().catch(()=>setSyncError('Unable to load monitoring configuration.'));
    const timer=setInterval(()=>{void refresh().catch(()=>{});if(queue.current.size)void flush().catch(()=>{});},3000);
    return()=>clearInterval(timer);
  },[refresh,flush]);
  const acknowledgeFace=async()=>{await api(`/sessions/${credentials.id}/face-warning/acknowledge`,json('POST'),credentials.token);await refresh();};
  const acknowledgeDevice=async()=>{await api(`/sessions/${credentials.id}/device-warning/acknowledge`,json('POST'),credentials.token);await refresh();};
  return {config,summary,status,syncError,emit,violate,flush,created,security,serverOffset,acknowledgeDevice,acknowledgeFace};
}
