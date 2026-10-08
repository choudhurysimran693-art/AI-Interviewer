import {useState} from 'react';
export default function CurrentTimeButton({field}:{field:string}){
 const [immediate,setImmediate]=useState(false);
 return <><input type="hidden" name="start_now" value={String(immediate)}/><button type="button" onClick={event=>{
  const input=event.currentTarget.form?.elements.namedItem(field) as HTMLInputElement|null;
  if(input){const now=new Date();input.value=new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,16);setImmediate(true);input.oninput=()=>setImmediate(false);if(input.form)input.form.onreset=()=>setImmediate(false);}
 }}>{immediate?'Starts when you submit':'Use current time'}</button></>;
}
