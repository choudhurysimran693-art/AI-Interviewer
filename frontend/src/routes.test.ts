import {describe,it,expect} from 'vitest';
import {resolveRoute} from './routes';
describe('authenticated role routing',()=>{
  it('redirects retired assessment and progress pages to the workspace',()=>{
    expect(resolveRoute('hr','/hr/assessment','')).toBe('/hr/dashboard');
    expect(resolveRoute('candidate','/hr/assessment','')).toBe('/candidate/dashboard');
    expect(resolveRoute('candidate','/candidate/progress','','practice')).toBe('/candidate/dashboard');
    expect(resolveRoute('hr','/candidate/progress','')).toBe('/hr/dashboard');
  });
  it('sends anonymous requests to login',()=>expect(resolveRoute(null,'/hr/dashboard','')).toBe('/login'));
  it('lands each account in its dashboard',()=>{
    expect(resolveRoute('hr','/','')).toBe('/hr/dashboard');
    expect(resolveRoute('candidate','/login','')).toBe('/candidate/dashboard');
  });
  it('blocks the other role including legacy URLs',()=>{
    expect(resolveRoute('hr','/candidate/practice','')).toBe('/hr/dashboard');
    expect(resolveRoute('candidate','/hr/reports','')).toBe('/candidate/dashboard');
    expect(resolveRoute('hr','/','?workspace=practice')).toBe('/hr/dashboard');
    expect(resolveRoute('candidate','/','?review=123')).toBe('/candidate/dashboard');
  });
  it('preserves refresh and old assignment links',()=>{
    expect(resolveRoute('admin','/hr/dashboard','')).toBe('/hr/dashboard');
    expect(resolveRoute('candidate','/candidate/dashboard','')).toBe('/candidate/dashboard');
    expect(resolveRoute('candidate','/','?assignment=123')).toBe('/candidate/interview?assignment=123');
  });
  it('keeps practice tracks out of candidate exam sign-in',()=>{
    expect(resolveRoute('candidate','/candidate/practice','')).toBe('/candidate/dashboard');
    expect(resolveRoute('candidate','/','?workspace=practice')).toBe('/candidate/dashboard');
    expect(resolveRoute('candidate','/candidate/practice','','practice')).toBe('/candidate/practice');
    expect(resolveRoute('candidate','/candidate/results','?session=practice-id','practice')).toBe('/candidate/results?session=practice-id');
  });
});
