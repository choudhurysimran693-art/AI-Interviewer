export type Mode = 'practice' | 'hr';
export type Profile = {skills:string[]; projects:string[]; responsibilities:string[]; experience:string};
export type Question = {options?:{id:string;text:string}[];multiple_select?:boolean;id:string; question:string; resume_basis:string; category:string; sequence:number; source:string; question_type?:string; starter_code?:string; language?:string; time_limit_seconds?:number};
export type Evaluation = {status:string; technical?:number; communication?:number; reason?:string; strengths?:string[]; improvements?:string[]; missing_concepts?:string[]; evidence?:string[]};
export type Answer = {id:string; question_id:string; transcript:string; approved:boolean; evaluation:Evaluation; duration:number; metrics:Record<string,number|null>; ai_evaluation?:Evaluation; followup?:{question:string;reply:string}; human_reviews?:{reviewer:string;reviewed_at:number;technical:number;communication:number;reason:string}[]};
export type SessionState = {round_type?:string;id:string; mode:Mode; status:string; role:string; name:string; questions:Question[]; answers:Answer[]; jobs:{id:string;kind:string;status:string;answer_id:string}[]};
export type Credentials = {id:string;token:string};
export type FeelingValue = {label:string; intensity:number|null};
export type FeelingsResponse = {question_id:string;feelings:FeelingValue[];note:string};
export type Observation = {id:string;type:string;timestamp:number;duration:number;stage:string;question_id?:string;label?:string;explanation?:string;snapshot?:boolean;limitation:string;severity?:string;confidence?:number;event_type?:string;gaze_direction?:string;eye_contact_percent?:number;head_pose_angle?:number};
export type ReportData = {role:string;mode:Mode;name:string;target_role:string;expires:number;summary:{technical:number|null;communication:number|null;overall?:number|null;coverage:string};questions:Question[];answers:Answer[];observations:Observation[];feelings_available:boolean;share_feelings:boolean;hr_link:string|null;proctor_summary?:import('./useProctoring').ActivitySummary};
export type Readiness = {environment:string;ai_configured:boolean;storage:string;detector:{passed:boolean;reason:string;model_revision?:string}};

export async function api<T>(path:string, options:RequestInit={}, token?:string):Promise<T>{
  const headers = new Headers(options.headers);
  const csrf=document.cookie.split('; ').find(x=>x.startsWith('interview_csrf='))?.split('=').slice(1).join('=');
  if(csrf)headers.set('X-CSRF-Token',decodeURIComponent(csrf));
  if(token) headers.set('Authorization',`Bearer ${token}`);
  if(options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  const response = await fetch(`/api${path}`,{...options,headers,cache:'no-store'});
  if(response.status===401&&!path.startsWith('/auth/'))window.dispatchEvent(new Event('auth-expired'));
  if(!response.ok){const body=await response.json().catch(()=>({detail:response.statusText}));throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
  return response.json();
}
export const json = (method:string, body?:unknown):RequestInit=>({method,body:body===undefined?undefined:JSON.stringify(body)});
