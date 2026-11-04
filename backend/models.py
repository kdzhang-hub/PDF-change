"""The editable scene is the only source of truth for both editor and export."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator,field_validator
import math
import uuid
import re


def uid() -> str:
    return uuid.uuid4().hex


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class PathCommand(Model):
    op: Literal['M', 'L', 'C', 'Z']
    points: list[float] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def valid_points(self):
        if len(self.points) != {'M': 2, 'L': 2, 'C': 6, 'Z': 0}[self.op]:
            raise ValueError('路径坐标数量不正确')
        return self


class TextShadow(Model):
    color: str = Field(default='#000000',pattern=r'^#[0-9a-fA-F]{6}$')
    opacity: float = Field(default=.6,ge=0,le=1)
    blur: float = Field(default=4,ge=0,le=100)
    dx: float = Field(default=0,ge=-100,le=100)
    dy: float = Field(default=2,ge=-100,le=100)


class FontAssetRef(Model):
    file: str = Field(pattern=r'^[a-zA-Z0-9_-]+\.ttf$')
    characters: str = Field(min_length=1,max_length=4096)
    label: str = Field(default='还原艺术字',max_length=120)


class NativeTextLayout(Model):
    offset: tuple[float,float] = (0,0)
    spacing: list[float] = Field(max_length=4000)

    @field_validator('spacing')
    @classmethod
    def bounded_spacing(cls,values):
        if any(abs(v)>100 for v in values):raise ValueError('文字局部字距超出可表达范围')
        return values


class TextLayout(Model):
    text: str = Field(max_length=4000)
    font: str
    font_size: float = Field(gt=0,le=1000)
    bold: bool = False
    italic: bool = False
    char_spacing: float = 0
    positions: list[tuple[float,float]] = Field(max_length=4000)
    pptx: NativeTextLayout | None = None
    docx: NativeTextLayout | None = None

    @model_validator(mode='after')
    def complete_characters(self):
        if len(self.positions)!=len(self.text) or any(n and len(n.spacing)!=len(self.text) for n in (self.pptx,self.docx)):
            raise ValueError('逐字位置及局部字距必须与完整文字对应')
        if any(abs(v)>50000 for xy in self.positions for v in xy):raise ValueError('逐字坐标超出范围')
        return self

    def matches(self,layer):
        return (layer.kind=='text' and layer.text_fit=='natural' and '\n' not in layer.text and '\r' not in layer.text
                and not layer.stroke and not layer.text_gradient and not layer.text_shadow
                and all(getattr(self,key)==getattr(layer,key) for key in ('text','font','font_size','bold','italic','char_spacing')))


class LayerElement(Model):
    id: str = Field(default_factory=uid, pattern=r'^[a-zA-Z0-9_-]+$')
    kind: Literal['text', 'path', 'image']
    name: str
    x: float
    y: float
    width: float = Field(gt=0, le=50000)
    height: float = Field(gt=0, le=50000)
    rotation: float = 0
    z: float = 0
    opacity: float = Field(default=1, ge=0, le=1)
    visible: bool = True
    locked: bool = False
    group_id: str | None = None
    parent_id: str | None = None
    text: str = ''
    text_fit: Literal['natural','shape'] = 'natural'
    text_layout: TextLayout | None = None
    font: str = 'Microsoft YaHei'
    font_asset: FontAssetRef | None = None
    font_size: float = Field(default=18, gt=0, le=1000)
    bold: bool = False
    italic: bool = False
    color: str = Field(default='#172033', pattern=r'^#[0-9a-fA-F]{6}$')
    fill: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    stroke: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    stroke_width: float = Field(default=1, ge=0, le=1000)
    fill_opacity: float = Field(default=1, ge=0, le=1)
    stroke_opacity: float = Field(default=1, ge=0, le=1)
    even_odd: bool = False
    path: list[PathCommand] = Field(default_factory=list)
    asset: str | None = None
    mask: str | None = None
    source: str = 'pdf-native'
    confidence: float = Field(default=1, ge=0, le=1)
    needs_review: bool = False
    inferred: bool = False
    edited: bool = False
    notes: list[str] = Field(default_factory=list)
    original_type: str | None = None
    restoration_asset: str | None = None
    text_gradient: list[str] = Field(default_factory=list,max_length=8)
    text_gradient_positions: list[float] = Field(default_factory=list,max_length=8)
    text_gradient_angle: float = Field(default=90,ge=0,le=360)
    source_ink_bbox: list[float] | None = Field(default=None,min_length=4,max_length=4)
    char_spacing: float = Field(default=0,ge=-100,le=100)
    text_shadow: TextShadow | None = None
    recognized_text: str = Field(default='',max_length=4000)
    content_role: Literal['auto','logo','content'] = 'auto'

    @field_validator('text_gradient')
    @classmethod
    def gradient_colors(cls,values):
        if values and len(values)<2:raise ValueError('渐变至少需要两个色点')
        if any(not re.fullmatch(r'#[0-9a-fA-F]{6}',value) for value in values):raise ValueError('渐变颜色格式不正确')
        return values

    @model_validator(mode='after')
    def gradient_stops(self):
        # An edited string or font must reflow as native text. Never apply old
        # glyph positions to new content, including writes outside the browser.
        if self.text_layout and not self.text_layout.matches(self):self.text_layout=None
        if self.font_asset:
            if self.kind!='text':raise ValueError('仅文字可关联还原字体')
            if any(char not in self.font_asset.characters for char in self.text):raise ValueError('新文字不在还原字体中，请替换为普通字体')
        if self.kind!='image' and self.content_role!='auto':raise ValueError('仅图片素材可设置标识保留方式')
        if self.text_fit=='shape' and (self.kind!='text' or '\n' in self.text or '\r' in self.text):raise ValueError('随框拉伸仅支持单行文字')
        values=self.text_gradient_positions
        if values and (len(values)!=len(self.text_gradient) or any(not 0<=v<=1 for v in values) or values!=sorted(values)):
            raise ValueError('渐变色点位置必须递增，且与颜色数量相同')
        return self


class PageScene(Model):
    index: int = Field(ge=0)
    width: float = Field(gt=0, le=50000)
    height: float = Field(gt=0, le=50000)
    original: str
    layers: list[LayerElement] = Field(default_factory=list, max_length=20000)
    status: Literal['pending', 'ready', 'needs_review', 'error'] = 'pending'
    warnings: list[str] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def unique_layers(self):
        if len({x.id for x in self.layers}) != len(self.layers):
            raise ValueError('图层 ID 重复')
        return self


class ConvertRequest(Model):
    pages: list[int] = Field(min_length=1, max_length=500)
    overwrite: bool = False
    calibrate: bool = True


class SplitRequest(Model):
    method: Literal['auto', 'box', 'rectangle', 'point', 'brush', 'sam', 'backdrop'] = 'auto'
    box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    points: list[list[float]] = Field(default_factory=list, max_length=10000)
    radius: float = Field(default=12, gt=0, le=500)
    fill: Literal['transparent', 'local'] = 'local'


class CloudRequest(Model):
    provider: Literal['qwen', 'sam3', 'flux']
    layer_id: str
    reason: str = Field(min_length=5, max_length=2000)
    prompt: str = Field(default='', max_length=4000)
    box: list[float] = Field(min_length=4, max_length=4)
    mask_asset: str | None = None


class ImageRoleRequest(Model):
    role: Literal['logo','content']


class TextRepairRequest(Model):
    box: list[float] = Field(min_length=4,max_length=4)
    text: str = Field(min_length=1,max_length=4000)
    font: str = Field(default='Microsoft YaHei',min_length=1,max_length=200)
    font_size: float = Field(default=18,gt=0,le=1000)
    color: str = Field(default='#172033',pattern=r'^#[0-9a-fA-F]{6}$')

    @field_validator('text')
    @classmethod
    def nonempty_text(cls,value):
        if not value.strip():raise ValueError('请输入校正后的文字')
        return value


class SplitApplyRequest(Model):
    preview_job: str = Field(pattern=r'^[a-f0-9]{32}$')
    candidate_ids: list[int] = Field(min_length=1,max_length=64)
    name: str = Field(default='完整对象',max_length=120)

    @field_validator('candidate_ids')
    @classmethod
    def valid_candidates(cls,values):
        if any(v<0 for v in values) or len(set(values))!=len(values):raise ValueError('候选区域无效或重复')
        return values

