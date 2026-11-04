import zipfile,math
import pytest
from lxml import etree as E
from backend import store,word_calibration as calibration
from backend.models import PageScene,LayerElement,TextShadow
from backend.export_docx import export_docx,NS


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()


def title(**updates):
    return LayerElement(kind='text',name='title',text='AB',font='Arial',font_size=20,
        x=15,y=20,width=100,height=40,source='pdf-text-group',source_ink_bbox=[30,40,65,60],**updates)


def test_native_word_effects_keep_rotated_and_multiline_text_editable(tmp_path):
    project=store.create('effects')
    layer=title(opacity=.6,rotation=15,text_gradient=['#ff0000','#00ff00','#0000ff'],
        text_gradient_positions=[.1,.4,.9],stroke='#abcdef',stroke_width=1.5,stroke_opacity=.5,
        text_shadow=TextShadow(color='#123456',opacity=.5,blur=2,dx=-3,dy=4))
    layer.text='中文\nAB'
    page=PageScene(index=0,width=300,height=200,original='none',status='ready',layers=[layer])
    with zipfile.ZipFile(export_docx(project,[page],tmp_path/'effects.docx')) as z:
        doc=E.fromstring(z.read('word/document.xml'))
        assert doc.xpath('//w:txbxContent//w:t/text()',namespaces=NS)==['中文','AB']
        assert not doc.xpath('//v:imagedata',namespaces=NS)
        assert len(doc.xpath('//wp:anchor',namespaces=NS))==1
        assert doc.xpath('//w14:textFill/w14:gradFill/w14:gsLst/w14:gs/@w14:pos',namespaces=NS)==['10000','40000','90000']*2
        assert doc.xpath('//w14:textFill//w14:alpha/@w14:val',namespaces=NS)==['40000']*6
        assert doc.xpath('//w14:textOutline/@w14:w',namespaces=NS)==['19050']*2
        assert doc.xpath('//w14:textOutline//w14:alpha/@w14:val',namespaces=NS)==['70000']*2
        assert doc.xpath('//w14:shadow/@w14:dist',namespaces=NS)==['63500']*2
        assert doc.xpath('//w14:shadow/@w14:dir',namespaces=NS)==[str(round(math.degrees(math.atan2(4,-3))*60000))]*2
        assert doc.xpath('//w14:shadow//w14:alpha/@w14:val',namespaces=NS)==['70000']*2
        for rp in doc.xpath('//w:rPr',namespaces=NS):
            assert len(rp.xpath('./w14:textFill',namespaces=NS))<=1


def test_word_ink_fit_uses_actual_metrics_and_rejects_clipped_or_wrong_bounds():
    layer=title(text_gradient=['#000000','#ffffff'])
    fitted=calibration.fit_measurement(layer,[2,5,32,25],20)
    assert (fitted.x,fitted.y,fitted.font_size,fitted.char_spacing)==(28,35,20,4)
    assert fitted.text_gradient_positions==pytest.approx([.125,.625])
    assert (layer.x,layer.y,layer.char_spacing)==(15,20,0)
    for bounds in ([0,5,32,25],[2,5,1440,25],[2,5,32,90],[2,5,32,10]):
        assert calibration.fit_measurement(layer,bounds,20) is None


def test_calibration_only_fits_unmodified_visible_ink_groups():
    layer=title();assert calibration.target(layer)
    for update in ({'source':'pdf-native'},{'source':'local-ocr'},{'locked':True},{'edited':True},
                   {'rotation':15},{'visible':False},{'source_ink_bbox':None},{'text':'A\nB'}):
        assert not calibration.target(layer.model_copy(update=update))


def test_word_environment_failure_preserves_every_scene(tmp_path,monkeypatch):
    from backend import fonts
    project=store.create('environment');layer=title()
    page=PageScene(index=0,width=300,height=200,original='none',status='ready',layers=[layer])
    monkeypatch.setattr(calibration,'available',lambda:False)
    copies,report=calibration.prepare(project,[page],tmp_path/'missing')
    assert copies[0].model_dump()==page.model_dump() and report['warnings']
    monkeypatch.setattr(calibration,'available',lambda:True)
    monkeypatch.setattr(fonts,'installed_map',lambda:{'arial':'Arial'})
    def failure(folder):raise RuntimeError('Word failed')
    monkeypatch.setattr(calibration,'render_probe',failure)
    copies,report=calibration.prepare(project,[page],tmp_path/'failed')
    assert copies[0].model_dump()==page.model_dump()
    assert report['warnings'] and report['calibrated']==[]


def test_missing_fonts_do_not_trigger_word_or_measure_substitutes(tmp_path,monkeypatch):
    from backend import fonts
    project=store.create('missing-font');page=PageScene(index=0,width=300,height=200,original='none',status='ready',layers=[title()])
    monkeypatch.setattr(calibration,'available',lambda:True)
    monkeypatch.setattr(fonts,'installed_map',lambda:{})
    monkeypatch.setattr(calibration,'render_probe',lambda *_:pytest.fail('A missing font must not be calibrated'))
    copies,report=calibration.prepare(project,[page],tmp_path/'missing-font')
    assert copies[0].model_dump()==page.model_dump() and report['skipped']==[page.layers[0].id]


def test_word_probe_fits_export_copy_but_keeps_manual_and_native_objects(tmp_path,monkeypatch):
    import fitz
    from backend import fonts
    project=store.create('fit-copy');layer=title();manual=title(edited=True);native=title().model_copy(update={'source':'pdf-native'})
    page=PageScene(index=0,width=300,height=200,original='none',status='ready',layers=[layer,manual,native])
    before=page.model_dump()
    monkeypatch.setattr(calibration,'available',lambda:True)
    monkeypatch.setattr(fonts,'installed_map',lambda:{'arial':'Arial'})
    def render(folder):
        doc=fitz.open();p=doc.new_page(width=1500,height=1200)
        # A measured ink rectangle with known offsets and a 40pt probe font.
        p.draw_rect(fitz.Rect(29,30,89,70),color=None,fill=(0,0,0))
        doc.save(folder/'probe.pdf');doc.close()
    monkeypatch.setattr(calibration,'render_probe',render)
    copies,report=calibration.prepare(project,[page],tmp_path/'fit')
    assert page.model_dump()==before
    assert len(report['calibrated'])==1 and not report['warnings']
    assert copies[0].layers[0].x==pytest.approx(28)
    assert copies[0].layers[0].y==pytest.approx(35)
    assert copies[0].layers[1].model_dump()==manual.model_dump()
    assert copies[0].layers[2].model_dump()==native.model_dump()


def test_word_export_reports_unavailable_calibration_to_browser(tmp_path,monkeypatch):
    import json
    from urllib.parse import unquote
    from fastapi.testclient import TestClient
    from backend.app import app
    from backend import export_service,jobs
    project=store.create('notice');page=PageScene(index=0,width=300,height=200,original='none',status='ready',layers=[title()])
    store.save_page(project,page)
    output=export_docx(project,[page],tmp_path/'notice.docx')
    message='本机 Word 字形校准未完成，请核对导出位置'
    output.with_suffix('.report.json').write_text(json.dumps({'warnings':[message]}),encoding='utf-8')
    monkeypatch.setattr(export_service,'create_export',lambda *a,**k:output)
    monkeypatch.setattr(jobs,'start_pool',lambda:None)
    monkeypatch.setattr(jobs,'stop_pool',lambda:None)
    with TestClient(app) as client:
        response=client.post(f'/api/projects/{project}/export-docx',json={'pages':[0]})
        assert response.status_code==200
        assert unquote(response.headers['X-LayerDeck-Notice'])==message
    assert store.get_page(project,0).model_dump()==page.model_dump()
    assert store.budget()['calls']==[]


def test_effect_roundtrip_tolerates_word_defaults_but_rejects_changed_appearance():
    from scripts.verify_word_effects_roundtrip import canonical,equivalent
    before=E.fromstring(('''<w14:textOutline xmlns:w14="'''+NS['w14']+'''" w14:w="4233"><w14:solidFill><w14:srgbClr w14:val="24D8EB"><w14:alpha w14:val="0"/></w14:srgbClr></w14:solidFill></w14:textOutline>''').encode())
    after=E.fromstring(E.tostring(before))
    after.set('{'+NS['w14']+'}w','4229')
    alpha=after.find('.//w14:alpha',NS);alpha.getparent().remove(alpha)
    E.SubElement(after,'{'+NS['w14']+'}prstDash',{'{'+NS['w14']+'}val':'solid'})
    E.SubElement(after,'{'+NS['w14']+'}bevel')
    assert equivalent(canonical(before),canonical(after))
    color=after.find('.//w14:srgbClr',NS)
    color.set('{'+NS['w14']+'}val','FF0000')
    assert not equivalent(canonical(before),canonical(after))
    color.set('{'+NS['w14']+'}val','24D8EB');after.set('{'+NS['w14']+'}w','4000')
    assert not equivalent(canonical(before),canonical(after))
