import {Bell} from 'lucide-react';
import {useQuery} from '@tanstack/react-query';
import {api,json} from './api';

type Notice={id:string;title:string;message:string;company_name:string;href:string;created_at:number;scheduled_at?:number;window_end_at?:number;read:boolean};
export default function CandidateNotifications(){
 const query=useQuery({queryKey:['candidate-notifications'],queryFn:()=>api<{items:Notice[];unread_count:number}>('/candidate/notifications?envelope=true'),refetchInterval:15000});
 const notices=query.data?.items||[];
 const unread=query.data?.unread_count||0;
 async function read(n:Notice){await api('/candidate/notifications/'+encodeURIComponent(n.id)+'/read',json('PATCH'));await query.refetch();}
 return <details className="candidate-notifications"><summary aria-label={`Notifications, ${unread} unread`}><Bell size={18} aria-hidden="true"/> Notifications {unread>0&&<b>{unread}</b>}</summary><section aria-label="Candidate notifications"><h2>Your updates</h2>{query.isPending?<p>Loading notifications…</p>:query.isError?<p>Unable to load notifications. <button onClick={()=>void query.refetch()}>Retry</button></p>:!notices.length?<p>Shortlist and interview updates will appear here.</p>:notices.map(n=><article key={n.id} className={n.read?'':'unread'}><small>{n.company_name} · {new Date(n.created_at*1000).toLocaleDateString()}</small><h3>{n.title}</h3><p>{n.message}</p>{n.scheduled_at&&<p>Starts: {new Date(n.scheduled_at*1000).toLocaleString()}</p>}{n.window_end_at&&<p>Closes: {new Date(n.window_end_at*1000).toLocaleString()}</p>}<a href={n.href} onClick={()=>{if(!n.read)void read(n).catch(()=>{});}}>View details →</a>{!n.read&&<button onClick={()=>void read(n).catch(()=>query.refetch())}>Mark as read</button>}</article>)}</section></details>;
}
