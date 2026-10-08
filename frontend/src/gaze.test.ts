import {describe,it,expect} from 'vitest';
import {GazeWindow} from './gaze';
describe('gaze episodes',()=>{
 it('flags once per uninterrupted episode and resets on center',()=>{const w=new GazeWindow(30,5);let flags=0;for(let t=0;t<=10;t+=.5)flags+=Number(w.add('left',t).violation);expect(flags).toBe(1);w.add('center',11);for(let t=12;t<=17;t+=.5)flags+=Number(w.add('right',t).violation);expect(flags).toBe(2);});
 it('does not bridge missing frames or missing eyes',()=>{const w=new GazeWindow(30,5);w.add('left',0);expect(w.add('left',6).violation).toBe(false);w.add('off_screen',6.5);expect(w.add('left',7).violation).toBe(false);});
 it('calculates rolling percentages over valid samples',()=>{const w=new GazeWindow(30,5);w.add('left',0);w.add('center',.5);expect(w.add('off_screen',1).percent).toBe(50);expect(w.add('center',31).percent).toBe(100);});
 it('treats degenerate landmarks as unavailable',()=>{expect(globalThis.Gaze.classify(Array(478).fill({x:0,y:0}),Array(16).fill(0))).toBe(null);});
 it('distinguishes iris motion from head rotation',()=>{
   const points=Array.from({length:478},()=>({x:0,y:0}));
   for(const [a,b,t,u,c,x] of [[33,133,159,145,468,.2],[362,263,386,374,473,.6]]){
     points[a]={x,y:.4};points[b]={x:x+.1,y:.4};points[t]={x:x+.05,y:.38};points[u]={x:x+.05,y:.42};points[c]={x:x+.05,y:.4};
   }
   const matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
   expect(globalThis.Gaze.classify(points,matrix)?.gaze_direction).toBe('center');
   points[468].x+=.03;points[473].x+=.03;
   expect(globalThis.Gaze.classify(points,matrix)?.movement).toBe('eyes');
   matrix[2]=-.6;
   expect(globalThis.Gaze.classify(points,matrix)?.movement).toBe('head');
 });
});
