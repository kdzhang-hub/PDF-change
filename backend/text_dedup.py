"""Prefer visible PDF-native text over an OCR copy of its raster effects."""
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold() if c.isalnum())


def bounds(layer):
    return layer.source_ink_bbox or [layer.x,layer.y,layer.x+layer.width,layer.y+layer.height]


def redundant_ocr_text(scene):
    result=scene.model_copy(deep=True)
    native=[l for l in result.layers if l.kind=='text' and l.source in ('pdf-native','pdf-text-group') and not l.edited and not l.locked]
    removed=[];diagnostics=[]
    for candidate in result.layers:
        if candidate.kind!='text' or candidate.source not in ('local-ocr','local-ocr-font-fit') or candidate.edited or candidate.locked or candidate.rotation:continue
        text=normalized(candidate.text)
        if len(text)<2:continue
        a=bounds(candidate);height=max(1,a[3]-a[1]);width=max(1,a[2]-a[0]);matches=[]
        for layer in native:
            if layer.rotation:continue
            b=bounds(layer);other_height=max(1,b[3]-b[1])
            vertical=max(0,min(a[3],b[3])-max(a[1],b[1]))
            horizontal=max(0,min(a[2],b[2])-max(a[0],b[0]))
            if vertical/min(height,other_height)<.65 or horizontal<=0:continue
            if abs((a[1]+a[3]-b[1]-b[3])/2)>max(3,(height+other_height)*.3):continue
            matches.append(layer)
        matches.sort(key=lambda l:bounds(l)[0])
        if not matches or text not in normalized(''.join(l.text for l in matches)):continue
        intervals=sorted((max(a[0],bounds(l)[0]),min(a[2],bounds(l)[2])) for l in matches)
        covered=0;edge=a[0]
        for left,right in intervals:
            covered+=max(0,right-max(edge,left));edge=max(edge,right)
        if covered/width<.8:continue
        removed.append(candidate.id)
        for layer in matches:
            layer.needs_review=True
            layer.notes.append('相同位置的 OCR 重复文字已合并到此原生文字；原图效果仍需对照核验')
        diagnostics.append({'removed_id':candidate.id,'kept_ids':[l.id for l in matches],
                            'text':candidate.text,'horizontal_coverage':covered/width,'parent_id':candidate.parent_id})
    removed=set(removed);result.layers=[l for l in result.layers if l.id not in removed]
    if removed:result.warnings.append(f'{len(removed)} 个 OCR 效果层重复文字已合并到原生文字，需核对描边与阴影')
    return result,diagnostics
