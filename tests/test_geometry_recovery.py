import numpy as np
import pytest
from backend.geometry_recovery import circle_alpha,recover_circles
from backend.models import LayerElement


def sample():
    width,height=160,110;box=(0,0,width,height)
    image=np.full((height,width,3),255,dtype=float)
    for center,color,opacity in [((51,55),(48,100,220),1),((79,55),(52,176,149),.6)]:
        alpha=circle_alpha(center,26,box)[:,:,None]*opacity
        image=image*(1-alpha)+np.array(color)*alpha
    return np.dstack((np.round(image).astype(np.uint8),np.full((height,width),255,np.uint8)))


def test_overlapping_circles_become_complete_native_shapes_without_old_copies():
    image=sample();before=image.copy()
    parent=LayerElement(kind='image',name='scan',x=10,y=20,width=80,height=55,asset='source.png')
    cleaned,layers,rows=recover_circles(parent,image)
    assert len(layers)==2 and len(rows)==1
    assert rows[0]['local_mean_absolute_error']<1
    assert rows[0]['foreground_opacity']==pytest.approx(.6,abs=.025)
    assert all(layer.kind=='path' and len(layer.path)==6 and layer.inferred and layer.needs_review for layer in layers)
    assert all(layer.width==pytest.approx(26,abs=1) for layer in layers)
    assert layers[0].x==pytest.approx(22.5,abs=.7)
    assert layers[1].x==pytest.approx(36.5,abs=.7)
    assert np.array_equal(cleaned,np.full_like(image,255))
    assert np.array_equal(image,before)


def test_tiny_unrelated_decoration_is_not_erased_by_a_good_overall_fit():
    image=sample();image[52:54,96:98,:3]=[235,20,65]
    parent=LayerElement(kind='image',name='scan',x=0,y=0,width=160,height=110,asset='x.png')
    cleaned,layers,rows=recover_circles(parent,image)
    assert not layers and not rows and np.array_equal(cleaned,image)


def test_nonflat_photograph_and_alpha_cutout_keep_the_original():
    parent=LayerElement(kind='image',name='photo',x=0,y=0,width=160,height=110,asset='x.png')
    photo=np.random.default_rng(4).integers(0,256,(110,160,4),dtype=np.uint8);photo[:,:,3]=255
    assert not recover_circles(parent,photo)[1]
    cutout=sample();cutout[0,0,3]=0
    cleaned,layers,_=recover_circles(parent,cutout)
    assert not layers and np.array_equal(cleaned,cutout)
    parent.opacity=.5
    assert not recover_circles(parent,sample())[1]
