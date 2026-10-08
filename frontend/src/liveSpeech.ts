// Browser speech recognition supplies provisional captions; the saved audio is
// transcribed on the server and reviewed before evaluation.
export function startLiveSpeech(onText:(text:string)=>void,onStatus:(text:string)=>void):()=>void {
  const Speech=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;
  if(!Speech){onStatus('Live captions are unavailable in this browser. Your recording will be transcribed after submission.');return ()=>{};}
  const recognition=new Speech();recognition.continuous=true;recognition.interimResults=true;recognition.lang='en-US';
  recognition.onresult=(event:any)=>{let text='';for(let i=0;i<event.results.length;i++)text+=event.results[i][0].transcript+' ';onText(text.trim());};
  recognition.onerror=()=>onStatus('Live captions interrupted. Audio recording continues; review the final transcript after submission.');
  recognition.onend=()=>onStatus('Live captions ended. Your audio recording is still saved for transcription.');
  try{recognition.start();onStatus('Live captions are provisional. Your browser may use its speech service to process audio.');}catch{onStatus('Live captions unavailable. Audio will be transcribed after submission.');}
  return ()=>{recognition.onend=null;recognition.abort();};
}
