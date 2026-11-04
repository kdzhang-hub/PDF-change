from pathlib import Path
import fitz
import numpy as np
import pytest
from backend.layout_quality import infer_quantum,quantize,corrected_spacing,prepare_reference,visual_scores
from backend.models import LayerElement,PageScene,TextLayout


def test_quantum_is_measured_and_irregular_or_constant_samples_are_rejected():
    values=[9.96+np.sign(v)*np.floor(abs(v)/.12+.500000001)*.12 for v in np.linspace(-.25,.25,51)]
    assert infer_quantum(values)==pytest.approx(.12)
    assert infer_quantum([10]*51) is None
    assert infer_quantum([10,10.1,float('nan')]*17) is None
    assert infer_quantum(np.linspace(10,10.5,51)) is None  # Fine spacing needs no coarse-grid compensation.
    assert infer_quantum([10,10.1,10.27,10.31,10.48,10.53,10.59,10.7,10.84]) is None


@pytest.mark.parametrize('value,expected',[(.06,.12),(-.06,-.12),(.05,0),(-.05,0),(.18,.24)])
def test_native_half_steps_round_away_from_zero(value,expected):
    assert quantize(value,.12)==pytest.approx(expected)


def test_cumulative_rounding_does_not_drift_across_a_long_line():
    selected=list(range(101));delta=np.column_stack((-np.arange(101)*.01,np.zeros(101)))
    values=corrected_spacing([0.0]*101,selected,delta,quantum=.12)
    error=np.r_[0,np.cumsum(values[:-1])]-delta[:,0]
    assert max(abs(error))<=.06000001
    assert max(abs(np.r_[0,np.cumsum(np.round(np.diff(delta[:,0]),2))]-delta[:,0]))<1e-8
    # Rounding each requested value separately onto the native grid loses an
    # entire point by the end, even though each requested gap is only .01 off.
    independent=[quantize(v,.12) for v in np.diff(delta[:,0])]
    assert abs(sum(independent)-delta[-1,0])>=.99


def test_whitespace_slots_and_the_last_character_are_not_reassigned():
    values=[0,.03,0,.04]
    result=corrected_spacing(values,[0,2,3],np.array([[0,0],[-.02,0],[-.04,0]]),quantum=.12)
    assert result[1]==values[1] and result[-1]==values[-1]
    assert values==[0,.03,0,.04]


def test_local_visual_scores_compare_actual_source_pixels_without_modifying_files(tmp_path):
    source=tmp_path/'source.pdf';other=tmp_path/'other.pdf'
    for path,offset in [(source,0),(other,5)]:
        doc=fitz.open();p=doc.new_page(width=200,height=100);p.insert_text((20+offset,40),'Hello',fontsize=12);doc.save(path);doc.close()
    layer=LayerElement(kind='text',name='Hello',text='Hello',x=20,y=25,width=90,height=20,font_size=12,source_ink_bbox=[18,26,55,44])
    layer.text_layout=TextLayout(text=layer.text,font=layer.font,font_size=12,positions=[(i*8,15) for i in range(5)])
    page=PageScene(index=0,width=200,height=100,original='unused',layers=[layer])
    before=source.read_bytes();reference=prepare_reference(source,0,page)
    assert visual_scores(reference,source)[layer.id]==pytest.approx(1)
    assert visual_scores(reference,other)[layer.id]<.95
    assert source.read_bytes()==before
    assert visual_scores(reference,tmp_path/'missing.pdf')=={}


def test_reference_size_is_bounded_and_wrong_geometry_is_not_scored(tmp_path):
    path=tmp_path/'source.pdf';doc=fitz.open();doc.new_page(width=100,height=100);doc.save(path);doc.close()
    layer=LayerElement(kind='text',name='tiny',text='A',x=0,y=0,width=2,height=2,source_ink_bbox=[0,0,2,2])
    layer.text_layout=TextLayout(text='A',font=layer.font,font_size=layer.font_size,positions=[(0,1)])
    page=PageScene(index=0,width=100,height=100,original='unused',layers=[layer])
    ref=prepare_reference(path,0,page,max_pixels=10_000)
    assert all(r[3].shape[0]*r[3].shape[1]<=10_000 for r in ref['rasters'])
    assert visual_scores(ref,path)=={}
    page.width=101;assert prepare_reference(path,0,page) is None
