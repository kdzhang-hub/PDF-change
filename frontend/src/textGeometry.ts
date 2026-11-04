import type {LayerElement} from './types';

// Konva clips a line that is taller than its fixed text box. Keep the same
// measured box in the saved scene and the exported PowerPoint.
export function fitTextBounds(layer:LayerElement,measure:(text:string)=>number):LayerElement{
 if(layer.kind!=='text'||layer.text_fit==='shape')return layer;
 const lines=layer.text.split('\n');
 const width=Math.max(...lines.map(text=>measure(text)+Math.max(0,Array.from(text).length-1)*(layer.char_spacing||0)),0);
 return {...layer,width:Math.min(50000,Math.max(layer.width,width+layer.font_size*.25)),
  height:Math.min(50000,Math.max(layer.height,lines.length*layer.font_size*1.3))};
}
