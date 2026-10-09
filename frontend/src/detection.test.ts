import {describe,it,expect} from 'vitest';
import {deviceDetections,DeviceTracker,IntervalTracker} from './detection';
const phone={label:'mobile phone',score:.8,box:{xmin:1,ymin:1,xmax:20,ymax:20}};
describe('device events',()=>{
  it('never converts face or person labels into device strikes',()=>{const tracker=new DeviceTracker();for(let now=0;now<30000;now+=1000)expect(tracker.update([{...phone,label:'person'},{...phone,label:'multiple_faces'}],now)).toEqual([]);});
  it('does not count a continuously visible device twice',()=>{
    const tracker=new DeviceTracker();const events=[];
    for(let now=0;now<=19000;now+=1000)events.push(...tracker.update([phone],now));
    const confirmed=events.filter(e=>e.confirmed);
    expect(confirmed).toHaveLength(1);
  });
  it('confirms CPU scans at the actual sampling cadence but rejects stale gaps',()=>{const t=new DeviceTracker();t.setMaxGap(11000);expect(t.update([phone],0)).toEqual([]);expect(t.update([phone],5000)).toEqual([]);expect(t.update([phone],10000)[0].confirmed).toBe(true);const stale=new DeviceTracker();stale.setMaxGap(11000);stale.update([phone],0);stale.update([phone],5000);expect(stale.update([phone],20000)).toEqual([]);});

  it('requires consecutive frames and ignores low confidence',()=>{const t=new DeviceTracker();expect(t.update([phone],0)).toEqual([]);expect(t.update([{...phone,score:.2}],1000)).toEqual([]);expect(t.update([phone],2000)).toEqual([]);expect(t.update([phone],3000)).toEqual([]);expect(t.update([phone],4000)[0].confirmed).toBe(true);});
  it('does not confirm across long gaps',()=>{const t=new DeviceTracker();t.update([phone],0);t.update([phone],1000);expect(t.update([phone],4000)).toEqual([]);});
  it('captures once while present and closes after absence',()=>{const t=new DeviceTracker();t.update([phone],0);t.update([phone],1000);const e=t.update([phone],2000)[0];expect(t.update([phone],3000)).toEqual([]);expect(t.update([],7000)).toEqual([]);const closed=t.update([],12000)[0];expect(closed.closed).toBe(true);expect(closed.id).toBe(e.id);});
  it('counts a confirmed return after removal as a new occurrence',()=>{const t=new DeviceTracker();for(let n=0;n<=2000;n+=1000)t.update([phone],n);t.update([],3000);t.update([],8000);expect(t.update([phone],9000)).toEqual([]);expect(t.update([phone],10000)).toEqual([]);expect(t.update([phone],11000)[0].confirmed).toBe(true);});
});
describe('face observations',()=>{it('uses continuous thresholds and merges short gaps',()=>{const t=new IntervalTracker();expect(t.update('no_face',true,0,3000)).toBeNull();expect(t.update('no_face',true,3000,3000)).toBeNull();const e=t.update('no_face',true,3334,3000);expect(e).not.toBeNull();expect(t.update('no_face',false,3500,3000)).toBeNull();expect(t.update('no_face',true,3800,3000)).toBeNull();expect(t.update('no_face',false,5000,3000)?.id).toBe(e?.id);});});

describe('device classification boundary',()=>{
  it('drops people, faces, unsupported classes and weak detections before messaging',()=>{
    expect(deviceDetections([{...phone,label:'person'},{...phone,label:'face'},{...phone,label:'headphones'},{...phone,score:.1},phone],.35)).toEqual([phone]);
  });
  it('keeps a real phone independent of human presence in the same frame',()=>{
    const devices=deviceDetections([{...phone,label:'person'},phone],.35);
    const tracker=new DeviceTracker();tracker.update(devices,0);tracker.update(devices,1000);
    expect(tracker.update(devices,2000).map(e=>e.label)).toEqual(['mobile phone']);
  });
});
describe('repeated multiple faces',()=>{
  it('gives a removal grace period and confirms a fresh face strike without device events',()=>{
    const faces=new IntervalTracker();faces.update('multiple_faces',true,0,2000);
    const first=faces.update('multiple_faces',true,2100,2000)!;
    expect(faces.update('multiple_faces',true,16000,2000)).toBeNull();
    expect(faces.update('multiple_faces',true,18000,2000)).toBeNull();
    const second=faces.update('multiple_faces',true,20100,2000)!;
    expect(second.id).not.toBe(first.id);expect(second.type).toBe('multiple_faces');
  });
});

it('does not accumulate isolated face false positives',()=>{const t=new IntervalTracker();for(let n=0;n<10000;n+=600){expect(t.update('multiple_faces',true,n,2000)).toBeNull();expect(t.update('multiple_faces',false,n+300,2000)).toBeNull();}});
it('counts a second sustained face occurrence after removal',()=>{const t=new IntervalTracker();t.update('multiple_faces',true,0,2000);const first=t.update('multiple_faces',true,2100,2000)!;t.update('multiple_faces',false,3200,2000);t.update('multiple_faces',true,4000,2000);const second=t.update('multiple_faces',true,6100,2000)!;expect(second.id).not.toBe(first.id);});

it("confirms a briefly held phone at one-second sampling",()=>{const tracker=new DeviceTracker(.35,3,3500);expect(tracker.update([phone],0)).toEqual([]);expect(tracker.update([phone],1002)).toEqual([]);expect(tracker.update([phone],2004)[0].confirmed).toBe(true);});
