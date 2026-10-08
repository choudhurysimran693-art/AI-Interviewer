// A classic worker is required by MediaPipe's WASM importScripts loader.
self.exports = {};
importScripts('/gaze.js');
let detector, landmarker, landmarksAvailable=false;
self.onmessage = async ({data}) => {
  const {type, frame, timestamp} = data;
  try {
    if (type === 'init') {
      importScripts('/vision/vision_bundle.js');
      const files = await self.exports.FilesetResolver.forVisionTasks('/vision/wasm');
      try {
        landmarker = await self.exports.FaceLandmarker.createFromOptions(files, {
          baseOptions:{modelAssetPath:'/models/face/face_landmarker.task',delegate:'CPU'},runningMode:'VIDEO',numFaces:2,
          outputFaceBlendshapes:false,outputFacialTransformationMatrixes:true
        });
        landmarksAvailable=true;
      } catch (_) { landmarksAvailable=false; }
      detector = await self.exports.FaceDetector.createFromOptions(files, {
        baseOptions: {modelAssetPath:'/models/face/blaze_face_short_range.tflite', delegate:'CPU'},
        runningMode:'VIDEO', minDetectionConfidence:0.75
      });
      self.postMessage({type:'ready'});
    } else if (type === 'frame') {
      const canvas = new OffscreenCanvas(frame.width, frame.height);
      canvas.getContext('2d').drawImage(frame,0,0);
      const result = detector.detectForVideo(canvas,timestamp);
      const mesh=landmarksAvailable?landmarker.detectForVideo(canvas,timestamp):null;
      const gazeResult=mesh?.faceLandmarks?.length===1?self.Gaze.classify(mesh.faceLandmarks[0],mesh.facialTransformationMatrixes?.[0]?.data):null;
      self.postMessage({type:'result', timestamp, count:result.detections.length>1&&mesh ? Math.min(result.detections.length,mesh.faceLandmarks.length) : result.detections.length,
        confidence:result.detections.length?Math.min(...result.detections.map(d=>d.categories[0].score)):null,
        ...(gazeResult||{gaze_direction:'off_screen',head_pose_angle:0}), gaze_available:landmarksAvailable, gaze_valid:!!gazeResult});
    }
  } catch (error) { self.postMessage({type:'error',message:String(error)}); }
  finally { frame?.close(); }
};
