from types import SimpleNamespace
import copy
import fitz
import pytest
from PIL import Image,ImageDraw
from backend import store,font_calibration
from backend.models import LayerElement,PageScene


@pytest.fixture
def wide_pdf(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    project=store.create('source-tracking')
    doc=fitz.open();page=doc.new_page(width=400,height=180)
    page.insert_text((30,80),'WIDE',fontsize=20)
    xref=page.get_contents()[0]
    doc.update_stream(xref,doc.xref_stream(xref).replace(b'BT',b'BT\n18 Tc',1))
    doc.save(store.project_dir(project)/'source.pdf');doc.close()
    with fitz.open(store.project_dir(project)/'source.pdf') as pdf:
        traces=pdf[0].get_texttrace()
    box=list(traces[0]['bbox'])
    layer=LayerElement(kind='text',name='WIDE',text='WIDE',font='Arial',font_size=20,
                       x=30,y=60,width=box[2]-box[0]+20,height=30,source_ink_bbox=box)
    return project,layer,traces


def test_wide_tracking_requires_real_pdf_coordinates(wide_pdf):
    _,layer,traces=wide_pdf
    assert font_calibration.source_tracking(traces,layer)==pytest.approx(18,abs=.01)
    elsewhere=layer.model_copy(deep=True);elsewhere.source_ink_bbox[0]+=150;elsewhere.source_ink_bbox[2]+=150
    assert font_calibration.source_tracking(traces,elsewhere) is None


def test_ocr_manual_locked_and_irregular_text_do_not_relax_limit(wide_pdf):
    _,layer,traces=wide_pdf
    for updates in ({'source':'local-ocr'},{'edited':True},{'locked':True},{'rotation':90}):
        assert font_calibration.source_tracking(traces,layer.model_copy(update=updates)) is None
    irregular=copy.deepcopy(traces)
    chars=list(irregular[0]['chars']);changed=list(chars[1]);changed[2]=(changed[2][0]+8,changed[2][1]);chars[1]=tuple(changed);irregular[0]['chars']=tuple(chars)
    assert font_calibration.source_tracking(irregular,layer) is None


def test_office_calibration_preserves_proven_wide_tracking(wide_pdf,monkeypatch):
    project,layer,_=wide_pdf
    ocr=layer.model_copy(deep=True);ocr.id+='-ocr';ocr.source='local-ocr'
    page=PageScene(index=0,width=400,height=180,original='unused',layers=[layer,ocr])
    monkeypatch.setattr(font_calibration,'available',lambda:True)
    def render(*args,**kwargs):
        image=Image.new('RGB',(3200,1800),'white');draw=ImageDraw.Draw(image)
        # Same measured Office glyph width for the native and OCR strings.
        for row in range(2):draw.rectangle((40,50+row*96,93,70+row*96),fill='black')
        image.save(store.project_dir(project)/'font-calibration/probe-1.png')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(font_calibration.subprocess,'run',render)
    candidate,measurements=font_calibration.calibrate_page(project,page)
    native,recovered=candidate.layers
    assert 15<native.char_spacing<22
    assert recovered.char_spacing==pytest.approx(4)
    assert measurements[0]['source_tracking_evidence']==pytest.approx(18,abs=.01)
    assert measurements[1]['source_tracking_evidence'] is None
    assert layer.char_spacing==0  # Calibration still operates on a scene copy.
