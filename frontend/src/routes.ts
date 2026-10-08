export const dashboardFor = (role:string) => role === 'candidate' ? '/candidate/dashboard' : '/hr/dashboard';

// Resolve only after /auth/me has returned the server-authenticated role.
export function resolveRoute(role:string|null, path:string, search:string,workspace:'candidate'|'practice'='candidate'):string {
  const query = new URLSearchParams(search);
  if(query.has('reset')) return '/login'+search;
  if(!role) return '/login';
  const home = dashboardFor(role);
  const candidate = role === 'candidate';
  if(path.startsWith('/report/')) return path+search;
  if(path.startsWith(candidate ? '/hr/' : '/candidate/')) return home;
  if(query.has('review')) return candidate ? home : '/hr/reports?review='+encodeURIComponent(query.get('review')!);
  if(query.has('assignment')||query.has('resume')) return candidate ? '/candidate/interview'+search : home;
  if(candidate&&workspace==='candidate'&&(path==='/candidate/practice'||query.get('workspace')==='practice'))return home;
  if(query.has('workspace')) return candidate && query.get('workspace')==='practice' ? '/candidate/practice' : home;
  const pages=candidate?['dashboard','practice','interview','results','profile','positions','applications']:['dashboard','candidates','interviews','jobs','reports','applications'];
  return pages.some(page=>path===`${candidate?'/candidate':'/hr'}/${page}`) ? path+search : home;
}
