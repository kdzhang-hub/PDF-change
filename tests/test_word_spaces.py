from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw,ImageFont
from backend.text_recovery import fit_font,fit_with_word_spaces

FONT=Path('C:/Windows/Fonts/arialbd.ttf')
pytestmark=pytest.mark.skipif(not FONT.exists(),reason='Real Arial fixture font unavailable')

def glyph(text,tracking=0):
    font=ImageFont.truetype(str(FONT),48);image=Image.new('L',(900,100));draw=ImageDraw.Draw(image)
    x=10
    for char in text:
        draw.text((x,10),char,font=font,fill=255);x+=font.getlength(char)+tracking
    return np.array(image.crop(image.getbbox()))

def test_missing_space_restores_text_and_bold_face_from_pixels():
    mask=glyph('LOCAL WHITE');before=fit_font('LOCALWHITE',mask)
    text,after=fit_with_word_spaces('LOCALWHITE',mask,before)
    assert text=='LOCAL WHITE' and after['bold']
    assert after['score']>=.84 and after['score']-before['score']>=.12

def test_uniform_tracking_does_not_invent_words():
    mask=glyph('HIHITEST',tracking=12);before=fit_font('HIHITEST',mask)
    text,after=fit_with_word_spaces('HIHITEST',mask,before)
    assert text=='HIHITEST' and after is before

def test_existing_spaces_and_unaligned_characters_are_preserved():
    mask=glyph('LOCAL WHITE');fit=fit_font('LOCAL WHITE',mask)
    assert fit_with_word_spaces('LOCAL WHITE',mask,fit)==('LOCAL WHITE',fit)
    assert fit_with_word_spaces('LOCALWHITEX',mask,None)==('LOCALWHITEX',None)
