import {fullscreenElement} from './fullscreen';
import {createDeviceWorker} from './createDeviceWorker';
import {GazeWindow} from './gaze';
import {useCallback,useEffect,useRef,useState} from 'react';
import {api,json,type Credentials} from './api';
import {deviceDetections,DeviceTracker,IntervalTracker} from './detection';
import type {EmitEvent,ProctorConfig} from './useProctoring';

export function useMonitoring(credentials:Credentials,hr:boolean,context:{question_id?:string;stage:string},config:ProctorConfig|null,emit:EmitEvent,violate?:(type:'device_detected'|'multiple_faces')=>Promise<void>){
  const video=useRef<HTMLVideoElement|null>(null);
  const [stream,setStream]=useState<MediaStream|null>(null),[healthy,setHealthy]=useState(false);
  const [selfCheck,setSelfCheck]=useState(false);
  const [status,setStatus]=useState('Camera and microphone off'),[face,setFace]=useState('Face detection unavailable');
  const [deviceStatus,setDeviceStatus]=useState('Detector off'),[micActive,setMicActive]=useState(false),[audioLevel,setAudioLevel]=useState(0);
  const [warning,setWarning]=useState(''),[events,setEvents]=useState<{id:string;label:string}[]>([]);
  const current=useRef(context);current.current=context;
  const stopRef=useRef(()=>{}),generation=useRef(0),acknowledged=useRef(0);
  const restart=useRef<()=>Promise<void>>(async()=>{}),recoveries=useRef(0),recoveryTimer=useRef(0);
  const start=useCallback(async()=>{
    if(!hr){setStatus('Practice does not collect proctoring signals.');return;}
    stopRef.current();const run=++generation.current;
    if(!config){setStatus('Wait for monitoring configuration to load.');return;}
    const deviceEnabled=config.device_detection_enabled!==false;
    const microphoneRequired=config.microphone_required!==false;
    const objectRequired=deviceEnabled&&!config.device_warning_only;
    setStatus(microphoneRequired?'Requesting camera and microphone…':'Requesting camera…');setFace('Loading face detector…');setDeviceStatus('Loading object detector…');
    let media:MediaStream|undefined;
    try{
      media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480}},audio:microphoneRequired?{echoCancellation:true,noiseSuppression:false}:false});
      if(run!==generation.current){media.getTracks().forEach(t=>t.stop());return;}
      const live=media;setStream(live);
      let disposed=false,faceBusy=false,objectBusy=false,faceReady=false,objectReady=false,evidenceReady=!hr,beatBusy=false,objectFast=false;
      let lastFace=0,lastObject=0,objectLatency=999999,visibleFaces:number|null=null,faceCount=0,objectCount=0,lastSubmit=0,lastHeartbeat=0,lastGaze=0,awayStarted=0,faceError='',objectError='';
      const started=performance.now(),baseTime=Date.now()/1000;
      const faceWorker=new Worker('/face-monitor.js');
      const objectWorker=deviceEnabled?createDeviceWorker():null;
      if(!deviceEnabled)setDeviceStatus('Device detection disabled pending validation');
      const intervals=new IntervalTracker(),tracker=new DeviceTracker(config.device_confidence,config.device_confirm_frames,config.device_max_gap_ms);
      const deviceBudget=config.device_result_max_age_ms??30000;
      const gazeWindow=new GazeWindow(config.gaze_window_seconds??30,config.gaze_away_seconds??5);
      let matchingFrame:HTMLCanvasElement|null=null,matchingContext=context;
      const coverage=()=>({face_coverage:Math.min(1,faceCount/Math.max(1,(performance.now()-started)/1000*3)),object_coverage:Math.min(1,objectCount/Math.max(1,(performance.now()-started)/1000))});
      const send=(event:Parameters<EmitEvent>[0])=>void emit(event).catch(()=>{});
      const recordInterval=(type:string,active:boolean,now:number,threshold:number,score?:number)=>{
        if(current.current.stage==='equipment'){intervals.states.delete(type);return;}
        const event=intervals.update(type,active,now,threshold);
        if(event&&current.current.stage!=='equipment'){
          send({id:event.id,type,duration:event.duration,score,metadata:{observed_start:baseTime+(event.started-started)/1000,face_count:visibleFaces??0}});
          if(active&&type==='no_face')setWarning('Please keep your face visible.');
          if(active&&type==='multiple_faces'){setWarning('Another person was detected in your camera. Please ensure you are alone during this interview.');}
          if(active&&type==='background_noise')setWarning('Sustained high microphone level detected. Check your surroundings; audio level cannot identify its source.');
        }
      };
      const audio=microphoneRequired?new AudioContext():null,analyser=audio?.createAnalyser();if(analyser)analyser.fftSize=1024;
      if(audio&&analyser){audio.createMediaStreamSource(live).connect(analyser);await audio.resume();}
      const samples=new Float32Array(analyser?.fftSize??1024);
      const disconnect=(kind:string)=>{setHealthy(false);setStatus('Camera and microphone access are required. Retrying once; use Retry monitoring if recovery fails.');setWarning('Monitoring interrupted. Your answer is preserved.');if(current.current.stage!=='equipment')send({type:kind==='video'?'camera_disconnected':'microphone_disconnected'});if(recoveries.current<1){recoveries.current++;recoveryTimer.current=window.setTimeout(()=>void restart.current(),1500);}};
      // Temporary `mute` events happen during device handoff and browser
      // power management. Only `ended` means the track was actually stopped.
      const listeners=live.getTracks().map(track=>{const lost=()=>disconnect(track.kind);track.addEventListener('ended',lost);return()=>track.removeEventListener('ended',lost);});
      const reportFailure=(name:string,message:string)=>{if(name.includes('detector')&&name!=='Face detector'&&!objectRequired){setDeviceStatus(`Device checks unavailable: ${message}. Answers can continue; HR review is required.`);send({type:'tracking_unavailable',metadata:{detector:name}});return;}setHealthy(false);setSelfCheck(false);console.error(`[${name}] ${message}`);setStatus(`${name} unavailable: ${message}. Retry monitoring.`);send({type:'tracking_unavailable',metadata:{detector:name}});};
      faceWorker.onmessage=({data})=>{
        if(disposed)return;
        if(data.type==='ready')faceReady=true;
        if(data.type==='error'){faceBusy=false;faceReady=false;faceError=data.message;setFace('Face detection unavailable');reportFailure('Face detector',faceError);}
        if(data.type==='result'){
          faceBusy=false;lastFace=performance.now();faceCount++;visibleFaces=data.count;
          if(data.count===1)setWarning(old=>/^(Another person|Multiple faces|Please keep your face)/.test(old)?'':old);
          setFace(data.count===0?'No face visible':data.count>1?`${data.count} faces visible`:'Face detected');
          recordInterval('no_face',data.count===0,lastFace,config.face_absence_ms);
          recordInterval('multiple_faces',data.count>1,lastFace,config.multiple_faces_ms,data.confidence);
          if(current.current.stage==='equipment'||current.current.stage==='finish'){gazeWindow.reset();}
          else if(data.gaze_available&&data.gaze_direction&&lastFace-lastGaze>=334){
            lastGaze=lastFace;
            const result=gazeWindow.add(data.gaze_direction,lastFace/1000);
            send({type:'gaze_sample',gaze_direction:data.gaze_direction,eye_contact_percent:result.percent??undefined,head_pose_angle:data.head_pose_angle||0,metadata:{head_pitch:data.head_pitch||0,movement:data.movement||'unavailable'}});
            if(result.violation)send({type:'gaze_violation',duration:result.duration,metadata:{gaze_direction:data.gaze_direction}});
          }
        }
      };
      if(objectWorker)objectWorker.onmessage=async({data})=>{
        if(disposed)return;
        if(data.type==='ready'){objectReady=true;setDeviceStatus('Ready; waiting for first inference');}
        if(data.type==='progress')setDeviceStatus(`Loading local model${typeof data.progress?.progress==='number'?` ${Math.round(data.progress.progress)}%`: '…'}`);
        if(data.type==='error'){objectBusy=false;objectReady=false;objectError=data.message;setDeviceStatus('Object detection unavailable');reportFailure('Object detector',objectError);}
        if(data.type==='result'){
          lastObject=performance.now();objectLatency=data.latency;objectCount++;objectFast=data.latency<=deviceBudget;
          const devices=deviceDetections(data.detections,config.device_confidence);
          tracker.setMaxGap(Math.min(deviceBudget,Math.max(config.device_max_gap_ms,8000,data.latency*2+6000)));
          setDeviceStatus(!objectFast?'Device scan exceeded the time limit. Retry monitoring.':devices.length?`Possible ${devices[0].label} (${Math.round(devices[0].score*100)}%)`:`Scanning camera view · ${(data.latency/1000).toFixed(1)}s per scan`);
          if(current.current.stage==='equipment'||current.current.stage==='finish'){
            if(current.current.stage==='equipment')setWarning(old=>devices.length?`Equipment check: remove the ${devices[0].label} from the camera view before starting.`:old.startsWith('Equipment check:')?'':old);
            tracker.tracks.clear();objectBusy=false;return;
          }
          for(const item of tracker.update(devices,lastObject)){
            let picture:Blob|undefined;
            if(item.confirmed){
              setWarning(`A possible ${item.label} was detected in the camera view. Please remove it. This event requires review.`);
              if(hr&&matchingFrame){const small=document.createElement('canvas');small.width=320;small.height=Math.round(matchingFrame.height*320/matchingFrame.width);small.getContext('2d')!.drawImage(matchingFrame,0,0,small.width,small.height);picture=await new Promise<Blob|undefined>(resolve=>small.toBlob(b=>resolve(b||undefined),'image/jpeg',.7));}
              if(hr&&!picture){evidenceReady=false;setStatus('Unable to capture event picture. Retry monitoring.');continue;}
            }
            try{
              const id=await emit({id:item.id,type:'device',duration:item.duration,label:item.label,score:item.score,box:item.box,metadata:{...matchingContext,model:data.model,backend:data.backend,latency_ms:data.latency}},picture);
              evidenceReady=true;
              if(item.confirmed&&hr){setEvents(old=>old.some(e=>e.id===id)?old:[...old,{id,label:`Possible ${item.label} — requires review`}]);}
            }catch{evidenceReady=false;setStatus('Event upload failed. Retrying; interview paused.');}
          }
          objectBusy=false;
        }
      };
      faceWorker.onerror=(event)=>{faceReady=false;faceBusy=false;faceError=event.message||'Worker failed';setFace('Face detector unavailable');reportFailure('Face detector',faceError);};
      if(objectWorker)objectWorker.onerror=()=>{objectReady=false;objectError='Worker failed';setDeviceStatus('Object detection unavailable');reportFailure('Object detector',objectError);};
      let timer=0;
      stopRef.current=()=>{if(disposed)return;disposed=true;acknowledged.current=0;++generation.current;clearInterval(timer);listeners.forEach(remove=>remove());faceWorker.terminate();objectWorker?.terminate();live.getTracks().forEach(t=>t.stop());if(audio&&audio.state!=='closed')void audio.close().catch(()=>{});if(video.current)video.current.srcObject=null;setStream(null);setHealthy(false);setMicActive(false);setAudioLevel(0);setStatus('Camera and microphone off');setFace('Face detection unavailable');setDeviceStatus('Detector off');if(hr)void api(`/sessions/${credentials.id}/monitoring/heartbeat`,json('POST',{camera:false,microphone:false,page_visible:false,fullscreen:false,face_age_ms:999999,object_age_ms:999999,evidence_ready:false,...coverage()}),credentials.token).catch(()=>{});};
      if(video.current){video.current.srcObject=live;await video.current.play();}
      faceWorker.postMessage({type:'init'});objectWorker?.postMessage({type:'init',threshold:config.device_confidence});
      if(hr){try{await api(`/sessions/${credentials.id}/monitoring/storage-check`,json('POST'),credentials.token);evidenceReady=true;}catch{setStatus('Evidence storage unavailable. Retry monitoring.');}}
      timer=window.setInterval(async()=>{
        if(disposed)return;
        const now=performance.now(),v=video.current;
        const camera=live.getVideoTracks().some(t=>t.readyState==='live'&&t.enabled&&!t.muted);
        const microphone=live.getAudioTracks().some(t=>t.readyState==='live'&&t.enabled&&!t.muted)&&audio?.state==='running';
        setMicActive(microphone);analyser?.getFloatTimeDomainData(samples);
        const rms=Math.sqrt(samples.reduce((n,x)=>n+x*x,0)/samples.length);setAudioLevel(Math.min(1,rms*5));
        recordInterval('background_noise',microphone&&rms>.2&&!['answer','answer_done'].includes(current.current.stage),now,5000);
        const detectors=faceReady&&lastFace>0&&now-lastFace<5000&&(!objectRequired||objectReady&&objectFast&&lastObject>0&&now-lastObject<deviceBudget);
        setSelfCheck(camera&&(!microphoneRequired||microphone)&&detectors&&evidenceReady);
        if(now-started>180000){if(!faceReady&&!faceError){faceError='Startup timed out';reportFailure('Face detector',faceError);}if(deviceEnabled&&!objectReady&&!objectError){objectError='Startup timed out';reportFailure('Device detector',objectError);}}
        if(faceError||objectError)setStatus(`Face detection: ${faceError?'unavailable':lastFace?'active':'starting'}. Device detection: ${objectError?'unavailable':lastObject?'active':'starting'}. Retry monitoring to complete the equipment check.`);
        const focused=!document.hidden&&document.hasFocus();
        const ok=camera&&(!microphoneRequired||microphone)&&detectors&&evidenceReady&&(!hr||focused&&!!fullscreenElement());
        if(!ok)acknowledged.current=0;setHealthy(ok);
        if(!faceError&&(!objectError||!objectRequired)&&camera&&(!microphoneRequired||microphone))setStatus(!objectRequired&&deviceEnabled?(ok?'Camera checks active. Device scanning runs in the background; unavailable scans are flagged for review.':'Complete the camera and face checks, then enter fullscreen.') :!deviceEnabled?(ok?'Camera, microphone and face checks active. Device detection disabled.':'Complete the face check and keep this window active. Device detection disabled.'):ok?(microphoneRequired?'Camera, microphone and detectors active':'Camera and detectors active; microphone not required'):!faceReady||!objectReady?'Loading local detection models…':!lastObject?'Running first object inference…':'Monitoring is not ready. Keep this window active and wait for fresh detector results.');
        if(v&&v.readyState>=2&&camera&&!document.hidden){
          if(faceReady&&!faceBusy){faceBusy=true;try{const frame=await createImageBitmap(v);if(!disposed)faceWorker.postMessage({type:'frame',frame,timestamp:now},[frame]);else frame.close();}catch{faceBusy=false;}}
          if(objectWorker&&objectReady&&!objectBusy&&now-lastSubmit>=5000&&now-lastObject>=5000){
            objectBusy=true;lastSubmit=now;matchingContext={...current.current};
            matchingFrame=document.createElement('canvas');matchingFrame.width=v.videoWidth;matchingFrame.height=v.videoHeight;matchingFrame.getContext('2d')!.drawImage(v,0,0);
            try{const frame=await createImageBitmap(matchingFrame);if(!disposed)objectWorker.postMessage({type:'frame',frame,timestamp:now},[frame]);else frame.close();}catch{objectBusy=false;}
          }
        }
        if(hr&&now-lastHeartbeat>=1000&&!beatBusy){lastHeartbeat=now;beatBusy=true;
          try{const res=await api<{healthy:boolean}>(`/sessions/${credentials.id}/monitoring/heartbeat`,json('POST',{camera,microphone,face_count:visibleFaces,page_visible:focused,fullscreen:!!fullscreenElement(),face_age_ms:lastFace?now-lastFace:999999,object_age_ms:lastObject?now-lastObject:999999,object_latency_ms:objectLatency,evidence_ready:evidenceReady,...coverage()}),credentials.token);if(!disposed){acknowledged.current=ok&&res.healthy?performance.now():0;setHealthy(ok&&res.healthy);}}catch{acknowledged.current=0;setHealthy(false);}finally{beatBusy=false;}
        }
      },334);
    }catch(error){media?.getTracks().forEach(t=>t.stop());setHealthy(false);setMicActive(false);setStream(null);setStatus(`Camera or microphone unavailable: ${(error as Error).message}. Retry monitoring.`);}
  },[credentials.id,credentials.token,hr,config,emit]);
  restart.current=start;
  useEffect(()=>()=>{clearTimeout(recoveryTimer.current);++generation.current;stopRef.current();},[]);
  const waitUntilReady=async()=>{const requested=performance.now();while(performance.now()-requested<35000){if(acknowledged.current>=requested&&fullscreenElement())return;await new Promise(resolve=>setTimeout(resolve,100));}throw new Error('Equipment check is not ready. Keep your face visible, confirm camera and microphone access, and retry monitoring before beginning.');};
  return {video,stream,selfCheck,waitUntilReady,start:()=>{setSelfCheck(false);clearTimeout(recoveryTimer.current);recoveries.current=0;return start();},stop:()=>{setSelfCheck(false);clearTimeout(recoveryTimer.current);++generation.current;stopRef.current();},status,healthy,face,deviceStatus,micActive,audioLevel,warning,setWarning,events};
}
