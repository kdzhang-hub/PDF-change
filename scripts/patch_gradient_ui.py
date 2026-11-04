from pathlib import Path
root=Path(__file__).resolve().parents[1]
types=root/'frontend'/'src'/'types.ts'
text=types.read_text('utf-8')
text=text.replace('export type LayerElement={','export type LayerElement=TextGradient & {')
types.write_text(text,'utf-8')
app=root/'frontend'/'src'/'main.tsx'
text=app.read_text('utf-8')
anchor='function IconButton('
helper='''function textPaint(l:LayerElement){return l.text_gradient?.length?{fillPriority:'linear-gradient' as const,fillLinearGradientStartPoint:{x:0,y:0},fillLinearGradientEndPoint:{x:0,y:l.font_size},fillLinearGradientColorStops:l.text_gradient.flatMap((color,i)=>[i/Math.max(1,l.text_gradient!.length-1),color])}:{}}
'''
if 'function textPaint(' not in text:text=text.replace(anchor,helper+anchor)
text=text.replace('<Text text={l.text}','<Text {...textPaint(l)} text={l.text}')
app.write_text(text,'utf-8')
