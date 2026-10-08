type FullElement=HTMLElement & {webkitRequestFullscreen?:()=>void|Promise<void>;mozRequestFullScreen?:()=>void|Promise<void>;msRequestFullscreen?:()=>void|Promise<void>};
type FullDocument=Document & {webkitFullscreenElement?:Element;mozFullScreenElement?:Element;msFullscreenElement?:Element;webkitExitFullscreen?:()=>void|Promise<void>;mozCancelFullScreen?:()=>void|Promise<void>;msExitFullscreen?:()=>void|Promise<void>};
export const fullscreenEvents=['fullscreenchange','webkitfullscreenchange','mozfullscreenchange','MSFullscreenChange'];
export function fullscreenElement(){const d=document as FullDocument;return d.fullscreenElement||d.webkitFullscreenElement||d.mozFullScreenElement||d.msFullscreenElement||null;}
export function requestFullscreen(target:HTMLElement=document.documentElement):Promise<void>{
 const e=target as FullElement,request=e.requestFullscreen||e.webkitRequestFullscreen||e.mozRequestFullScreen||e.msRequestFullscreen;
 if(fullscreenElement())return Promise.resolve();
 if(!request)return Promise.reject(new Error('Fullscreen is not supported. Please maximize your browser and avoid switching tabs. HR interviews require a browser with fullscreen support.'));
 try{return Promise.resolve(request.call(e)).catch(()=>{throw new Error('Fullscreen is required to start this interview. Please allow fullscreen and try again.');});}catch{return Promise.reject(new Error('Fullscreen is required to start this interview. Please allow fullscreen and try again.'));}
}
export async function exitFullscreen(){const d=document as FullDocument,exit=d.exitFullscreen||d.webkitExitFullscreen||d.mozCancelFullScreen||d.msExitFullscreen;if(fullscreenElement()&&exit)try{await exit.call(d);}catch{/* Browser may already have exited. */}}
