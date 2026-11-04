import {useEffect,useState} from 'react';
import type {PageScene} from './types';

const loaded=new Map<string,FontFace>();
export function useProjectFonts(project:string|undefined,scene:PageScene|null){
 const [version,setVersion]=useState(0),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const fonts=Array.from(new Map((scene?.layers||[]).filter(l=>l.font_asset).map(l=>[l.font_asset!.file,{family:l.font,file:l.font_asset!.file}])).values());
 const signature=JSON.stringify(fonts);
 useEffect(()=>{
  let stopped=false;setError('');
  if(!project||!fonts.length){setLoading(false);return}
  setLoading(true);
  Promise.all(fonts.map(async({family,file})=>{
   const key=project+':'+file+':'+family;if(loaded.has(key))return;
   const face=new FontFace(family,`url("/api/projects/${encodeURIComponent(project)}/assets/${encodeURIComponent(file)}")`);
   await face.load();document.fonts.add(face);loaded.set(key,face);
  })).then(()=>{if(!stopped){setVersion(n=>n+1);setLoading(false)}}).catch(()=>{if(!stopped){setError('还原字体未能加载，项目已保留；请重新打开项目或替换字体');setLoading(false)}});
  return()=>{stopped=true};
 },[project,signature]);
 return {version,loading,error};
}
