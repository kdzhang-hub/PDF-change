"""Compare native effect XML before and after real Word font/text edits."""
import argparse,json,zipfile
from pathlib import Path
from collections import Counter
from lxml import etree as E

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'v':'urn:schemas-microsoft-com:vml',
    'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'mc':'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'w14':'http://schemas.microsoft.com/office/word/2010/wordml'}


def effects(path):
    with zipfile.ZipFile(path) as z:document=E.fromstring(z.read('word/document.xml'))
    result={}
    for key in ('textFill','textOutline','shadow'):
        result[key]=Counter()
        for element in document.xpath('.//w14:'+key,namespaces=NS):
            # Word can reorder XML attributes and rewrite namespace prefixes.
            def value(node):return [node.tag,sorted(node.attrib.items()),[value(child) for child in node]]
            result[key][json.dumps(value(element),sort_keys=True)]+=1
    return result


def canonical(node):
    if node is None:return None
    tag=E.QName(node).localname
    attrs={E.QName(k).localname:v for k,v in node.attrib.items()}
    children=[]
    for child in node:
        name=E.QName(child).localname
        # Word writes explicit default joins/dashes and omits opaque alpha.
        if name=='alpha' and child.get('{'+NS['w14']+'}val')=='0':continue
        if tag=='textOutline' and (name=='bevel' or (name=='prstDash' and child.get('{'+NS['w14']+'}val')=='solid')):continue
        children.append(canonical(child))
    return {'tag':tag,'attrs':attrs,'children':children}


def equivalent(before,after):
    if before is None or after is None:return before==after
    if before['tag']!=after['tag'] or before['attrs'].keys()!=after['attrs'].keys():return False
    for key,value in before['attrs'].items():
        actual=after['attrs'][key]
        # Word quantizes EMU lengths on save. 12 EMU is below .001 pt.
        if before['tag'] in ('shadow','textOutline') and key in ('w','blurRad','dist'):
            if abs(int(value)-int(actual))>12:return False
        elif value!=actual:return False
    return len(before['children'])==len(after['children']) and all(equivalent(a,b) for a,b in zip(before['children'],after['children']))


def shape_effects(path):
    with zipfile.ZipFile(path) as z:document=E.fromstring(z.read('word/document.xml'))
    result={}
    # Word writes a legacy fallback copy for modern shapes. The actual Word
    # runtime uses the Choice branch; do not count both as separate objects.
    for shape in document.xpath('.//v:shape[.//w:txbxContent and not(ancestor::mc:Fallback)]|.//wp:anchor[.//w:txbxContent and not(ancestor::mc:Fallback)]',namespaces=NS):
        identity=shape.get('id') or shape.find('wp:docPr',NS).get('name')
        if identity in result:raise ValueError('Duplicate text shape identity')
        combinations=[]
        for run in shape.xpath('.//w:txbxContent//w:r[w:t]',namespaces=NS):
            rp=run.find('w:rPr',NS)
            if rp is None:raise ValueError('Text run has no explicit properties')
            fill=rp.find('w14:textFill',NS)
            if fill is None:
                clr=rp.find('w:color',NS)
                value=clr.get('{'+NS['w']+'}val','AUTO').upper() if clr is not None else 'AUTO'
                fill=E.Element('{'+NS['w14']+'}textFill')
                solid=E.SubElement(fill,'{'+NS['w14']+'}solidFill')
                E.SubElement(solid,'{'+NS['w14']+'}srgbClr',{'{'+NS['w14']+'}val':value})
            # Wrap the three effects in an owner-bound signature. Splitting a
            # uniform run is allowed; moving an effect to another object is not.
            item={'tag':'effects','attrs':{},'children':[canonical(fill),
                canonical(rp.find('w14:textOutline',NS)),canonical(rp.find('w14:shadow',NS))]}
            if not any(equivalent(item,old) for old in combinations):combinations.append(item)
        result[identity]=combinations
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
    before=effects(args.folder/'converted.docx');after=effects(args.folder/'word-font-edit-check.docx')
    original=shape_effects(args.folder/'converted.docx');edited=shape_effects(args.folder/'word-font-edit-check.docx')
    if not original:raise SystemExit('No native text objects found for roundtrip verification')
    mismatches=[]
    for identity in original.keys()|edited.keys():
        a=original.get(identity,[]);b=edited.get(identity,[])
        if not a or not b or not all(any(equivalent(x,y) for y in b) for x in a) or not all(any(equivalent(y,x) for x in a) for y in b):mismatches.append(identity)
    result={'before':{key:sum(values.values()) for key,values in before.items()},
        'after':{key:sum(values.values()) for key,values in after.items()},
        'rawXmlIdentical':before==after,'objectsChecked':len(original),'effectsPreserved':not mismatches,
        'mismatches':mismatches,'normalization':'Opaque alpha and outline defaults; length differences at most 12 EMU (.001 pt); uniform run splitting allowed'}
    (args.folder/'word-effects-roundtrip.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    if mismatches:raise SystemExit('Word changed native text effect semantics; inspect mismatched objects')
