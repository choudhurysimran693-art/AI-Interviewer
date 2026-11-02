import {useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {api,json} from './api';

type Notice={id:string;title:string;message:string;href:string;type?:string;created_at:number;read:boolean;window_end_at?:number};
function useNotices(){return useQuery({queryKey:['candidate-notifications'],queryFn:()=>api<{items:Notice[];unread_count:number}>('/candidate/notifications?envelope=true'),refetchInterval:15000});}

export function Messages(){
 const q=useNotices(),cache=useQueryClient();
 const [opened,setOpened]=useState<string[]>([]),[error,setError]=useState('');
 async function open(n:Notice){setError('');try{if(!n.read)await api('/candidate/notifications/'+encodeURIComponent(n.id)+'/read',json('PATCH'));setOpened(old=>[...old,n.id]);await cache.invalidateQueries({queryKey:['candidate-notifications']});}catch(e){setError((e as Error).message);}}
 return <section className="portal-panel"><h1>Messages</h1>{error&&<p role="alert">{error}</p>}{q.isPending?<p>Loading messages…</p>:q.isError?<p role="alert">Could not load messages. <button onClick={()=>void q.refetch()}>Retry</button></p>:!q.data?.items.length?<p>No messages yet.</p>:q.data.items.map(n=><article key={n.id} className="notification"><button aria-expanded={opened.includes(n.id)} onClick={()=>void open(n)}>{!n.read?'New · ':''}{n.title}</button><p><small>{new Date(n.created_at*1000).toLocaleString()}</small></p>{opened.includes(n.id)&&<><p>{n.message}</p>{n.window_end_at&&<p>Deadline: {new Date(n.window_end_at*1000).toLocaleString()}</p>}<a href={n.href}>View next steps →</a></>}</article>)}</section>;
}

export function RoundUnlockedBanner(){
 const q=useNotices();
 const notices=q.data?.items.filter(n=>!n.read&&n.type==='next_round'&&(!n.window_end_at||n.window_end_at>Date.now()/1000))||[];
 return notices.length?<section className="assignment-notice" aria-label="New round unlocked"><div><h2>A new round is ready</h2>{notices.map(n=><p key={n.id}>{n.title} · <a href="/candidate/messages">Read your invitation and deadline</a></p>)}</div></section>:null;
}

type Log={id:string;type:string;title:string;created_at:number;email_status:string};
export function NotificationLog({candidateId}:{candidateId:string}){
 const q=useQuery({queryKey:['workflow-log',candidateId],queryFn:()=>api<Log[]>('/hr/candidates/'+encodeURIComponent(candidateId)+'/workflow-notifications'),refetchInterval:15000});
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function retry(id:string){setBusy(true);setError('');try{await api('/hr/workflow-notifications/'+encodeURIComponent(id)+'/retry',json('POST'));await q.refetch();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <section><h3>Notification history</h3>{error&&<p role="alert">{error}</p>}{q.isPending?<p>Loading notifications…</p>:q.isError?<p role="alert">Unable to load notification history. <button onClick={()=>void q.refetch()}>Retry</button></p>:!q.data?.length?<p>No workflow notifications yet.</p>:q.data.map(n=><article key={n.id}><strong>{n.type.replaceAll('_',' ')}</strong><p>{n.title}</p><small>{new Date(n.created_at*1000).toLocaleString()} · Email: {n.email_status==='sent'?'Accepted by email provider':n.email_status}</small>{n.email_status.startsWith('failed:')&&<button disabled={busy} onClick={()=>void retry(n.id)}>Retry email</button>}</article>)}</section>;
}
