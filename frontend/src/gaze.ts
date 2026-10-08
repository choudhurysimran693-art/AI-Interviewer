import '../public/gaze.js';
declare global {var Gaze:{Window:new(seconds?:number,awaySeconds?:number)=>{reset:()=>void;add:(direction:string,time:number)=>{percent:number|null;violation:boolean;duration:number}};classify:(points:unknown[],matrix:number[])=>{gaze_direction:string;head_pose_angle:number;head_pitch:number;movement:string}|null};}
export const GazeWindow=globalThis.Gaze.Window;
