import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {RoundHistory,type Round} from './Rounds';

const base:Round={id:'r2',round_id:'d2',round_name:'Aptitude',round_type:'aptitude',status:'pending'};
describe('Sequential round actions',()=>{
  it('keeps pending rounds locked without start or resume actions',()=>{
    const html=renderToStaticMarkup(<RoundHistory rounds={[base]}/>);
    expect(html).toContain('Locked');
    expect(html).not.toContain('Start Round');
    expect(html).not.toContain('Resume Round');
  });
  it('offers the current invitation and resumes a saved attempt',()=>{
    const start=renderToStaticMarkup(<RoundHistory rounds={[{...base,status:'invited',is_current:true,can_start:true,assignment_id:'a2'}]}/>);
    expect(start).toContain('Start Round');
    expect(start).toContain('/candidate/interview?assignment=a2');
    const resume=renderToStaticMarkup(<RoundHistory rounds={[{...base,status:'in_progress',is_current:true,can_resume:true,resume_session_id:'s2'}]}/>);
    expect(resume).toContain('Resume Round');
    expect(resume).not.toContain('Start Round');
  });
  it('keeps manual final decisions available only in the recruiter view',()=>{
    const final:Round={...base,round_type:'final_interview',evaluation_mode:'human_only',status:'scheduled',scheduled_at:1};
    const save=async()=>{};
    expect(renderToStaticMarkup(<RoundHistory rounds={[final]} save={save}/>)).not.toContain('Select candidate');
    const html=renderToStaticMarkup(<RoundHistory rounds={[final]} hr save={save}/>);
    expect(html).toContain('Select candidate');
    expect(html).toContain('Reject candidate');
  });
});
