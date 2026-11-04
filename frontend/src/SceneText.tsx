import {useMemo} from 'react';
import {Shape,Text} from 'react-konva';
import type {LayerElement} from './types';
import {gradientLine,glyphGradientLine} from './gradientGeometry';

function fontStyle(layer:LayerElement){return [layer.bold?'bold':'',layer.italic?'italic':''].join(' ')}

export function SceneText({layer:l}:{layer:LayerElement}){
 const fit=useMemo(()=>{
  if(l.text_fit!=='shape'||!l.text.trim())return null;
  const context=document.createElement('canvas').getContext('2d');if(!context)return null;
  const fontSize=256,tracking=(l.char_spacing||0)*fontSize/l.font_size;
  context.font=`${fontStyle(l)} ${fontSize}px ${JSON.stringify(l.font)}`;context.textBaseline='middle';
  const metrics=context.measureText(l.text),spacing=tracking*Math.max(0,Array.from(l.text).length-1);
  let left=-metrics.actualBoundingBoxLeft,top=fontSize/2-metrics.actualBoundingBoxAscent;
  let width=metrics.actualBoundingBoxLeft+metrics.actualBoundingBoxRight+spacing;
  let height=metrics.actualBoundingBoxAscent+metrics.actualBoundingBoxDescent;
  // Font ink metrics can include grid-fitting bearings. Measure the actual
  // glyph paint in a bounded local probe so selection and resizing use ink.
  const probe=document.createElement('canvas'),pad=32;
  probe.width=Math.ceil(Math.max(metrics.width,width)+Math.abs(spacing)+pad*4);probe.height=fontSize*3;
  if(probe.width<=4096){
   const ink=probe.getContext('2d',{willReadFrequently:true});
   if(ink){
    ink.font=context.font;ink.textBaseline='middle';const originX=pad+Math.max(0,metrics.actualBoundingBoxLeft),originY=fontSize;
    if(tracking){let x=originX;for(const char of Array.from(l.text)){ink.fillText(char,x,originY);x+=ink.measureText(char).width+tracking}}
    else ink.fillText(l.text,originX,originY);
    const pixels=ink.getImageData(0,0,probe.width,probe.height).data;
    let x0=probe.width,y0=probe.height,x1=-1,y1=-1;
    for(let y=0;y<probe.height;y++)for(let x=0;x<probe.width;x++)if(pixels[(y*probe.width+x)*4+3]>16){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y)}
    if(x1>=x0&&y1>=y0){left=x0-originX;top=y0-originY+fontSize/2;width=x1-x0+1;height=y1-y0+1}
   }
  }
  if(width<=0||height<=0)return null;
  return {left,top,width,height,fontSize,tracking,canvasWidth:Math.max(width,metrics.width+spacing)+fontSize,canvasHeight:fontSize*2};
 },[l.text_fit,l.text,l.font,l.font_size,l.bold,l.italic,l.char_spacing]);
 const line=gradientLine(l.width,l.text_gradient_positions?.length?l.height:l.font_size,l.text_gradient_angle??90);
 const gradient=l.text_gradient?.length?{
  fillPriority:'linear-gradient' as const,fillLinearGradientStartPoint:line.start,
  fillLinearGradientEndPoint:line.end,
  fillLinearGradientColorStops:l.text_gradient.flatMap((color,i)=>[l.text_gradient_positions?.[i]??i/Math.max(1,l.text_gradient!.length-1),color]),
 }:{};
 if(l.text_layout)return <Shape width={l.width} height={l.height} fill={l.color}
  sceneFunc={context=>{
   context.save();context.setAttr('font',`${fontStyle(l)} ${l.font_size}px ${JSON.stringify(l.font)}`);
   context.setAttr('textBaseline','alphabetic');context.setAttr('textAlign','left');context.setAttr('fillStyle',l.color);
   Array.from(l.text).forEach((char,i)=>{const point=l.text_layout!.positions[i];if(point)context.fillText(char,point[0],point[1])});
   context.restore();
  }} hitFunc={(context,shape)=>{context.beginPath();context.rect(0,0,l.width,l.height);context.closePath();context.fillStrokeShape(shape)}}/>;
 if(fit)return <Shape width={l.width} height={l.height} fill={l.color} stroke={l.stroke||undefined}
  strokeWidth={l.stroke?l.stroke_width:0} shadowEnabled={!!l.text_shadow} shadowColor={l.text_shadow?.color}
  shadowOpacity={l.text_shadow?.opacity} shadowBlur={l.text_shadow?.blur}
  shadowOffsetX={l.text_shadow?.dx} shadowOffsetY={l.text_shadow?.dy}
  sceneFunc={context=>{
   const sx=l.width/fit.width,sy=l.height/fit.height;
   context.save();context.scale(sx,sy);context.translate(-fit.left,-fit.top);
   context.setAttr('font',`${fontStyle(l)} ${fit.fontSize}px ${JSON.stringify(l.font)}`);
   context.setAttr('textBaseline','middle');context.setAttr('textAlign','left');
   let fill:string|CanvasGradient=l.color;
   if(l.text_gradient?.length){
    const points=glyphGradientLine(l.width,l.height,sx,sy,l.text_gradient_angle??90);
    const g=context.createLinearGradient(fit.left+points.start.x,fit.top+points.start.y,fit.left+points.end.x,fit.top+points.end.y);
    l.text_gradient.forEach((color,i)=>g.addColorStop(l.text_gradient_positions?.[i]??i/(l.text_gradient!.length-1),color));fill=g;
   }
   context.setAttr('fillStyle',fill);
   context.setAttr('strokeStyle',l.stroke||l.color);context.setAttr('lineWidth',l.stroke_width/Math.sqrt(sx*sy));
   const draw=(word:string,x:number)=>{if(l.stroke)context.strokeText(word,x,fit.fontSize/2);context.fillText(word,x,fit.fontSize/2)};
   if(fit.tracking){let x=0;for(const char of Array.from(l.text)){draw(char,x);x+=context.measureText(char).width+fit.tracking}}
   else draw(l.text,0);
   context.restore();
  }} hitFunc={(context,shape)=>{context.beginPath();context.rect(0,0,l.width,l.height);context.closePath();context.fillStrokeShape(shape)}}/>;
 return <Text {...gradient} text={l.text}
  letterSpacing={l.char_spacing||0} width={l.width} height={l.height}
  fontSize={l.font_size} fontFamily={l.font} fontStyle={fontStyle(l)} fill={l.color}
  stroke={l.stroke||undefined} strokeWidth={l.stroke?l.stroke_width:0} fillAfterStrokeEnabled
  shadowEnabled={!!l.text_shadow} shadowColor={l.text_shadow?.color} shadowOpacity={l.text_shadow?.opacity}
  shadowBlur={l.text_shadow?.blur} shadowOffsetX={l.text_shadow?.dx} shadowOffsetY={l.text_shadow?.dy}
  wrap="none" lineHeight={1.2}/>;
}
