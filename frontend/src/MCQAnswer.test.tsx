import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {MCQAnswer} from './MCQAnswer';
const props={options:[{id:'a',text:'700'},{id:'b',text:'680'}],value:'b',onChange:()=>{},onSubmit:()=>{},busy:false,paused:false};
describe('MCQ answer controls',()=>{
  it('locks expired choices but permits retry of an unanswered timeout',()=>{
    const html=renderToStaticMarkup(<MCQAnswer {...props} value="" expired/>);
    expect(html).toContain('<fieldset disabled=""');
    expect(html).toContain('Time is up.');
    expect(html).toContain('<button class="button">');
    expect(renderToStaticMarkup(<MCQAnswer {...props} value="" expired paused/>)).toContain('<button class="button" disabled=""');
  });
  it('uses labelled options and a single submit-and-next action',()=>{
    const html=renderToStaticMarkup(<MCQAnswer {...props}/>);
    expect(html).toContain('mcq-choice selected');expect(html).toContain('type="radio"');
    expect(html).toContain('Submit &amp; next');expect(html).not.toContain('Review selection');
    expect(html).not.toContain('<select');expect(html).not.toContain('disabled');
  });
  it('prevents duplicate submissions during save and shows final action',()=>{
    expect(renderToStaticMarkup(<MCQAnswer {...props} busy/>)).toContain('Saving…');
    expect(renderToStaticMarkup(<MCQAnswer {...props} busy/>)).toContain('disabled');
    expect(renderToStaticMarkup(<MCQAnswer {...props} last/>)).toContain('Submit final answer');
    expect(renderToStaticMarkup(<MCQAnswer {...props} value=""/>)).toContain('disabled');
  });
});
