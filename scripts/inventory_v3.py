from pathlib import Path
import json,zipfile,hashlib,re,shutil
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'/'v3-movement-20261028';OUT.mkdir(parents=True,exist_ok=True)
SOURCES={'ordinary':Path('D:/桌面项目/职规赛/参赛材料/v3.pptx'),'image':Path('D:/桌面项目/职规赛/参赛材料/v3 图片版.pptx')}
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
result={}
for key,path in SOURCES.items():
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    copy=OUT/f'{key}-source.pptx'
    if copy.exists():assert hashlib.sha256(copy.read_bytes()).hexdigest()==digest
    else:shutil.copy2(path,copy)
    with zipfile.ZipFile(path) as z:
        deck=etree.fromstring(z.read('ppt/presentation.xml'));size=deck.find('p:sldSz',NS)
        names=sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)),key=lambda n:int(re.search(r'slide(\d+)',n).group(1)))
        pages=[]
        for index,name in enumerate(names):
            doc=etree.fromstring(z.read(name));tree=doc.find('p:cSld/p:spTree',NS);shapes=[]
            for shape in tree:
                kind=etree.QName(shape).localname
                if kind not in ('sp','pic','grpSp','graphicFrame','cxnSp'):continue
                identity=shape.find('.//p:cNvPr',NS);texts=shape.xpath('.//a:t/text()',namespaces=NS)
                transform=shape.find('p:spPr/a:xfrm',NS)
                if transform is None:transform=shape.find('p:grpSpPr/a:xfrm',NS)
                box=None
                if transform is not None:
                    offset=transform.find('a:off',NS);extent=transform.find('a:ext',NS)
                    if offset is not None and extent is not None:box=[int(offset.get('x'))/12700,int(offset.get('y'))/12700,int(extent.get('cx'))/12700,int(extent.get('cy'))/12700]
                shapes.append({'id':int(identity.get('id')) if identity is not None else None,'name':identity.get('name') if identity is not None else '',
                    'kind':kind,'text':'\n'.join(texts),'box':box,'children':len(shape.xpath('.//p:pic|.//p:sp',namespaces=NS)) if kind=='grpSp' else 0})
            pages.append({'page':index+1,'top_shapes':len(shapes),'pictures':len(doc.xpath('//p:pic',namespaces=NS)),'native_text_objects':len(doc.xpath('//p:sp[p:txBody/a:p/a:r/a:t]',namespaces=NS)),
                'text':'\n'.join(doc.xpath('//a:t/text()',namespaces=NS)),'shapes':shapes})
    result[key]={'source':str(path),'sha256':digest,'bytes':path.stat().st_size,'size_pt':[int(size.get('cx'))/12700,int(size.get('cy'))/12700],
        'pages':pages,'total_native_text_objects':sum(p['native_text_objects'] for p in pages),'total_pictures':sum(p['pictures'] for p in pages)}
(OUT/'input-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
for key,info in result.items():print(json.dumps({'kind':key,'pages':len(info['pages']),'size':info['size_pt'],'native_text':info['total_native_text_objects'],'pictures':info['total_pictures'],'top_shapes_first_pages':[x['top_shapes'] for x in info['pages'][:5]]},ensure_ascii=True))
