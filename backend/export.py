from __future__ import annotations
import math
from pathlib import Path
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.oxml.xmlchemy import OxmlElement
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from .models import PageScene
from .store import asset_path
from .image_assets import picture_source


def element(tag,**attributes):
    node=OxmlElement(tag)
    for key,value in attributes.items(): node.set(key,str(value))
    return node


def solid(parent,color,alpha=1):
    node=element('a:solidFill'); rgb=element('a:srgbClr',val=color.lstrip('#'))
    if alpha<1: rgb.append(element('a:alpha',val=round(alpha*100000)))
    node.append(rgb); parent.append(node)


def _style_text_run(r,layer,scale,line,spacing):
    r.font.name=layer.font; r.font.size=Pt(max(1,layer.font_size*scale))
    r.font.bold=layer.bold; r.font.italic=layer.italic
    r.font.color.rgb=RGBColor.from_string(layer.color[1:])
    rpr=r._r.get_or_add_rPr()
    if layer.stroke:
        outline=element('a:ln',w=round(layer.stroke_width*scale*12700))
        solid(outline,layer.stroke,layer.opacity*layer.stroke_opacity);rpr.insert(0,outline)
    is_cjk=any('\u2e80'<=ch<='\ua4cf' for ch in line)
    rpr.set('lang','zh-CN' if is_cjk else 'en-US')
    if spacing:rpr.set('spc',str(round(spacing*scale*100)))
    rpr.append(element('a:ea',typeface=layer.font,charset='-122' if is_cjk else '0',pitchFamily='34'))
    if is_cjk:
        for latin in rpr.xpath('./a:latin'):latin.set('charset','-122')
    if layer.text_gradient:
        for fill in rpr.xpath('./a:solidFill'):rpr.remove(fill)
        grad=element('a:gradFill',rotWithShape='1');stops=element('a:gsLst')
        for gi,value in enumerate(layer.text_gradient):
            position=layer.text_gradient_positions[gi] if layer.text_gradient_positions else gi/max(1,len(layer.text_gradient)-1)
            stop=element('a:gs',pos=round(100000*position))
            stop.append(element('a:srgbClr',val=value.lstrip('#')));stops.append(stop)
        # DrawingML fill precedes the latin/ea font elements.
        # Appending it afterwards makes Office ignore the fill.
        grad.append(stops);grad.append(element('a:lin',ang=round((layer.text_gradient_angle%360)*60000),scaled='0'));rpr.insert(1 if layer.stroke else 0,grad)
    if layer.opacity<1:
        for rgb in rpr.xpath('./a:solidFill/a:srgbClr | ./a:gradFill/a:gsLst/a:gs/a:srgbClr'):
            rgb.append(element('a:alpha',val=round(layer.opacity*100000)))
    if layer.text_shadow:
        shadow=layer.text_shadow;effects=element('a:effectLst')
        effect=element('a:outerShdw',blurRad=round(shadow.blur*scale*12700),dist=round(math.hypot(shadow.dx,shadow.dy)*scale*12700),dir=round(math.degrees(math.atan2(shadow.dy,shadow.dx))%360*60000),algn='ctr',rotWithShape='0')
        shade=element('a:srgbClr',val=shadow.color[1:]);shade.append(element('a:alpha',val=round(shadow.opacity*layer.opacity*100000)));effect.append(shade);effects.append(effect)
        fonts=list(rpr);index=next((i for i,n in enumerate(fonts) if n.tag.endswith(('latin','ea','cs'))),len(fonts));rpr.insert(index,effects)


def export_pptx(project,pages: list[PageScene],output: Path,on_page=None):
    if not pages: raise ValueError('没有可导出的页面')
    if any(p.status=='pending' for p in pages): raise ValueError('所选页面尚未转换')
    from .fonts import activate_existing
    activate_existing(l.font for page in pages for l in page.layers if l.kind=='text')
    prs=Presentation(); sw=pages[0].width; sh=pages[0].height
    # PowerPoint limits physical slide size to 56 inches.
    normalization=min(1,4032/max(sw,sh))
    sw*=normalization; sh*=normalization
    prs.slide_width=Pt(sw); prs.slide_height=Pt(sh)
    for page in pages:
        if on_page:on_page(page.index)
        slide=prs.slides.add_slide(prs.slide_layouts[6])
        font_adjustments=[]
        scale=min(sw/page.width,sh/page.height)
        ox=(sw-page.width*scale)/2; oy=(sh-page.height*scale)/2
        groups={}
        for layer in sorted(page.layers,key=lambda x:x.z):
            if not layer.visible: continue
            layout=layer.text_layout.pptx if layer.text_layout else None
            w=layer.width*scale; h=layer.height*scale
            angle=math.radians(layer.rotation)
            # Scene rotation is about upper-left; DrawingML rotates about the centre.
            x=ox+layer.x*scale+math.cos(angle)*w/2-math.sin(angle)*h/2-w/2
            y=oy+layer.y*scale+math.sin(angle)*w/2+math.cos(angle)*h/2-h/2
            if layout:
                dx,dy=layout.offset
                x+=(math.cos(angle)*dx-math.sin(angle)*dy)*scale
                y+=(math.sin(angle)*dx+math.cos(angle)*dy)*scale
            if layer.kind=='text':
                shape=slide.shapes.add_textbox(Pt(x),Pt(y),Pt(w),Pt(h))
                tf=shape.text_frame; tf.word_wrap=False
                tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
                tf.vertical_anchor=MSO_ANCHOR.TOP
                if layer.text_fit=='shape':
                    shape._element.nvSpPr.cNvSpPr.attrib.pop('txBox',None)
                    body=tf._txBody.bodyPr
                    for child in list(body):body.remove(child)
                    body.set('wrap','none')
                    warp=element('a:prstTxWarp',prst='textPlain');warp.append(element('a:avLst'));body.append(warp)
                    body.append(element('a:spAutoFit'))
                if layer.font_size*scale<1:
                    font_adjustments.append((layer.id,f'{layer.name}: 原字号小于1磅，导出按1磅处理，请核对'))
                for i,line in enumerate(layer.text.split('\n')):
                    p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
                    p.space_before=Pt(0); p.space_after=Pt(0)
                    p.line_spacing=Pt(layer.font_size*scale*1.2)
                    pieces=list(line) if layout else [line]
                    for character_index,piece in enumerate(pieces):
                        r=p.add_run(); r.text=piece
                        _style_text_run(r,layer,scale,line,layout.spacing[character_index] if layout else layer.char_spacing)
            elif layer.kind=='image':
                shape=slide.shapes.add_picture(picture_source(asset_path(project,layer.asset),w,h),Pt(x),Pt(y),Pt(w),Pt(h))
                if layer.opacity<1:
                    shape._element.blipFill.blip.append(element('a:alphaModFix',amt=round(layer.opacity*100000)))
            else:
                shape=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Pt(x),Pt(y),Pt(w),Pt(h))
                sp=shape._element.spPr
                # The default template adds theme shadows to newly-created shapes.
                # PDF paints do not imply that theme effect; remove it explicitly.
                for style in shape._element.xpath('./p:style'): shape._element.remove(style)
                for child in list(sp):
                    if child.tag.endswith(('prstGeom','solidFill','ln')): sp.remove(child)
                geom=element('a:custGeom')
                for tag in ('avLst','gdLst','ahLst','cxnLst'): geom.append(element('a:'+tag))
                geom.append(element('a:rect',l='0',t='0',r='r',b='b'))
                paths=element('a:pathLst')
                path=element('a:path',w=max(1,round(layer.width*1000)),h=max(1,round(layer.height*1000)),
                             fill='norm' if layer.fill else 'none',stroke='1' if layer.stroke else '0')
                for cmd in layer.path:
                    node=element({'M':'a:moveTo','L':'a:lnTo','C':'a:cubicBezTo','Z':'a:close'}[cmd.op])
                    for i in range(0,len(cmd.points),2): node.append(element('a:pt',x=round(cmd.points[i]*1000),y=round(cmd.points[i+1]*1000)))
                    path.append(node)
                paths.append(path); geom.append(paths); sp.append(geom)
                if layer.fill: solid(sp,layer.fill,layer.opacity*layer.fill_opacity)
                else: sp.append(element('a:noFill'))
                line=element('a:ln',w=round(layer.stroke_width*scale*12700),cap='flat')
                if layer.stroke: solid(line,layer.stroke,layer.opacity*layer.stroke_opacity)
                else: line.append(element('a:noFill'))
                line.append(element('a:miter',lim=800000))
                sp.append(line)
                sp.append(element('a:effectLst'))
            shape.rotation=layer.rotation%360
            shape.name=layer.name
            nv=shape._element.xpath('.//p:cNvPr')[0]
            nv.set('descr',f'LayerDeck:{layer.id}; source={layer.source}; inferred={layer.inferred}; review={layer.needs_review}')
            if layer.group_id: groups.setdefault(layer.group_id,[]).append(shape)
        # Group only contiguous shapes so explicit drawing order never changes.
        for members in groups.values():
            order=list(slide.shapes); positions=[order.index(s) for s in members]
            if len(members)>1 and max(positions)-min(positions)+1==len(members):
                tree=slide.shapes._spTree; insertion=list(tree).index(members[0]._element)
                group=slide.shapes.add_group_shape(members)
                tree.remove(group._element); tree.insert(insertion,group._element)
        slide.notes_slide.notes_text_frame.text='LayerDeck 分层还原。'+ '\n'.join(page.warnings)+ '\n'+ '\n'.join(
            f'{l.name}: 推断补全，需人工确认' for l in page.layers if l.inferred)+'\n'+'\n'.join(item[1] for item in font_adjustments)
    prs.save(output)
    from .font_assets import embed
    embed(project,pages,output,'pptx')
    return output
