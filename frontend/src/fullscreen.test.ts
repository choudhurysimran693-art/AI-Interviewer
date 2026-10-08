import {afterEach,describe,expect,it,vi} from 'vitest';
import {requestFullscreen,exitFullscreen,fullscreenElement} from './fullscreen';
afterEach(()=>vi.unstubAllGlobals());
describe('fullscreen compatibility',()=>{
 for(const method of ['requestFullscreen','webkitRequestFullscreen','mozRequestFullScreen','msRequestFullscreen'])it('calls '+method+' synchronously before returning',async()=>{const request=vi.fn();const element={[method]:request};vi.stubGlobal('document',{documentElement:element});const pending=requestFullscreen();expect(request).toHaveBeenCalledOnce();await pending;});
 it('reports rejected permission requests',async()=>{vi.stubGlobal('document',{documentElement:{requestFullscreen:()=>Promise.reject(new Error('denied'))}});await expect(requestFullscreen()).rejects.toThrow('Please allow fullscreen');});
 it('explains unsupported browsers',async()=>{vi.stubGlobal('document',{documentElement:{}});await expect(requestFullscreen()).rejects.toThrow('maximize your browser');});
 it('recognizes and exits prefixed fullscreen',async()=>{const element={},exit=vi.fn();vi.stubGlobal('document',{webkitFullscreenElement:element,webkitExitFullscreen:exit});expect(fullscreenElement()).toBe(element);await exitFullscreen();expect(exit).toHaveBeenCalledOnce();});
});
