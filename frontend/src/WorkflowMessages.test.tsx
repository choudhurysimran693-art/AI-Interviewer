import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {Messages,RoundUnlockedBanner,NotificationLog} from './WorkflowMessages';
import {resolveRoute} from './routes';

describe('Workflow notification views',()=>{
 it('routes candidates to Messages but keeps HR in their own workspace',()=>{
  expect(resolveRoute('candidate','/candidate/messages','')).toBe('/candidate/messages');
  expect(resolveRoute('hr','/candidate/messages','')).toBe('/hr/dashboard');
 });
 it('shows unread invitations and only banners unexpired unread rounds',()=>{
  const client=new QueryClient();
  const item={id:'n',title:'Next round: Aptitude',message:'You passed Resume Screening.',type:'next_round',href:'/candidate/interview?assignment=a',created_at:1,read:false,window_end_at:Date.now()/1000+1000};
  client.setQueryData(['candidate-notifications'],{items:[item],unread_count:1});
  const render=(child:React.ReactNode)=>renderToStaticMarkup(<QueryClientProvider client={client}>{child}</QueryClientProvider>);
  expect(render(<Messages/>)).toContain('New · Next round: Aptitude');
  expect(render(<RoundUnlockedBanner/>)).toContain('A new round is ready');
  client.setQueryData(['candidate-notifications'],{items:[{...item,read:true}],unread_count:0});
  expect(render(<RoundUnlockedBanner/>)).toBe('');
  client.setQueryData(['candidate-notifications'],{items:[{...item,window_end_at:1}],unread_count:1});
  expect(render(<RoundUnlockedBanner/>)).toBe('');
 });
 it('shows failed delivery and a retry action in the HR log',()=>{
  const client=new QueryClient();
  client.setQueryData(['workflow-log','c'],[{id:'n',type:'rejected',title:'Application update',created_at:1,email_status:'failed: SMTP error'}]);
  const html=renderToStaticMarkup(<QueryClientProvider client={client}><NotificationLog candidateId="c"/></QueryClientProvider>);
  expect(html).toContain('failed: SMTP error');expect(html).toContain('Retry email');
 });
});
