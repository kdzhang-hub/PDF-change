from backend.models import LayerElement,PageScene
from backend.text_dedup import redundant_ocr_text


def text(value,box,source='pdf-native',**kw):
    x,y,r,b=box
    return LayerElement(kind='text',name=value,text=value,x=x,y=y,width=r-x,height=b-y,
                        source_ink_bbox=box,source=source,**kw)


def scene(*layers):return PageScene(index=0,width=400,height=300,original='x',layers=list(layers))


def test_raster_effect_ocr_cannot_make_a_second_editable_copy():
    native=text('参赛赛道',[10,20,90,40]);ocr=text('参赛赛道',[11,21,91,41],source='local-ocr')
    image=LayerElement(kind='image',name='cleaned effect',x=5,y=15,width=95,height=30,asset='cleaned.png')
    before=native.model_dump();result,rows=redundant_ocr_text(scene(image,native,ocr))
    assert [l.id for l in result.layers]==[image.id,native.id]
    assert rows[0]['kept_ids']==[native.id] and rows[0]['removed_id']==ocr.id
    assert native.model_dump()==before


def test_styled_native_fragments_cover_the_ocr_line_without_losing_punctuation():
    a=text('2024年',[10,20,45,40]);b=text('我考入，',[45,20,100,40])
    ocr=text('2024年我考入',[10,21,100,41],source='local-ocr')
    result,rows=redundant_ocr_text(scene(a,b,ocr))
    assert rows and [l.text for l in result.layers]==['2024年','我考入，']


def test_same_words_elsewhere_extra_words_and_manual_objects_remain():
    a=text('AlphaBeta',[10,20,90,40])
    elsewhere=text('AlphaBeta',[10,150,90,170],source='local-ocr')
    extended=text('AlphaBetaGamma',[10,20,140,40],source='local-ocr')
    manual=text('AlphaBeta',[10,20,90,40],source='local-ocr',edited=True)
    result,rows=redundant_ocr_text(scene(a,elsewhere,extended,manual))
    assert not rows and len(result.layers)==4
