import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {applicationItems,CandidateApplicationList,OpenPositionList,positionItems} from './Applications';
const application={id:'a',candidate:'Candidate',candidate_id:'c',position:'Backend Engineer',position_id:'p',status:'applied',applied_at:1750000000,updated_at:1750000000};
const render=(extra={})=>renderToStaticMarkup(<CandidateApplicationList pending={false} failed={false} items={[]} retry={()=>{}} {...extra}/>);
const roles=[{id:'p',title:'Backend Engineer',department:'Engineering',description:'Build APIs',vacancies_remaining:2},{id:'q',title:'QA Engineer',department:'Quality',vacancies_remaining:1}];
const renderPositions=(extra={})=>renderToStaticMarkup(<OpenPositionList pending={false} failed={false} positions={[]} applications={[]} retry={()=>{}} apply={()=>{}} {...extra}/>);
describe('open positions states',()=>{
 it('shows loading without an empty state',()=>{const html=renderPositions({pending:true});expect(html).toContain('Loading open positions');expect(html).not.toContain('Check back soon');});
 it('shows retry instead of stale cards or empty text on errors',()=>{const html=renderPositions({failed:true,positions:roles});expect(html).toContain('Something went wrong loading open positions. Please try again.');expect(html).toContain('Retry</button>');expect(html).not.toContain('Backend Engineer');expect(html).not.toContain('Check back soon');expect(html).not.toContain('Not Found');});
 it('shows the requested successful empty state',()=>{expect(renderPositions()).toContain('There are no open positions right now. Check back soon.');});
 it('shows role details and disables already applied roles after applications refresh',()=>{const before=renderPositions({positions:roles});expect(before.match(/>Apply<\/button>/g)).toHaveLength(2);const after=renderPositions({positions:roles,applications:[application]});expect(after).toContain('disabled="">Applied</button>');expect(after).toContain('>Apply</button>');expect(after).toContain('Build APIs');expect(after).toContain('2 vacancies remaining');expect(after).toContain('Engineering');});
 it('accepts array and legacy responses, rejects invalid success data',()=>{expect(positionItems([])).toEqual([]);expect(positionItems({items:roles})).toEqual(roles);expect(()=>positionItems({detail:'Not Found'} as never)).toThrow();});
});
describe('candidate application states',()=>{
 it('loads without showing an empty state',()=>{const html=render({pending:true});expect(html).toContain('Loading your applications');expect(html).not.toContain("haven&#x27;t applied");});
 it('failed requests have a retry action, never an empty state',()=>{const html=render({failed:true});expect(html).toContain('Something went wrong loading your applications. Please try again.');expect(html).toContain('Retry</button>');expect(html).not.toContain('Not Found');expect(html).not.toContain('Browse open positions');});
 it('only a successful empty result shows the browse CTA',()=>{const html=render();expect(html).toContain('Applications</h1>');expect(html).toContain("You haven&#x27;t applied to any roles yet.");expect(html).toContain('href="/candidate/positions"');});
 it('shows one application and multiple applications',()=>{expect(render({items:[application]})).toContain('Backend Engineer');const html=render({items:[application,{...application,id:'b',position:'QA Engineer',status:'interview_scheduled',assignment_id:'assignment'}]});expect(html).toContain('QA Engineer');expect(html).toContain('Interview scheduled');expect(html).toContain('href="/candidate/interview"');expect(html).not.toContain('Browse open positions');});
 it('does not link an unscheduled application to an interview',()=>{expect(render({items:[application]})).not.toContain('href="/candidate/interview"');});
 it('supports the array contract and legacy envelopes but rejects malformed success bodies',()=>{expect(applicationItems([])).toEqual([]);expect(applicationItems({items:[application]})).toEqual([application]);expect(()=>applicationItems({detail:'Not Found'} as never)).toThrow();});
});
