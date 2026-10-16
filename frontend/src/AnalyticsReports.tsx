import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {ResponsiveContainer,BarChart,Bar,XAxis,YAxis,Tooltip,CartesianGrid,LabelList,ScatterChart,Scatter} from 'recharts';
import {api} from './api';
import './analytics.css';
type Distribution={band:string;count:number};
type PositionAverage={position_id:string;position_title:string;average_score:number};
type Trend={month:string;average_score:number};
type Point={technical_score:number;communication_score:number};
function Bars({rows,label,value,maximum}:{rows:Record<string,unknown>[];label:string;value:string;maximum?:number}){
 return <div style={{height:Math.max(240,rows.length*44)}}><ResponsiveContainer width="100%" height="100%"><BarChart data={rows} layout="vertical" margin={{top:10,right:50,left:10,bottom:10}} accessibilityLayer><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" domain={maximum?[0,maximum]:[0,'auto']}/><YAxis type="category" dataKey={label} width={145} tick={{fontSize:12}}/><Tooltip/><Bar dataKey={value} fill="#527b66" maxBarSize={28} radius={[0,4,4,0]}><LabelList dataKey={value} position="right"/></Bar></BarChart></ResponsiveContainer></div>;
}
export default function AnalyticsReports(){
 const [position,setPosition]=useState(''),[from,setFrom]=useState(''),[to,setTo]=useState('');
 const invalid=!!(from&&to&&from>to);
 const params=new URLSearchParams();if(position)params.set('position_id',position);if(from)params.set('date_from',from);if(to)params.set('date_to',to);
 const suffix='?'+params.toString();
 const roles=useQuery({queryKey:['analytics-roles'],queryFn:()=>api<{items:{id:string;title:string}[]}>('/positions?status=')});
 const dist=useQuery({queryKey:['analytics','distribution',position,from,to],queryFn:()=>api<Distribution[]>('/analytics/score-distribution'+suffix),enabled:!invalid,refetchInterval:30000});
 const averages=useQuery({queryKey:['analytics','positions',position,from,to],queryFn:()=>api<PositionAverage[]>('/analytics/by-position'+suffix),enabled:!invalid,refetchInterval:30000});
 const trends=useQuery({queryKey:['analytics','trends',position,from,to],queryFn:()=>api<Trend[]>('/analytics/trends'+suffix),enabled:!invalid,refetchInterval:30000});
 const points=useQuery({queryKey:['analytics','scatter',position,from,to],queryFn:()=>api<Point[]>('/analytics/technical-communication'+suffix),enabled:!invalid,refetchInterval:30000});
 const state=(q:{isPending:boolean;isError:boolean;refetch:()=>unknown},empty:boolean)=>invalid?<p role="alert">Correct the date range to load this chart.</p>:q.isPending?<p role="status">Loading scores...</p>:q.isError?<p role="alert">Unable to load scores. <button onClick={()=>void q.refetch()}>Retry</button></p>:empty?<p>No data for the selected filters.</p>:null;
 return <section className="analytics-report"><section className="portal-panel"><div className="analytics-filters"><label>Recruitment role<select value={position} onChange={e=>setPosition(e.target.value)}><option value="">All recruitment roles</option>{roles.data?.items.map(p=><option key={p.id} value={p.id}>{p.title}</option>)}</select></label><label>From (UTC)<input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label><label>To (UTC)<input type="date" value={to} onChange={e=>setTo(e.target.value)}/></label>{!invalid&&<><a href={'/api/analytics/export/csv'+suffix}>Export CSV</a><a className="portal-primary" href={'/api/analytics/export/pdf'+suffix}>Save as PDF</a></>}</div>{invalid&&<p role="alert">From date must be on or before To date.</p>}{roles.isError&&<p role="alert">Could not load roles. <button onClick={()=>void roles.refetch()}>Retry</button></p>}<p>Completed interviews with recorded scores only. Dates use interview completion time.</p></section>
 <div className="recruiter-columns"><section className="portal-panel"><h2>Score distribution</h2>{state(dist,!dist.data?.some(r=>r.count>0))||<Bars rows={dist.data!} label="band" value="count"/>}<small>Bands include the lower bound; only 80-100 includes its upper bound.</small></section>
 <section className="portal-panel"><h2>Average score by position</h2><p>Compares all recruitment roles; date filters apply.</p>{state(averages,!averages.data?.length)||<Bars rows={averages.data!} label="position_title" value="average_score" maximum={100}/>}</section>
 <section className="portal-panel"><h2>Monthly score trends</h2>{!from&&!to&&<p>Current month and previous 11 months (UTC).</p>}{state(trends,!trends.data?.length)||<div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={trends.data} margin={{top:15,right:20,left:0,bottom:25}} accessibilityLayer><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="month"/><YAxis domain={[0,100]}/><Tooltip/><Bar dataKey="average_score" name="Average score" fill="#527b66"/></BarChart></ResponsiveContainer></div>}</section>
 <section className="portal-panel"><h2>Technical / communication scores</h2><p>Vertical axis: Communication score (0-100)</p>{state(points,!points.data?.length)||<div className="analytics-chart"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{top:20,right:20,bottom:35,left:25}} accessibilityLayer><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="technical_score" name="Technical" domain={[0,100]} label={{value:'Technical score (0-100)',position:'bottom',offset:15}}/><YAxis type="number" dataKey="communication_score" name="Communication" domain={[0,100]}/><Tooltip cursor={{strokeDasharray:'3 3'}}/><Scatter data={points.data} fill="#527b66"/></ScatterChart></ResponsiveContainer></div>}<small>Up to 3,000 most recent scored interviews.</small></section></div></section>;
}
