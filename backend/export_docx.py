"""Export the same edited scene as native, page-positioned Word objects.

Text stays Word text inside movable text boxes or native WordArt. This is layout preservation,
not automatic reconstruction of flowing paragraphs or semantic tables.
"""
import zipfile,math
from lxml import etree as E
from PIL import Image
from .store import asset_path
from .image_assets import png_bytes

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'v':'urn:schemas-microsoft-com:vml','o':'urn:schemas-microsoft-com:office:office',
    'w10':'urn:schemas-microsoft-com:office:word','rel':'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct':'http://schemas.openxmlformats.org/package/2006/content-types',
    'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'mc':'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'w14':'http://schemas.microsoft.com/office/word/2010/wordml',
    'wps':'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'}


def node(tag,parent=None,**attrs):
    prefix,name=tag.split(':');value=E.Element('{'+NS[prefix]+'}'+name)
    for key,item in attrs.items():
        if ':' in key:
            p,n=key.split(':');key='{'+NS[p]+'}'+n
        value.set(key,str(item))
    if parent is not None:parent.append(value)
    return value


def xml(value):return E.tostring(value,xml_declaration=True,encoding='UTF-8',standalone=True)


def word_z_order(z):
    # Use one Word foreground range for both VML and DrawingML. Small raw
    # DrawingML values otherwise sort below Word's normalized VML pictures.
    return 251658240+(z+1)*1024


def native_wordart(layer):
    # Word ignores independent horizontal textPlain scaling in modern text
    # boxes. Its native whole-word text path does fit both frame dimensions.
    # Complex effects and tracking keep their modern representation until
    # their native WordArt equivalents have passed actual rendering checks.
    # VML text paths also fall back when the recovered font is only embedded;
    # modern text boxes consume the document's embedded font correctly.
    return (layer.kind=='text' and layer.text_fit=='shape' and bool(layer.text.strip())
            and not layer.font_asset and not layer.text_gradient and not layer.text_shadow and not layer.char_spacing)


def wordart_type(parent):
    """The straight WordArt type serialized by the installed Word application."""
    shape=node('v:shapetype',parent,id='_x0000_t136',coordsize='21600,21600',adj=10800,
               path='m@7,l@8,m@5,21600l@6,21600e',**{'o:spt':136})
    formulas=node('v:formulas',shape)
    for formula in ('sum #0 0 10800','prod #0 2 1','sum 21600 0 @1','sum 0 0 @2','sum 21600 0 @3',
                    'if @0 @3 0','if @0 21600 @1','if @0 0 @2','if @0 @4 21600','mid @5 @6',
                    'mid @8 @5','mid @7 @8','mid @6 @7','sum @6 0 @5'):node('v:f',formulas,eqn=formula)
    node('v:path',shape,textpathok='t',**{'o:connecttype':'custom','o:connectlocs':'@9,0;@10,10800;@11,21600;@12,10800','o:connectangles':'270,180,90,0'})
    node('v:textpath',shape,on='t',fitshape='t')
    node('v:h',node('v:handles',shape),position='#0,bottomRight',xrange='6629,14971')
    node('o:lock',shape,**{'v:ext':'edit','text':'t','shapetype':'t'})


def whole_wordart(parent,layer,style,declare_type):
    picture=node('w:pict',node('w:r',parent))
    if declare_type:wordart_type(picture)
    shape=node('v:shape',picture,id='layer_'+layer.id,type='#_x0000_t136',style=style,
               filled='t',fillcolor=layer.color,stroked='t' if layer.stroke else 'f',alt=layer.name)
    node('v:fill',shape,opacity=layer.opacity)
    if layer.stroke:
        shape.set('strokecolor',layer.stroke);shape.set('strokeweight',f'{layer.stroke_width}pt')
        node('v:stroke',shape,opacity=layer.opacity*layer.stroke_opacity)
    family=layer.font.replace('\\','\\\\').replace('"','\\"').replace('\r',' ').replace('\n',' ')
    font=f'font-family:"{family}";font-size:{layer.font_size}pt;v-text-kern:t'
    if layer.bold:font+=';font-weight:bold'
    if layer.italic:font+=';font-style:italic'
    node('v:textpath',shape,style=font,trim='t',fitpath='t',string=layer.text)
    return shape


def text_effects(properties,layer):
    """Keep fill, outline and shadow attached to editable Word glyphs."""
    def color(parent,value,opacity):
        rgb=node('w14:srgbClr',parent,**{'w14:val':value[1:].upper()})
        # Word font effects serialize transparency, not scene opacity.
        node('w14:alpha',rgb,**{'w14:val':round((1-opacity)*100000)})
    if layer.stroke:
        outline=node('w14:textOutline',properties,**{'w14:w':round(layer.stroke_width*12700),
            'w14:cap':'flat','w14:cmpd':'sng','w14:algn':'ctr'})
        color(node('w14:solidFill',outline),layer.stroke,layer.opacity*layer.stroke_opacity)
    if layer.text_gradient:
        gradient=node('w14:gradFill',node('w14:textFill',properties))
        stops=node('w14:gsLst',gradient)
        for index,value in enumerate(layer.text_gradient):
            position=layer.text_gradient_positions[index] if layer.text_gradient_positions else index/(len(layer.text_gradient)-1)
            color(node('w14:gs',stops,**{'w14:pos':round(position*100000)}),value,layer.opacity)
        node('w14:lin',gradient,**{'w14:ang':round((layer.text_gradient_angle%360)*60000),'w14:scaled':0})
    elif layer.opacity<1:
        color(node('w14:solidFill',node('w14:textFill',properties)),layer.color,layer.opacity)
    if layer.text_shadow:
        effect=layer.text_shadow
        shadow=node('w14:shadow',properties,**{'w14:blurRad':round(effect.blur*12700),
            'w14:dist':round(math.hypot(effect.dx,effect.dy)*12700),
            'w14:dir':round(math.degrees(math.atan2(effect.dy,effect.dx))%360*60000),
            'w14:sx':100000,'w14:sy':100000,'w14:kx':0,'w14:ky':0,'w14:algn':'ctr'})
        color(shadow,effect.color,effect.opacity*layer.opacity)


def rotated_textbox(paragraph,layer,z,identity,x,y):
    """Modern Word shapes rotate glyphs with their frame; VML does not."""
    drawing=node('w:drawing',node('w:r',paragraph))
    anchor=node('wp:anchor',drawing,distT=0,distB=0,distL=0,distR=0,simplePos=0,
                relativeHeight=word_z_order(z),behindDoc=0,locked=0,layoutInCell=0,allowOverlap=1)
    node('wp:simplePos',anchor,x=0,y=0)
    for direction,value in [('H',x),('V',y)]:
        position=node('wp:position'+direction,anchor,relativeFrom='page')
        node('wp:posOffset',position).text=str(round(value*12700))
    width=max(1,round(layer.width*12700));height=max(1,round(layer.height*12700))
    node('wp:extent',anchor,cx=width,cy=height)
    node('wp:effectExtent',anchor,l=0,t=0,r=0,b=0);node('wp:wrapNone',anchor)
    node('wp:docPr',anchor,id=identity,name='layer_'+layer.id,descr=layer.name)
    node('wp:cNvGraphicFramePr',anchor)
    graphic=node('a:graphic',anchor);data=node('a:graphicData',graphic,uri=NS['wps'])
    shape=node('wps:wsp',data)
    node('wps:cNvSpPr',shape,**({} if layer.text_fit=='shape' else {'txBox':1}))
    properties=node('wps:spPr',shape)
    transform=node('a:xfrm',properties,rot=round((layer.rotation%360)*60000))
    node('a:off',transform,x=0,y=0);node('a:ext',transform,cx=width,cy=height)
    node('a:avLst',node('a:prstGeom',properties,prst='rect'))
    node('a:noFill',properties);node('a:noFill',node('a:ln',properties))
    content=node('w:txbxContent',node('wps:txbx',shape))
    body=node('wps:bodyPr',shape,rot=0,vert='horz',wrap='none',lIns=0,tIns=0,rIns=0,bIns=0,
              anchor='t',anchorCtr=0,upright=0,vertOverflow='overflow',horzOverflow='overflow')
    if layer.text_fit=='shape':node('a:avLst',node('a:prstTxWarp',body,prst='textPlain'))
    node('a:noAutofit',body)
    return content


def export_docx(project,pages,output):
    if not pages or any(page.status=='pending' for page in pages):raise ValueError('所选页面尚未转换')
    if any(max(page.width,page.height)>1584 for page in pages):raise ValueError('Word 单页最大边长为22英寸，请先缩小页面')
    document=E.Element('{'+NS['w']+'}document',nsmap={k:v for k,v in NS.items() if k not in ('rel','ct')})
    document.set('{'+NS['mc']+'}Ignorable','w14');body=node('w:body',document)
    rels=node('rel:Relationships');node('rel:Relationship',rels,Id='styles',Type=NS['r']+'/styles',Target='styles.xml')
    node('rel:Relationship',rels,Id='settings',Type=NS['r']+'/settings',Target='settings.xml')
    media={};shape_identity=0;wordart_defined=False
    for number,page in enumerate(pages):
        anchor=node('w:p',body);pp=node('w:pPr',anchor)
        node('w:spacing',pp,**{'w:before':0,'w:after':0,'w:line':1,'w:lineRule':'exact'})
        for z,layer in enumerate(sorted(page.layers,key=lambda value:value.z)):
            if not layer.visible:continue
            layout=layer.text_layout.docx if layer.text_layout else None
            shape_id='layer_'+layer.id
            # VML rotates around the centre; scenes rotate around the top left.
            angle=math.radians(layer.rotation)
            x=layer.x+(math.cos(angle)*layer.width-math.sin(angle)*layer.height-layer.width)/2
            y=layer.y+(math.sin(angle)*layer.width+math.cos(angle)*layer.height-layer.height)/2
            if layout:
                dx,dy=layout.offset
                x+=math.cos(angle)*dx-math.sin(angle)*dy
                y+=math.sin(angle)*dx+math.cos(angle)*dy
            style=f'position:absolute;margin-left:{x:.4f}pt;margin-top:{y:.4f}pt;width:{layer.width:.4f}pt;height:{layer.height:.4f}pt;z-index:{word_z_order(z)};mso-position-horizontal-relative:page;mso-position-vertical-relative:page;rotation:{layer.rotation:.4f}'
            shape=None
            as_wordart=native_wordart(layer)
            if as_wordart:
                shape=whole_wordart(anchor,layer,style,not wordart_defined);wordart_defined=True
            elif layer.kind=='text' and (abs(layer.rotation%360)>.001 or layer.text_fit=='shape'):
                shape_identity+=1
                content=rotated_textbox(anchor,layer,z,shape_identity,x,y)
            else:
                picture=node('w:pict',node('w:r',anchor))
                shape=node('v:shape',picture,id=shape_id,style=style,coordsize=f'{max(1,round(layer.width*1000))},{max(1,round(layer.height*1000))}',stroked='f',filled='f',**{'o:allowincell':'f','o:allowoverlap':'t','alt':layer.name})
            if as_wordart:pass
            elif layer.kind=='text':
                if shape is not None:
                    shape.set('type','#_x0000_t202')
                    textbox=node('v:textbox',shape,inset='0,0,0,0',style='mso-fit-shape-to-text:f')
                    content=node('w:txbxContent',textbox)
                for line in layer.text.split('\n'):
                    paragraph=node('w:p',content);prop=node('w:pPr',paragraph)
                    node('w:spacing',prop,**{'w:before':0,'w:after':0,'w:line':round(layer.font_size*24),'w:lineRule':'exact'})
                    if layer.font_asset:
                        from .font_assets import metadata
                        inset=metadata(project,layer.font_asset,layer.font).get('word_padding_em',.05)
                        prop.find('{'+NS['w']+'}spacing').set('{'+NS['w']+'}before',str(round(layer.font_size*inset*20)))
                    node('w:contextualSpacing',prop,**{'w:val':0})
                    if layout:
                        node('w:autoSpaceDE',prop,**{'w:val':0})
                        node('w:autoSpaceDN',prop,**{'w:val':0})
                    for character_index,piece in enumerate(list(line) if layout else [line]):
                        run=node('w:r',paragraph);rp=node('w:rPr',run)
                        node('w:rFonts',rp,**{'w:ascii':layer.font,'w:hAnsi':layer.font,'w:eastAsia':layer.font,'w:cs':layer.font})
                        node('w:color',rp,**{'w:val':layer.color[1:]})
                        for tag in ('w:sz','w:szCs'):node(tag,rp,**{'w:val':max(1,round(layer.font_size*2))})
                        if layer.bold:node('w:b',rp);node('w:bCs',rp)
                        if layer.italic:node('w:i',rp);node('w:iCs',rp)
                        spacing=layout.spacing[character_index] if layout else layer.char_spacing
                        if spacing:node('w:spacing',rp,**{'w:val':round(spacing*20)})
                        if layer.font_asset and layer.text_fit=='shape':
                            # Word textPlain fits height but leaves the embedded
                            # font's original width unless the whole run is fitted.
                            node('w:fitText',rp,**{'w:val':max(1,round(layer.width*20)),'w:id':shape_identity})
                        text_effects(rp,layer)
                        text=node('w:t',run);text.set('{http://www.w3.org/XML/1998/namespace}space','preserve');text.text=piece
            elif layer.kind=='image':
                identity='image'+str(len(media)+1);target=f'media/{identity}.png'
                image=Image.open(asset_path(project,layer.asset)).convert('RGBA')
                if layer.opacity<1:image.putalpha(image.getchannel('A').point(lambda a:round(a*layer.opacity)))
                media['word/'+target]=png_bytes(image,(layer.width,layer.height))
                node('rel:Relationship',rels,Id=identity,Type=NS['r']+'/image',Target=target)
                shape.set('type','#_x0000_t75');node('v:imagedata',shape,**{'r:id':identity,'o:title':layer.name})
            else:
                commands=[]
                for command in layer.path:
                    op={'M':'m','L':'l','C':'c','Z':'x'}[command.op]
                    commands.append(op+' '+','.join(str(round(point*1000)) for point in command.points))
                shape.set('path',' '.join(commands)+' e')
                if layer.fill:
                    shape.set('filled','t');shape.set('fillcolor',layer.fill)
                    node('v:fill',shape,opacity=str(layer.fill_opacity*layer.opacity))
                if layer.stroke:
                    shape.set('stroked','t');shape.set('strokecolor',layer.stroke);shape.set('strokeweight',f'{layer.stroke_width}pt')
                    node('v:stroke',shape,opacity=str(layer.stroke_opacity*layer.opacity))
            if shape is not None:node('w10:wrap',shape,type='none')
        section=node('w:sectPr',body if number==len(pages)-1 else pp)
        node('w:type',section,**{'w:val':'nextPage'})
        node('w:pgSz',section,**{'w:w':round(page.width*20),'w:h':round(page.height*20)})
        node('w:pgMar',section,**{'w:top':0,'w:right':0,'w:bottom':0,'w:left':0,'w:header':0,'w:footer':0,'w:gutter':0})
    content_types=node('ct:Types')
    for extension,mime in [('rels','application/vnd.openxmlformats-package.relationships+xml'),('xml','application/xml'),('png','image/png')]:node('ct:Default',content_types,Extension=extension,ContentType=mime)
    node('ct:Override',content_types,PartName='/word/document.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml')
    node('ct:Override',content_types,PartName='/word/styles.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml')
    node('ct:Override',content_types,PartName='/word/settings.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml')
    package_rels=node('rel:Relationships');node('rel:Relationship',package_rels,Id='document',Type=NS['r']+'/officeDocument',Target='word/document.xml')
    styles=node('w:styles');normal=node('w:style',styles,**{'w:type':'paragraph','w:default':1,'w:styleId':'Normal'});node('w:name',normal,**{'w:val':'Normal'})
    settings=node('w:settings');compat=node('w:compat',settings)
    node('w:compatSetting',compat,**{'w:name':'compatibilityMode','w:uri':'http://schemas.microsoft.com/office/word','w:val':15})
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in {'[Content_Types].xml':xml(content_types),'_rels/.rels':xml(package_rels),'word/document.xml':xml(document),'word/styles.xml':xml(styles),'word/settings.xml':xml(settings),'word/_rels/document.xml.rels':xml(rels),**media}.items():archive.writestr(name,value)
    from .font_assets import embed
    embed(project,pages,output,'docx')
    return output
