import zipfile
from pathlib import Path
import pytest
from lxml import etree as E
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from backend import store,font_assets
from backend.models import FontAssetRef,LayerElement,PageScene
from backend.export import export_pptx
from backend.export_docx import export_docx


@pytest.fixture
def font_case(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('font-fixture')
    family='TestRecovered';builder=FontBuilder(1000,isTTF=True);names=['.notdef','space','A','B'];glyphs={}
    for name in names:
        pen=TTGlyphPen(None)
        if name in ('A','B'):
            pen.moveTo((0,0));pen.lineTo((300,700));pen.lineTo((600,0));pen.closePath()
        glyphs[name]=pen.glyph()
    builder.setupGlyphOrder(names);builder.setupCharacterMap({32:'space',65:'A',66:'B'});builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({n:(600,0) for n in names});builder.setupHorizontalHeader(ascent=800,descent=-200)
    builder.setupNameTable({'familyName':family,'styleName':'Regular','fullName':family,'psName':family,'uniqueFontIdentifier':family})
    builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200,fsType=0);builder.setupPost();builder.setupMaxp()
    ttf=tmp_path/'own.ttf';builder.save(ttf)
    ppt=tmp_path/'native.pptx';word=tmp_path/'native.docx'
    with zipfile.ZipFile(ppt,'w') as z:
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{font_assets.P}" xmlns:r="{font_assets.R}"><p:embeddedFontLst><p:embeddedFont><p:font typeface="{family}" charset="0"/><p:regular r:id="font"/></p:embeddedFont></p:embeddedFontLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="{font_assets.REL}"><Relationship Id="font" Target="fonts/font.fntdata"/></Relationships>')
        z.writestr('[Content_Types].xml',f'<Types xmlns="{font_assets.CT}"><Default Extension="fntdata" ContentType="application/x-fontdata"/></Types>')
        z.writestr('ppt/fonts/font.fntdata',b'test-container-not-an-office-render-proof')
    with zipfile.ZipFile(word,'w') as z:
        z.writestr('word/fontTable.xml',f'<w:fonts xmlns:w="{font_assets.W}" xmlns:r="{font_assets.R}"><w:font w:name="{family}"><w:embedRegular r:id="font" w:fontKey="{{11111111-1111-1111-1111-111111111111}}"/></w:font></w:fonts>')
        z.writestr('word/_rels/fontTable.xml.rels',f'<Relationships xmlns="{font_assets.REL}"><Relationship Id="font" Target="fonts/font.odttf"/></Relationships>')
        z.writestr('word/fonts/font.odttf',b'test-word-container-not-an-office-render-proof')
    family,ref=font_assets.import_verified(project,ttf,ppt,word,'自制字体测试')
    layer=LayerElement(kind='text',name='one word',text='AB',font=family,font_asset=ref,x=20,y=20,width=200,height=150,font_size=100)
    page=PageScene(index=0,width=400,height=300,original='none.png',status='needs_review',layers=[layer])
    return project,page,ref


def test_recovered_font_rejects_wrong_kind_and_unsupported_characters():
    with pytest.raises(ValueError):FontAssetRef(file='../font.ttf',characters='AB')
    ref=FontAssetRef(file='font.ttf',characters='AB')
    for updates in ({'kind':'image','text':'AB'},{'kind':'text','text':'AC'}):
        with pytest.raises(ValueError):LayerElement(name='bad',x=0,y=0,width=20,height=20,font_asset=ref,**updates)


def test_both_exports_embed_project_font_once_without_flattening_text(font_case,tmp_path):
    project,page,ref=font_case
    second=page.layers[0].model_copy(deep=True);second.id='second';second.text='BA';page.layers.append(second)
    before=page.model_dump()
    for fmt,builder in [('pptx',export_pptx),('docx',export_docx)]:
        path=tmp_path/('result.'+fmt);builder(project,[page],path)
        with zipfile.ZipFile(path) as z:
            assert len([n for n in z.namelist() if '/fonts/' in n])==1
            if fmt=='pptx':
                root=E.fromstring(z.read('ppt/presentation.xml'));assert len(root.findall(f'.//{{{font_assets.P}}}embeddedFont'))==1
                assert root.get('embedTrueTypeFonts')=='1'
                xml=E.fromstring(z.read('ppt/slides/slide1.xml'));assert xml.xpath('//*[local-name()="t"]/text()')==['AB','BA']
            else:
                root=E.fromstring(z.read('word/fontTable.xml'));assert root[0].get(f'{{{font_assets.W}}}name')=='TestRecovered'
                assert E.fromstring(z.read('word/settings.xml')).find(f'{{{font_assets.W}}}embedTrueTypeFonts') is not None
                xml=E.fromstring(z.read('word/document.xml'));ns={'w':font_assets.W}
                assert xml.xpath('//w:t/text()',namespaces=ns)==['AB','BA']
                assert all(n.get(f'{{{font_assets.W}}}before')=='100' for n in xml.findall('.//w:txbxContent/w:p/w:pPr/w:spacing',ns))
    assert page.model_dump()==before


def test_recovered_font_shape_uses_modern_text_not_wordart_fallback(font_case,tmp_path):
    project,page,_=font_case;page.layers[0].text_fit='shape'
    path=tmp_path/'recovered.docx';export_docx(project,[page],path)
    with zipfile.ZipFile(path) as z:
        xml=E.fromstring(z.read('word/document.xml'))
        assert not xml.xpath('//*[local-name()="textpath"]')
        assert xml.xpath('//*[local-name()="prstTxWarp"]/@prst')==['textPlain']
        assert xml.xpath('//*[local-name()="t"]/text()')==['AB']
        assert xml.xpath('//*[local-name()="fitText"]/@*[local-name()="val"]')==['4000']
        assert xml.xpath('//*[local-name()="fitText"]/@*[local-name()="id"]')==['1']


@pytest.mark.parametrize('failure',['family','characters','ttf','container'])
def test_mismatched_or_damaged_font_stops_export_without_changing_scene(font_case,tmp_path,failure):
    project,page,ref=font_case
    if failure=='family':page.layers[0].font='OtherFace'
    elif failure=='characters':ref.characters+='C'
    elif failure=='ttf':store.asset_path(project,ref.file).write_bytes(b'damaged')
    else:
        info=font_assets.metadata(project,ref,page.layers[0].font)
        store.asset_path(project,info['formats']['pptx']['file']).write_bytes(b'damaged')
    before=page.model_dump()
    with pytest.raises(ValueError):export_pptx(project,[page],tmp_path/'bad.pptx')
    assert page.model_dump()==before


def test_hidden_unused_font_is_not_embedded_or_required(font_case,tmp_path):
    project,page,ref=font_case;page.layers[0].visible=False;store.asset_path(project,ref.file).unlink()
    export_pptx(project,[page],tmp_path/'hidden.pptx')
    with zipfile.ZipFile(tmp_path/'hidden.pptx') as z:assert not [n for n in z.namelist() if '/fonts/' in n]


def test_conflicting_same_family_fonts_do_not_silently_replace_each_other(font_case,tmp_path):
    from fontTools.ttLib import TTFont
    project,page,ref=font_case
    with TTFont(store.asset_path(project,ref.file)) as font:
        font['name'].setName('Different resource revision',5,3,1,0x409)
        font.save(tmp_path/'other.ttf')
    family,other=font_assets.import_verified(project,tmp_path/'other.ttf',tmp_path/'native.pptx',tmp_path/'native.docx')
    layer=page.layers[0].model_copy(deep=True);layer.id='other';layer.font_asset=other;page.layers.append(layer)
    with pytest.raises(ValueError,match='冲突'):export_pptx(project,[page],tmp_path/'collision.pptx')


@pytest.mark.parametrize('permanent',[False,True])
def test_windows_font_package_replace_is_bounded_and_never_returns_unembedded_file(font_case,tmp_path,monkeypatch,permanent):
    project,page,_=font_case;original=Path.replace;calls=[]
    def replace(path,target):
        if path.name.endswith('.fonts-building'):
            calls.append(path)
            if permanent or len(calls)<3:
                error=PermissionError('simulated Windows sharing lock');error.winerror=32;raise error
        return original(path,target)
    monkeypatch.setattr(Path,'replace',replace);monkeypatch.setattr(font_assets.time,'sleep',lambda delay:None)
    path=tmp_path/'atomic.pptx'
    if permanent:
        with pytest.raises(PermissionError):export_pptx(project,[page],path)
        assert len(calls)==5 and path.with_name(path.name+'.fonts-building').exists()
    else:
        export_pptx(project,[page],path)
        # Two injected locks are guaranteed; Windows can add a real transient
        # sharing lock. Success must remain within the production retry bound.
        assert 3<=len(calls)<=5
        with zipfile.ZipFile(path) as archive:assert any('/fonts/' in name for name in archive.namelist())

