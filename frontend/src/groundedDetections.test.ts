import {describe,it,expect} from 'vitest';
import {groundedDetections} from './groundedDetections';
import {DeviceTracker} from './detection';
const groups=[{label:'mobile phone',positions:[1]},{label:'tablet computer',positions:[2]}];
const box={xmin:0,ymin:0,xmax:20,ymax:20};
describe('tablet detections',()=>{
  it('uses tablet token confidence rather than padding probabilities',()=>{
    expect(groundedDetections([[.99,.1,.8]],[[.5,.5,.2,.2]],groups,100,100,.35)[0].label).toBe('tablet computer');
    expect(groundedDetections([[.99,.1,.1]],[[.5,.5,.2,.2]],groups,100,100,.35)).toEqual([]);
  });
  it('does not treat label flicker as a second device event',()=>{
    const t=new DeviceTracker();const events=[];
    for(let i=0;i<40;i++)events.push(...t.update([{label:i%2?'mobile phone':'tablet computer',score:.8,box}],i*1000));
    expect(events.filter(e=>e.confirmed)).toHaveLength(1);
    t.update([],41000);t.update([],46000);
    t.update([{label:'tablet computer',score:.8,box}],47000);
    t.update([{label:'tablet computer',score:.8,box}],48000);
    expect(t.update([{label:'tablet computer',score:.8,box}],49000)[0].confirmed).toBe(true);
  });
});
