import type {Detection} from './detection';
// Only query-word probabilities count. Padding, punctuation and special tokens
// are excluded: the library decoder can otherwise attempt to decode no words.
export function groundedDetections(probabilities:number[][],boxes:number[][],groups:{label:string;positions:number[]}[],width:number,height:number,threshold:number):Detection[]{
  const found:Detection[]=[];
  for(let i=0;i<probabilities.length;i++){
    const row=probabilities[i];let best:typeof groups[number]|undefined,score=0;
    for(const group of groups){if(!group.positions.length)continue;const value=Math.max(...group.positions.map(j=>row[j]));if(value>score){score=value;best=group;}}
    if(!best||score<threshold||!Number.isFinite(score))continue;
    const [cx,cy,w,h]=boxes[i];if(![cx,cy,w,h].every(Number.isFinite)||w<=0||h<=0||w*h>=.9)continue;
    found.push({label:best.label,score,box:{xmin:Math.max(0,(cx-w/2)*width),ymin:Math.max(0,(cy-h/2)*height),xmax:Math.min(width,(cx+w/2)*width),ymax:Math.min(height,(cy+h/2)*height)}});
  }
  const kept:Detection[]=[];
  for(const d of found.sort((a,b)=>b.score-a.score)){
    if(kept.some(k=>{
      const a=k.box,b=d.box,overlap=Math.max(0,Math.min(a.xmax,b.xmax)-Math.max(a.xmin,b.xmin))*Math.max(0,Math.min(a.ymax,b.ymax)-Math.max(a.ymin,b.ymin));
      const union=(a.xmax-a.xmin)*(a.ymax-a.ymin)+(b.xmax-b.xmin)*(b.ymax-b.ymin)-overlap;
      return union>0&&overlap/union>.5;
    }))continue;
    kept.push(d);if(kept.length===10)break;
  }
  return kept;
}
