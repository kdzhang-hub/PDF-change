import copy
import json
import zipfile

import fitz
import numpy as np
import pytest
from lxml import etree
from pydantic import ValidationError
from backend import store,native_text_layout
from backend.models import LayerElement,PageScene,TextLayout,NativeTextLayout
from backend.export import export_pptx
from backend.export_docx import export_docx


def positioned(text='A中B'):
    layer=LayerElement(kind='text',name='line',text=text,x=10,y=20,width=100,height=30,font='Arial',font_size=12)
    layer.text_layout=TextLayout(text=text,font='Arial',font_size=12,positions=[(i*18,12) for i in range(len(text))],
        pptx=NativeTextLayout(offset=(.2,.3),spacing=[1.2]*len(text)),
        docx=NativeTextLayout(offset=(-.4,.5),spacing=[2.1]*len(text)))
    return layer


@pytest.mark.parametrize('updates',[{'text':'Changed'},{'font':'SimSun'},{'font_size':14},{'bold':True},{'char_spacing':2},{'text_fit':'shape'},{'stroke':'#ff0000'}])
def test_stale_character_positions_are_cleared_when_text_or_style_changes(updates):
    data=positioned().model_dump();data.update(updates)
    assert LayerElement.model_validate(data).text_layout is None


def test_move_rotate_color_keep_local_layout_and_unicode_uses_codepoints():
    layer=positioned('A😀B');data=layer.model_dump();data.update(x=80,y=90,rotation=25,color='#ff0000')
    updated=LayerElement.model_validate(data)
    assert updated.text_layout==layer.text_layout and len(updated.text_layout.positions)==3
    bad=copy.deepcopy(data);bad['text_layout']['positions'].append([0,0])
    with pytest.raises(ValidationError):LayerElement.model_validate(bad)
    bad=copy.deepcopy(data);bad['text_layout']['pptx']['spacing'][0]=float('nan')
    with pytest.raises(ValidationError):LayerElement.model_validate(bad)


def test_both_exporters_keep_one_native_text_shape_and_exact_whole_text(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('layout')
    layer=positioned();page=PageScene(index=0,width=200,height=120,original='unused',status='ready',layers=[layer])
    ppt=tmp_path/'one.pptx';word=tmp_path/'one.docx'
    export_pptx(project,[page],ppt);export_docx(project,[page],word)
    with zipfile.ZipFile(ppt) as z:
        xml=etree.fromstring(z.read('ppt/slides/slide1.xml'))
        assert len(xml.xpath('//*[local-name()="sp"]'))==1
        assert ''.join(xml.xpath('//*[local-name()="t"]/text()'))==layer.text
        assert xml.xpath('//*[local-name()="rPr"]/@spc')==['120']*3
        # python-pptx truncates EMU conversion; one EMU is <0.00008 points.
        assert abs(int(xml.xpath('//*[local-name()="xfrm"]/*[local-name()="off"]/@x')[0])-round(10.2*12700))<=1
    with zipfile.ZipFile(word) as z:
        xml=etree.fromstring(z.read('word/document.xml'))
        assert len(xml.xpath('//*[local-name()="shape"]'))==1
        assert ''.join(xml.xpath('//*[local-name()="t"]/text()'))==layer.text
        assert xml.xpath('//*[local-name()="rPr"]/*[local-name()="spacing"]/@*[local-name()="val"]')==['42']*3
        assert xml.xpath('//*[local-name()="autoSpaceDE"]/@*[local-name()="val"]')==['0']


@pytest.fixture
def source_case(tmp_path,monkeypatch):
    monkeypatch.setattr(native_text_layout,'spacing_quantum',lambda *args:None)
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('source')
    doc=fitz.open();p=doc.new_page(width=240,height=140);p.insert_text((20,40),'Hello',fontsize=12)
    doc.save(store.project_dir(project)/'source.pdf');doc.close()
    layer=LayerElement(kind='text',name='Hello',text='Hello',x=20,y=25,width=90,height=20,font='Arial',font_size=12)
    page=PageScene(index=0,width=240,height=140,original='unused',status='ready',layers=[layer])
    return project,page


def test_environment_failure_keeps_natural_text_and_never_calls_cloud(source_case,monkeypatch):
    project,page=source_case;before=page.model_dump()
    def failed(*args):raise RuntimeError('Office unavailable')
    monkeypatch.setattr(native_text_layout,'render',failed)
    result,diagnostics=native_text_layout.calibrate(project,page)
    assert page.model_dump()==before
    assert result.layers[0].text_layout is None and len(result.warnings)==2
    assert not store.budget()['calls']


def test_locked_and_manual_content_are_never_remeasured(source_case,monkeypatch):
    project,page=source_case
    def forbidden(*args):raise AssertionError('Manual content must not be probed')
    monkeypatch.setattr(native_text_layout,'render',forbidden)
    for key in ('locked','edited'):
        sample=page.model_copy(deep=True);setattr(sample.layers[0],key,True)
        result,diagnostics=native_text_layout.calibrate(project,sample)
        assert not diagnostics and result.model_dump()==sample.model_dump()


def test_same_word_elsewhere_cannot_supply_layout_coordinates():
    layer=positioned('ABC')
    assert native_text_layout.actual_positions([('ABC',np.array([[200,300],[220,300],[240,300]]))],layer) is None


def test_coordinates_are_verified_after_bounded_corrections(source_case,monkeypatch):
    project,page=source_case;calls=[];before=page.model_dump()
    def renderer(project,candidate,kind,folder):
        folder.mkdir(parents=True,exist_ok=True);calls.append(kind)
        l=candidate.layers[0];n=getattr(l.text_layout,kind)
        # A controlled renderer with known local advances and a fixed bearing.
        origin=np.array([l.x+2+n.offset[0],l.y+10+n.offset[1]])
        x=np.arange(len(l.text))*6+np.concatenate(([0],np.cumsum(n.spacing[:-1])))
        return [(l.text,np.column_stack((x+origin[0],np.full(len(l.text),origin[1]))))]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    result,diagnostics=native_text_layout.calibrate(project,page)
    assert calls==['pptx','docx']*4 and page.model_dump()==before
    assert result.layers[0].text_layout.pptx and result.layers[0].text_layout.docx
    assert all(r['maxOriginError']<=1 for r in diagnostics if r['round']==3)


def test_a_later_bad_measurement_cannot_replace_a_verified_layout(source_case,monkeypatch):
    project,page=source_case;rounds={'pptx':0,'docx':0}
    def renderer(project,candidate,kind,folder):
        folder.mkdir(parents=True,exist_ok=True)
        layer=candidate.layers[0];target=np.array(layer.text_layout.positions)+[layer.x,layer.y]
        error=[(2,3),(.2,.2),(3,3),(4,4)][rounds[kind]];rounds[kind]+=1
        return [(layer.text,target+error)]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    result,_=native_text_layout.calibrate(project,page)
    for kind in ('pptx','docx'):
        assert getattr(result.layers[0].text_layout,kind).offset==pytest.approx((-2,-3))


def test_diagnostic_page_can_widen_without_changing_saved_geometry(source_case,monkeypatch,tmp_path):
    from backend import export
    from types import SimpleNamespace
    project,page=source_case;page.layers[0].text_layout=positioned('Hello').text_layout
    before=page.model_dump();probes=[];folder=tmp_path/'probe'
    monkeypatch.setattr(export,'export_pptx',lambda p,pages,path:probes.append(pages[0]))
    def office(*args,**kwargs):
        doc=fitz.open();p=doc.new_page(width=300,height=140);p.insert_text((20,40),'Hello');doc.save(folder/'powerpoint.pdf');doc.close()
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(native_text_layout.subprocess,'run',office)
    native_text_layout.render(project,page,'pptx',folder)
    assert page.model_dump()==before and probes[0] is not page
    assert probes[0].layers[0].width>page.layers[0].width


def test_retry_only_measures_missing_format_and_preserves_verified_cache(source_case,monkeypatch):
    project,page=source_case;layer=page.layers[0]
    with fitz.open(store.project_dir(project)/'source.pdf') as doc:positions=native_text_layout.source_positions(doc[0],layer)
    layer.text_layout=TextLayout(text=layer.text,font=layer.font,font_size=layer.font_size,positions=positions,
        pptx=NativeTextLayout(offset=(.1,.2),spacing=[.3]*len(layer.text)))
    before=layer.text_layout.pptx.model_copy(deep=True);calls=[]
    def renderer(project,candidate,kind,folder):
        calls.append(kind);folder.mkdir(parents=True,exist_ok=True)
        item=candidate.layers[0]
        return [(item.text,np.array(item.text_layout.positions)+[item.x,item.y])]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    result,_=native_text_layout.calibrate(project,page)
    assert calls==['docx']*4
    assert result.layers[0].text_layout.pptx==before and result.layers[0].text_layout.docx
    assert page.layers[0].text_layout.docx is None


def test_office_failure_after_a_verified_round_keeps_that_round(source_case,monkeypatch):
    project,page=source_case;calls={'pptx':0,'docx':0}
    def renderer(project,candidate,kind,folder):
        folder.mkdir(parents=True,exist_ok=True);calls[kind]+=1
        if calls[kind]>1:raise RuntimeError('Office became unavailable')
        item=candidate.layers[0]
        return [(item.text,np.array(item.text_layout.positions)+[item.x,item.y])]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    result,_=native_text_layout.calibrate(project,page)
    assert result.layers[0].text_layout.pptx and result.layers[0].text_layout.docx
    assert calls=={'pptx':2,'docx':2} and len(result.warnings)==2


def test_visual_fidelity_wins_over_a_smaller_origin_error_within_the_gate(source_case,monkeypatch):
    project,page=source_case;calls={'pptx':0,'docx':0};scores={}
    def renderer(project,candidate,kind,folder):
        folder.mkdir(parents=True,exist_ok=True);index=calls[kind];calls[kind]+=1
        item=candidate.layers[0];errors=[(2,3),(.2,.2),(0,0),(.1,.1)]
        scores[str(folder)]={item.id:[1,.99,.9,.95][index]}
        return [(item.text,np.array(item.text_layout.positions)+[item.x,item.y]+errors[index])]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    monkeypatch.setattr(native_text_layout,'visual_scores',lambda ref,path:scores[str(path.parent)])
    result,_=native_text_layout.calibrate(project,page)
    for kind in ('pptx','docx'):
        # The perfect-looking first image fails the coordinate gate; the third
        # has perfect origins but worse glyph pixels than the second image.
        assert getattr(result.layers[0].text_layout,kind).offset==pytest.approx((-2,-3))


def cached_source(source_case):
    project,page=source_case;layer=page.layers[0]
    with fitz.open(store.project_dir(project)/'source.pdf') as doc:positions=native_text_layout.source_positions(doc[0],layer)
    layer.text_layout=TextLayout(text=layer.text,font=layer.font,font_size=layer.font_size,positions=positions,
        pptx=NativeTextLayout(offset=(2,3),spacing=[0]*len(layer.text)),
        docx=NativeTextLayout(offset=(2,3),spacing=[0]*len(layer.text)))
    return project,page


def test_explicit_recalibration_can_upgrade_existing_automatic_layouts(source_case,monkeypatch):
    project,page=cached_source(source_case);before=page.model_dump();calls=[]
    def renderer(project,candidate,kind,folder):
        calls.append(kind);folder.mkdir(parents=True,exist_ok=True);layer=candidate.layers[0]
        native=getattr(layer.text_layout,kind)
        return [(layer.text,np.array(layer.text_layout.positions)+[layer.x,layer.y]+native.offset)]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    unchanged,_=native_text_layout.calibrate(project,page)
    assert not calls and unchanged.model_dump()==before
    result,_=native_text_layout.calibrate(project,page,force=True)
    assert calls==['pptx','docx']*4 and page.model_dump()==before
    assert result.layers[0].text_layout.pptx.offset==pytest.approx((0,0))
    assert result.layers[0].text_layout.docx.offset==pytest.approx((0,0))


def test_explicit_recalibration_failure_preserves_previously_verified_layouts(source_case,monkeypatch):
    project,page=cached_source(source_case);before=page.model_dump()
    def failed(*args):raise RuntimeError('Office unavailable')
    monkeypatch.setattr(native_text_layout,'render',failed)
    result,_=native_text_layout.calibrate(project,page,force=True)
    assert result.layers[0].text_layout==page.layers[0].text_layout
    assert page.model_dump()==before and len(result.warnings)==2


def test_calibration_job_requests_an_explicit_layout_refresh(source_case,monkeypatch):
    from types import SimpleNamespace
    from backend import jobs,font_calibration
    project,page=source_case;store.save_page(project,page);calls=[]
    def calibrate(p,current,rebuild_native=False):
        calls.append(rebuild_native);return current,[{'id':current.layers[0].id}]
    monkeypatch.setattr(font_calibration,'calibrate_page',calibrate)
    monkeypatch.setattr(jobs,'POOL',SimpleNamespace(submit=lambda func,arg:func(arg)))
    job=jobs.submit(project,[0],'calibrate')
    assert store.get_job(job)['status']=='done' and calls==[True]


def test_rejected_refresh_preserves_previous_layout_and_discloses_it(source_case,monkeypatch):
    project,page=cached_source(source_case)
    def renderer(project,candidate,kind,folder):
        folder.mkdir(parents=True,exist_ok=True);layer=candidate.layers[0]
        return [(layer.text,np.array(layer.text_layout.positions)+[layer.x+10,layer.y])]
    monkeypatch.setattr(native_text_layout,'render',renderer)
    result,_=native_text_layout.calibrate(project,page,force=True)
    assert result.layers[0].text_layout==page.layers[0].text_layout
    assert len(result.warnings)==2 and all('保留已有布局' in w for w in result.warnings)
