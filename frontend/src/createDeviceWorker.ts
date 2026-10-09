// Live interviews and the diagnostic page must use the same detector.
export function createDeviceWorker(){
  return new Worker(new URL('./workers/device.worker.ts',import.meta.url),{type:'module'});
}
