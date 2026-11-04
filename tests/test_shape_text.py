import zipfile
from lxml import etree as E
import pytest
from backend.models import LayerElement,PageScene,TextShadow
from backend.export import export_pptx
from backend.export_docx import export_docx
from backend.font_calibration import eligible
from backend.word_calibration import target
from backend import store


def text(**updates):
    values=dict(kind='text',name='fitted text',text='ART',font='Arial',font_size=60,
        x=20,y=30,width=180,height=40,text_fit='shape');values.update(updates)
    return LayerElement(**values)


@pytest.mark.parametrize('updates',[{'kind':'image'},{'kind':'path'},{'text':'two\nlines'},{'text':'two\rlines'}])
def test_shape_fit_rejects_nontext_and_multiline(updates):
    with pytest.raises(ValueError,match='单行文字'):text(**updates)


def test_fixed_glyph_geometry_is_excluded_from_natural_calibration():
    fitted=text(source='pdf-text-group',source_ink_bbox=[20,30,200,70])
    assert not eligible(fitted) and not target(fitted)
    fitted.text_fit='natural'
    assert eligible(fitted) and target(fitted)


@pytest.mark.parametrize('mode',['natural','shape'])
@pytest.mark.parametrize('rotation',[0,24])
def test_both_formats_keep_native_text_styles_and_explicit_fit_policy(tmp_path,monkeypatch,mode,rotation):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('shape-text')
    layer=text(text_fit=mode,rotation=rotation,text_gradient=['#fff6c0','#edac22'],stroke='#11aacc',stroke_width=.4,
        opacity=.7,text_shadow=TextShadow(dx=2,dy=3,opacity=.4))
    page=PageScene(index=0,width=400,height=200,original='unused.png',status='needs_review',layers=[layer]);before=page.model_dump()
    for format,builder,path in [('pptx',export_pptx,'ppt/slides/slide1.xml'),('docx',export_docx,'word/document.xml')]:
        output=tmp_path/(mode+str(rotation)+'.'+format);builder(project,[page],output)
        with zipfile.ZipFile(output) as archive:
            xml=E.fromstring(archive.read(path));ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            assert xml.xpath('//a:t/text()|//w:t/text()',namespaces=ns)==['ART']
            warp=xml.xpath('//a:prstTxWarp',namespaces=ns)
            assert bool(warp)==(mode=='shape')
            if warp:assert warp[0].get('prst')=='textPlain'
            assert b'edac22' in E.tostring(xml).lower() and b'11aacc' in E.tostring(xml).lower()
            assert layer.id.encode() in E.tostring(xml)
            assert not [n for n in archive.namelist() if '/media/' in n]
            if format=='docx' and mode=='shape':
                assert len(xml.xpath('//a:noAutofit',namespaces=ns))==1
                assert not xml.xpath('//a:spAutoFit',namespaces=ns)
    assert page.model_dump()==before


@pytest.mark.parametrize('rotation',[0,24])
@pytest.mark.parametrize('value',['ART','代码'])
def test_plain_fitted_word_is_one_native_wordart_with_full_editable_string(tmp_path,monkeypatch,rotation,value):
    from backend.export_docx import native_wordart
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('native-wordart')
    layer=text(text=value,rotation=rotation,width=450,height=125,font_size=100,color='#445566',
        bold=True,italic=True,opacity=.7,stroke='#11aacc',stroke_width=.4,stroke_opacity=.6)
    page=PageScene(index=0,width=600,height=350,original='unused.png',status='needs_review',layers=[layer]);before=page.model_dump()
    assert native_wordart(layer)
    output=tmp_path/'native.docx';export_docx(project,[page],output)
    with zipfile.ZipFile(output) as archive:
        root=E.fromstring(archive.read('word/document.xml'));ns={'v':'urn:schemas-microsoft-com:vml','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        shapes=root.xpath('//v:shape',namespaces=ns);assert len(shapes)==1
        shape=shapes[0];assert shape.get('id')=='layer_'+layer.id
        assert shape.get('type')=='#_x0000_t136' and shape.get('fillcolor')=='#445566'
        assert shape.get('strokecolor')=='#11aacc'
        word=shape.find('v:textpath',ns);assert word.get('string')==value
        assert 'font-size:100' in word.get('style') and 'font-weight:bold' in word.get('style') and 'font-style:italic' in word.get('style')
        assert float(shape.find('v:fill',ns).get('opacity'))==.7
        assert float(shape.find('v:stroke',ns).get('opacity'))==pytest.approx(.42)
        assert not root.xpath('//w:txbxContent',namespaces=ns)
        template=root.find('.//v:shapetype',ns)
        assert template.find('v:path',ns).get('{urn:schemas-microsoft-com:office:office}connecttype')=='custom'
        assert template.find('{urn:schemas-microsoft-com:office:office}lock') is not None
        assert not [name for name in archive.namelist() if '/media/' in name]
    assert page.model_dump()==before


def test_native_wordart_type_is_shared_and_complex_shape_text_warns(tmp_path,monkeypatch):
    from backend.word_calibration import prepare
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('wordart-types')
    plain=text();other=text();complex=text(text_gradient=['#ff0000','#0000ff'])
    page=PageScene(index=0,width=600,height=350,original='unused.png',status='needs_review',layers=[plain,other,complex])
    output=tmp_path/'mixed.docx';export_docx(project,[page],output)
    with zipfile.ZipFile(output) as archive:
        root=E.fromstring(archive.read('word/document.xml'));ns={'v':'urn:schemas-microsoft-com:vml','wps':'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'}
        assert len(root.xpath('//v:shapetype',namespaces=ns))==1
        assert len(root.xpath('//v:shape/v:textpath',namespaces=ns))==2
        assert len(root.xpath('//wps:wsp',namespaces=ns))==1
    copies,report=prepare(project,[page],tmp_path/'probe')
    assert copies[0].model_dump()==page.model_dump() and any('横向字形' in warning for warning in report['warnings'])
