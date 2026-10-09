export type Detection = {label:string;score:number;box:Record<string,number>};
export const DEVICE_LABELS=['mobile phone','tablet computer','laptop computer'] as const;
export function deviceDetections(detections:Detection[],threshold:number){return detections.filter(d=>DEVICE_LABELS.some(label=>label===d.label)&&Number.isFinite(d.score)&&d.score>=threshold);}
export type DeviceEvent = {id:string;label:string;started:number;duration:number;score:number;box:Record<string,number>;confirmed:boolean;closed:boolean};
type Track = {hits:number;lastSeen:number;started:number;event?:DeviceEvent;lastWarning:number;absentSince?:number};
export class DeviceTracker {
  constructor(private threshold=.35,private confirmFrames=3,private maxGap=2000){}
  tracks = new Map<string,Track>();
  setMaxGap(milliseconds:number){this.maxGap=milliseconds;}
  update(detections:Detection[], now:number):DeviceEvent[]{
    const events:DeviceEvent[]=[];
    // One visible-device episode, even if the model alternates phone/tablet labels.
    for(const label of ['device']){
      let track=this.tracks.get(label);
      if(!track){track={hits:0,lastSeen:-Infinity,started:now,lastWarning:-Infinity};this.tracks.set(label,track);}
      const found=deviceDetections(detections,this.threshold).sort((a,b)=>b.score-a.score)[0];
      if(found){
        track.absentSince=undefined;
        if(now-track.lastSeen>this.maxGap){track.hits=0;track.started=now;}
        track.hits++;track.lastSeen=now;
        if(!track.event&&track.hits>=this.confirmFrames&&now-track.lastWarning>=15000){
          track.event={id:crypto.randomUUID(),label:found.label,started:track.started,duration:0,score:found.score,box:found.box,confirmed:true,closed:false};
          track.lastWarning=now;events.push({...track.event});
        }
      }else if(track.event){
        track.absentSince??=now;
        if(now-track.absentSince>=5000){
          events.push({...track.event,duration:(track.lastSeen-track.event.started)/1000,confirmed:false,closed:true});track.event=undefined;track.hits=0;track.lastWarning=-Infinity;
        }
      }else if(!track.event){track.hits=0;}
    }
    return events;
  }
}

export class IntervalTracker {
  states=new Map<string,{since:number;id:string;emitted:boolean;lastTrue:number}>();
  update(type:string,active:boolean,now:number,threshold:number){
    let s=this.states.get(type);
    if(active){
      if(!s){s={since:now,id:crypto.randomUUID(),emitted:false,lastTrue:now};this.states.set(type,s);}
      if(type==='multiple_faces'&&s.emitted&&now-s.since>=threshold+15000){s={since:now,id:crypto.randomUUID(),emitted:false,lastTrue:now};this.states.set(type,s);}
      s.lastTrue=now;
      if(!s.emitted&&now-s.since>threshold){s.emitted=true;return {id:s.id,type,started:s.since,duration:(now-s.since)/1000};}
    } else if(s&&(!s.emitted||now-s.lastTrue>=1000)){
      this.states.delete(type);
      if(s.emitted)return {id:s.id,type,started:s.since,duration:(s.lastTrue-s.since)/1000};
    }
    return null;
  }
}
