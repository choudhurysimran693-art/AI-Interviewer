// Independent CPU worker: a face or gaze failure cannot disable object detection.
self.exports = {};
let detector, canvas, context;
let threshold=.35;
self.onmessage = async ({data}) => {
  const {type, frame, timestamp} = data;
  try {
    if (type === 'init') {
      threshold=Number.isFinite(data.threshold)?data.threshold:.35;
      importScripts('/vision/vision_bundle.js');
      const files = await self.exports.FilesetResolver.forVisionTasks('/vision/wasm');
      detector = await self.exports.ObjectDetector.createFromOptions(files, {
        baseOptions:{modelAssetPath:'/models/efficientdet_lite0.tflite',delegate:'CPU'},
        runningMode:'IMAGE',scoreThreshold:threshold,maxResults:20,categoryAllowlist:['cell phone','laptop']
      });
      self.postMessage({type:'ready'});
    } else if (type === 'frame') {
      const start=performance.now();
      // Reuse the pixel buffer instead of allocating one for every scan.
      if(!canvas){canvas=new OffscreenCanvas(frame.width,frame.height);context=canvas.getContext('2d');}
      if(canvas.width!==frame.width)canvas.width=frame.width;
      if(canvas.height!==frame.height)canvas.height=frame.height;
      context.drawImage(frame,0,0);
      const result=detector.detect(canvas);
      const detections=result.detections.flatMap(d=>{
        const category=d.categories[0];
        // Person/face classes never enter the device pipeline. This model has no tablet class.
        if(!category||category.score<threshold||!['cell phone','laptop'].includes(category.categoryName))return [];
        const b=d.boundingBox;
        return [{label:category.categoryName==='cell phone'?'mobile phone':'laptop computer',score:category.score,
          box:{xmin:b.originX,ymin:b.originY,xmax:b.originX+b.width,ymax:b.originY+b.height}}];
      });
      self.postMessage({type:'result',timestamp,latency:performance.now()-start,backend:'CPU',model:'EfficientDet Lite0',detections});
    }
  } catch(error) {self.postMessage({type:'error',message:String(error)});}
  finally {frame?.close();}
};
