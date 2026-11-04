from scripts.verify_image_formats import known_text_coverage
from scripts.audit_editability_gate import badge_text_complete
from scripts.audit_editability_gate import preserved_brand_mark


def test_strict_symbols_and_repeated_characters_cannot_be_reported_as_zero_missing():
    coverage=known_text_coverage(['A∙A','1 23'],['A·A','123'])
    assert coverage=={'missing_strings':['A∙A'],'missing_chars':1,'extra_chars':1}
    assert known_text_coverage(['A A A'],['AA'])['missing_chars']==1


def test_big_logo_name_does_not_satisfy_all_circular_badge_text():
    assert not badge_text_complete([])
    assert not badge_text_complete(['溫州大學'])
    assert not badge_text_complete(['WENZHOU UNIVERSITY'])
    assert badge_text_complete(['溫州大學','WENZHOU UNIVERSITY'])


def test_only_an_explicit_intact_brand_is_exempt_from_text_reconstruction():
    image={'id':'brand','kind':'image','x':793,'y':20,'width':145,'height':48,'visible':True,'asset':'original.png','restoration_asset':'original.png'}
    assert not preserved_brand_mark({'layers':[image]})
    image['content_role']='logo';assert preserved_brand_mark({'layers':[image]})
    assert not preserved_brand_mark({'layers':[{**image,'asset':'ocr-clean.png'}]})
    assert not preserved_brand_mark({'layers':[image,{'id':'child','kind':'text','parent_id':'brand'}]})
