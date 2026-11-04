"""Optional CPU analysis adapters. No identity recognition or hiring decisions."""
import math
from pathlib import Path


def semantic(answer, points, model_path):
    if not answer.strip() or not points:return {'status':'unavailable','reason':'An answer and reference rubric are required.'}
    if not Path(model_path).is_dir():return {'status':'unavailable','reason':'Sentence model is not prepared.'}
    import numpy as np
    from sentence_transformers import SentenceTransformer
    model=SentenceTransformer(model_path,device='cpu',local_files_only=True,trust_remote_code=False)
    # Avoid silently truncating an entire long answer to the encoder window.
    words=answer.split();chunks=[' '.join(words[i:i+100]) for i in range(0,min(len(words),3000),100)]
    vectors=model.encode(chunks+points,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
    scores=np.clip(vectors[len(chunks):] @ vectors[:len(chunks)].T,-1,1).max(axis=1)
    if not np.isfinite(scores).all():return {'status':'unavailable','reason':'The model returned invalid similarity values.'}
    return {'status':'ready','model':'all-MiniLM-L6-v2','metric':'cosine_similarity','similarity':round(float(scores.mean()),3),'rubric_matches':[{'point':p,'similarity':round(float(v),3)} for p,v in zip(points,scores)],'limitation':'Semantic similarity is not correctness. Negation, incorrect facts and copied rubric text can still match. It does not alter interview marks.'}


def voice(path):
    import librosa
    import numpy as np
    y,sr=librosa.load(path,sr=16000,mono=True,duration=30)
    if len(y)<sr*.5 or not np.isfinite(y).all():return {'status':'unavailable','reason':'Provide at least half a second of valid audio.'}
    rms=librosa.feature.rms(y=y)[0]
    if float(np.max(rms))<.0001:return {'status':'unavailable','reason':'No audible signal detected.'}
    return {'status':'ready','duration_seconds':round(len(y)/sr,2),'rms_level_dbfs':round(20*math.log10(max(float(np.sqrt(np.mean(y*y))),1e-9)),1),'quiet_frame_percent':round(float(np.mean(rms<max(.001,float(np.max(rms))*.05)))*100,1),'clipping_percent':round(float(np.mean(np.abs(y)>=.99))*100,2),'spectral_centroid_hz':round(float(np.mean(librosa.feature.spectral_centroid(y=y,sr=sr))),1),'limitation':'Recording-level acoustic measurements, not emotion, confidence, accent quality or interview marks. Microphone settings and background noise affect results.'}


def expression(path):
    import os
    weights=Path(os.environ.get('DEEPFACE_HOME',str(Path.home())))/'.deepface'/'weights'/'facial_expression_model_weights.h5'
    if not weights.is_file():return {'status':'unavailable','reason':'Expression model is not prepared. Run the model setup first.'}
    import cv2
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    from deepface import DeepFace
    image=cv2.imread(str(path))
    if image is None:return {'status':'unavailable','reason':'The photo could not be decoded.'}
    scale=min(640/image.shape[1],480/image.shape[0],1)
    if scale<1:image=cv2.resize(image,(max(1,int(image.shape[1]*scale)),max(1,int(image.shape[0]*scale))))
    # Explicit allowlist: never run age, race, gender, identity or verification models.
    detector=cv2.CascadeClassifier(str(Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml'))
    if detector.empty():return {'status':'unavailable','reason':'The OpenCV face detector is not installed correctly.'}
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    faces=detector.detectMultiScale(gray,scaleFactor=1.2,minNeighbors=5,minSize=(32,32))
    if len(faces)!=1:return {'status':'unavailable','reason':'Use a photo showing exactly one face.'}
    # Detection has already enforced one face. Reuse that crop rather than scanning twice.
    x,y,w,h=faces[0]
    rows=DeepFace.analyze(img_path=image[y:y+h,x:x+w],actions=['emotion'],detector_backend='skip',enforce_detection=True,silent=True)
    if isinstance(rows,dict):rows=[rows]
    if len(rows)!=1:return {'status':'unavailable','reason':'Use a photo showing exactly one face.'}
    values=rows[0].get('emotion',{})
    labels={'happy':'smile-like','surprise':'surprise-like','neutral':'neutral-like','sad':'sadness-like','angry':'anger-like','fear':'fear-like','disgust':'disgust-like'}
    distribution=[{'label':label+' expression','value':round(float(values[key]),1)} for key,label in labels.items() if key in values and math.isfinite(float(values[key]))]
    if len(distribution)!=7:return {'status':'unavailable','reason':'Expression model output was incomplete.'}
    return {'status':'ready','model':'DeepFace expression model','distribution':distribution,'limitation':'Experimental visual-pattern labels. These are not evidence of feelings, personality, honesty or suitability. Results are private practice feedback and do not affect marks.'}
