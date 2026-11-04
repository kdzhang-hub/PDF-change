"""Project-owned Unicode fonts and verified, portable Office font resources."""
import hashlib,io,json,posixpath,time,zipfile
from pathlib import Path
from lxml import etree as E
from . import store
from .models import FontAssetRef

P='http://schemas.openxmlformats.org/presentationml/2006/main'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'

def digest(data):return hashlib.sha256(data).hexdigest()

def font_identity(data):
    try:
        from fontTools.ttLib import TTFont
        with TTFont(io.BytesIO(data),lazy=False) as font:
            if font['OS/2'].fsType:raise ValueError('还原字体必须允许编辑嵌入')
            return font['name'].getDebugName(1),''.join(chr(c) for c in sorted(font.getBestCmap()))
    except (ImportError,KeyError,OSError) as exc:raise ValueError('本地字体校验环境或文件不完整，不会使用云端') from exc

def metadata(project,ref,family):
    path=store.asset_path(project,ref.file);meta_path=path.with_suffix('.font.json')
    if not path.is_file() or not meta_path.is_file():raise ValueError('还原字体资源缺失，请恢复原项目或替换字体')
    raw=path.read_bytes();meta=json.loads(meta_path.read_text('utf-8'))
    if digest(raw)!=meta.get('sha256') or family!=meta.get('family'):raise ValueError('还原字体已改变或字体名称不匹配')
    actual,characters=font_identity(raw)
    if actual!=family or set(characters)!=set(ref.characters) or characters!=meta.get('characters'):raise ValueError('还原字体字符映射不匹配')
    return meta

def import_verified(project,ttf,pptx,docx,label='还原艺术字'):
    """Import font packages produced and tested locally; never read a reference deck."""
    raw=Path(ttf).read_bytes();family,characters=font_identity(raw);stem='font-'+digest(raw)[:20]
    font_file=stem+'.ttf';records={}
    with zipfile.ZipFile(pptx) as archive:
        xml=E.fromstring(archive.read('ppt/presentation.xml'));rels=E.fromstring(archive.read('ppt/_rels/presentation.xml.rels'))
        entry=next((entry for entry in xml.findall(f'{{{P}}}embeddedFontLst/{{{P}}}embeddedFont') if entry.find(f'{{{P}}}font').get('typeface')==family),None)
        if entry is None:raise ValueError('PPTX 中未找到该还原字体的嵌入数据')
        identity=entry.find(f'{{{P}}}regular').get(f'{{{R}}}id');rel=next(r for r in rels if r.get('Id')==identity)
        part=posixpath.normpath(posixpath.join('ppt',rel.get('Target')));data=archive.read(part)
        font_info=dict(entry.find(f'{{{P}}}font').attrib)
        content=E.fromstring(archive.read('[Content_Types].xml'))
        mime=next((n.get('ContentType') for n in content if n.get('Extension')=='fntdata'),None)
        if not mime:mime=next(n.get('ContentType') for n in content if n.get('PartName')=='/'+part)
        filename=stem+'-ppt.fntdata';records['pptx']={'file':filename,'sha256':digest(data),'font':font_info,'content_type':mime}
        ppt_data=data
    with zipfile.ZipFile(docx) as archive:
        xml=E.fromstring(archive.read('word/fontTable.xml'));rels=E.fromstring(archive.read('word/_rels/fontTable.xml.rels'))
        entry=next((entry for entry in xml if entry.get(f'{{{W}}}name')==family),None)
        if entry is None:raise ValueError('DOCX 中未找到该还原字体的嵌入数据')
        embedded=entry.find(f'{{{W}}}embedRegular');identity=embedded.get(f'{{{R}}}id');rel=next(r for r in rels if r.get('Id')==identity)
        part=posixpath.normpath(posixpath.join('word',rel.get('Target')));data=archive.read(part)
        filename=stem+'-word.odttf';records['docx']={'file':filename,'sha256':digest(data),'entry':E.tostring(entry).decode('utf-8')};word_data=data
    for filename,data in [(font_file,raw),(records['pptx']['file'],ppt_data),(records['docx']['file'],word_data)]:
        store.asset_path(project,filename).write_bytes(data)
    meta={'family':family,'characters':characters,'sha256':digest(raw),'word_padding_em':.05,'formats':records}
    store.asset_path(project,stem+'.font.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf-8')
    return family,FontAssetRef(file=font_file,characters=characters,label=label)

def resources(project,pages,format):
    result={}
    for page in pages:
        for layer in page.layers:
            if not layer.visible or not layer.font_asset:continue
            ref=layer.font_asset;meta=metadata(project,ref,layer.font);item=meta['formats'].get(format)
            if item is None:raise ValueError('该还原字体缺少所选格式的嵌入资源，请重新恢复')
            data=store.asset_path(project,item['file']).read_bytes()
            if len(data)>8_000_000 or digest(data)!=item.get('sha256'):raise ValueError('还原字体嵌入数据不完整，导出已停止')
            if layer.font in result and result[layer.font][0]['sha256']!=meta['sha256']:raise ValueError('同名字体资源冲突，请重新恢复')
            result[layer.font]=(meta,item,data)
    return result

def replace_package(temporary,path):
    # Windows may briefly deny replacement just after a ZIP is closed. Retry
    # only those sharing/access errors; never delete the original to force it.
    for attempt,delay in enumerate((0,.05,.1,.2,.4)):
        if delay:time.sleep(delay)
        try:temporary.replace(path);return
        except PermissionError as exc:
            if getattr(exc,'winerror',None) not in (5,32,33) or attempt==4:raise

def embed(project,pages,path,format):
    fonts=resources(project,pages,format)
    if not fonts:return
    path=Path(path)
    with zipfile.ZipFile(path) as archive:files={name:archive.read(name) for name in archive.namelist()}
    content=E.fromstring(files['[Content_Types].xml'])
    if format=='pptx':
        document=E.fromstring(files['ppt/presentation.xml']);rels_path='ppt/_rels/presentation.xml.rels';rels=E.fromstring(files[rels_path])
        document.set('embedTrueTypeFonts','1')
        listing=document.find(f'{{{P}}}embeddedFontLst')
        if listing is None:
            listing=E.Element(f'{{{P}}}embeddedFontLst');later={f'{{{P}}}'+n for n in ('custShowLst','photoAlbum','custDataLst','kinsoku','defaultTextStyle','modifyVerifier','extLst')}
            at=next((i for i,n in enumerate(document) if n.tag in later),len(document));document.insert(at,listing)
    else:
        settings=E.fromstring(files['word/settings.xml'])
        if settings.find(f'{{{W}}}embedTrueTypeFonts') is None:
            # This flag precedes saveSubsetFonts and the other normal settings.
            early={f'{{{W}}}'+n for n in ('writeProtection','view','zoom','removePersonalInformation','removeDateAndTime','doNotDisplayPageBoundaries','displayBackgroundShape','printPostScriptOverText','printFractionalCharacterWidth','printFormsData')}
            at=next((i for i,n in enumerate(settings) if n.tag not in early),len(settings))
            settings.insert(at,E.Element(f'{{{W}}}embedTrueTypeFonts'))
        files['word/settings.xml']=E.tostring(settings)
        document=E.fromstring(files.get('word/fontTable.xml',f'<w:fonts xmlns:w="{W}" xmlns:r="{R}"/>'.encode()))
        rels_path='word/_rels/fontTable.xml.rels';rels=E.fromstring(files.get(rels_path,f'<Relationships xmlns="{REL}"/>'.encode()))
        root_rels=E.fromstring(files['word/_rels/document.xml.rels'])
        if not any(r.get('Type')==R+'/fontTable' for r in root_rels):
            identity='recoveredFontTable'
            while any(r.get('Id')==identity for r in root_rels):identity+='x'
            E.SubElement(root_rels,f'{{{REL}}}Relationship',Id=identity,Type=R+'/fontTable',Target='fontTable.xml')
        files['word/_rels/document.xml.rels']=E.tostring(root_rels)
        if not any(n.get('PartName')=='/word/fontTable.xml' for n in content):E.SubElement(content,f'{{{CT}}}Override',PartName='/word/fontTable.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml')
    for index,(family,(meta,item,data)) in enumerate(fonts.items()):
        identity='recoveredFont'+str(index)
        while any(r.get('Id')==identity for r in rels):identity+='x'
        suffix='fntdata' if format=='pptx' else 'odttf';name='layerdeck-'+str(index)+'.'+suffix
        while (('ppt/' if format=='pptx' else 'word/')+'fonts/'+name) in files:name='x'+name
        E.SubElement(rels,f'{{{REL}}}Relationship',Id=identity,Type=R+'/font',Target='fonts/'+name)
        if format=='pptx':
            entry=E.SubElement(listing,f'{{{P}}}embeddedFont');E.SubElement(entry,f'{{{P}}}font',**item['font']);E.SubElement(entry,f'{{{P}}}regular').set(f'{{{R}}}id',identity)
        else:
            entry=E.fromstring(item['entry'].encode(),parser=E.XMLParser(resolve_entities=False,no_network=True))
            if entry.tag!=f'{{{W}}}font' or entry.get(f'{{{W}}}name')!=family:raise ValueError('还原字体表名称不匹配')
            entry.find(f'{{{W}}}embedRegular').set(f'{{{R}}}id',identity);document.append(entry)
        mime=item['content_type'] if format=='pptx' else 'application/vnd.openxmlformats-officedocument.obfuscatedFont'
        if not any(n.get('Extension')==suffix for n in content):E.SubElement(content,f'{{{CT}}}Default',Extension=suffix,ContentType=mime)
        files[('ppt/' if format=='pptx' else 'word/')+'fonts/'+name]=data
    files['ppt/presentation.xml' if format=='pptx' else 'word/fontTable.xml']=E.tostring(document)
    files[rels_path]=E.tostring(rels);files['[Content_Types].xml']=E.tostring(content)
    temporary=path.with_name(path.name+'.fonts-building')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    replace_package(temporary,path)
