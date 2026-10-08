// Shared with the classic worker and unit tests. No frames leave the worker.
(function(root){
  function classify(points,matrix){
    const eyes=[[33,133,159,145,468],[362,263,386,374,473]];
    const offsets=[];
    for(const [a,b,top,bottom,iris] of eyes){
      if(![a,b,top,bottom,iris].every(i=>points?.[i]))return null;
      const p=points[a],q=points[b],t=points[top],u=points[bottom],c=points[iris];
      const dx=q.x-p.x,dy=q.y-p.y,width=Math.hypot(dx,dy);
      if(width<.005)return null;
      const ux=dx/width,uy=dy/width,vx=-uy,vy=ux;
      const height=Math.abs((u.x-t.x)*vx+(u.y-t.y)*vy);
      if(height/width<.08)return null; // blink/occlusion: unavailable
      offsets.push({x:((c.x-(p.x+q.x)/2)*ux+(c.y-(p.y+q.y)/2)*uy)/width,
        y:((c.x-(t.x+u.x)/2)*vx+(c.y-(t.y+u.y)/2)*vy)/height});
    }
    if(!matrix||matrix.length!==16)return null;
    const yaw=Math.asin(Math.max(-1,Math.min(1,-matrix[2])))*180/Math.PI;
    const pitch=Math.atan2(matrix[6],matrix[10])*180/Math.PI;
    const x=(offsets[0].x+offsets[1].x)/2,y=(offsets[0].y+offsets[1].y)/2;
    if(![x,y,yaw,pitch].every(Number.isFinite))return null;
    const head=Math.abs(yaw)>25||Math.abs(pitch)>20;
    const direction=head?(Math.abs(yaw)/25>Math.abs(pitch)/20?(yaw>0?'right':'left'):(pitch>0?'down':'up')):
      Math.abs(x)>.20?(x>0?'right':'left'):Math.abs(y)>.28?(y>0?'down':'up'):'center';
    return {gaze_direction:direction,head_pose_angle:yaw,head_pitch:pitch,movement:head?'head':direction==='center'?'center':'eyes'};
  }
  class Window {
    constructor(seconds=30,awaySeconds=5){this.seconds=seconds;this.awaySeconds=awaySeconds;this.samples=[];this.reset();}
    reset(){this.samples=[];this.since=null;this.last=null;this.flagged=false;}
    add(direction,time){
      if(this.last!==null&&(time<=this.last||time-this.last>1.5)){this.since=null;this.flagged=false;}
      this.last=time;
      this.samples=this.samples.filter(s=>s.time>time-this.seconds);
      this.samples.push({direction,time});
      const valid=this.samples.filter(s=>s.direction!=='off_screen');
      const percent=valid.length?Math.round(100*valid.filter(s=>s.direction==='center').length/valid.length):null;
      if(direction==='center'||direction==='off_screen'){this.since=null;this.flagged=false;}
      else if(this.since===null)this.since=time;
      const duration=this.since===null?0:time-this.since;
      const violation=!this.flagged&&this.since!==null&&duration>=this.awaySeconds;
      if(violation)this.flagged=true;
      return {percent,violation,duration};
    }
  }
  root.Gaze={classify,Window};
})(globalThis);
