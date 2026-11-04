"""Offline model adapters. No runtime download or cloud fallback is allowed here."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path
import numpy as np
from .store import ROOT

MODELS = ROOT / 'models'
_OCR_ENGINE=None
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK','True')
os.environ.setdefault('PADDLE_PDX_CACHE_HOME',str(MODELS/'cache'))
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
if Path('C:/Windows/Fonts/msyh.ttc').exists():
    os.environ.setdefault('PADDLE_PDX_LOCAL_FONT_FILE_PATH','C:/Windows/Fonts/msyh.ttc')


def manifest():
    path = MODELS / 'manifest.json'
    return json.loads(path.read_text('utf-8')) if path.exists() else {}


def status():
    m = manifest()
    return {
        'ocr': bool(importlib.util.find_spec('paddleocr')) and all((MODELS / m.get(k,'__missing__')).exists() for k in ('ocr_det','ocr_rec')),
        'sam': bool(importlib.util.find_spec('sam2')) and bool(m.get('sam_sha256')) and (MODELS / m.get('sam_checkpoint','__missing__')).is_file(),
        'note': '模型缺失时仍可使用原生 PDF、OpenCV 与手工遮罩；不会转交云端。',
    }


def visible_rgb(image,background=255):
    """Models must see the rendered cutout, never RGB hidden by alpha."""
    if image.ndim!=3 or image.shape[2] not in (3,4):
        raise ValueError('图像必须为 RGB 或 RGBA')
    if image.shape[2]==3:return image,np.ones(image.shape[:2],bool)
    alpha=image[:,:,3:4].astype(np.float32)/255
    rgb=np.round(image[:,:,:3]*alpha+np.asarray(background)*(1-alpha)).astype(np.uint8)
    return rgb,image[:,:,3]>0


def ocr_background(image):
    """Choose contrast from visible paint, excluding RGB concealed by alpha."""
    if image.shape[2]==4 and np.mean(image[:,:,3]<250)>.2:
        foreground=image[:,:,3]>32
        colors=image[:,:,:3][foreground]
        # Saturated outlines and glows can outnumber a white glyph's core and
        # pull its mean below the old threshold. Test visible bright cores too.
        bright_cores=bool(len(colors) and np.mean(colors.min(axis=1)>175)>=.12)
        if len(colors) and (colors.mean()>160 or bright_cores):return (28,35,48)
    return 255


def distinct_ocr_records(records):
    """Keep one owner for detections repeated by alternate contrast views."""
    selected=[]
    for index,record in sorted(enumerate(records),key=lambda item:item[1][1],reverse=True):
        poly=np.asarray(record[2]);low=poly.min(axis=0);high=poly.max(axis=0)
        area=float(np.prod(high-low));duplicate=False
        for _,other in selected:
            box=np.asarray(other[2]);a=box.min(axis=0);b=box.max(axis=0)
            intersection=float(np.prod(np.maximum(0,np.minimum(high,b)-np.maximum(low,a))))
            if intersection/max(1,min(area,float(np.prod(b-a))))>.75:
                duplicate=True;break
        if not duplicate:selected.append((index,record))
    return [record for _,record in sorted(selected,key=lambda item:item[0])]


def ocr(image: np.ndarray):
    global _OCR_ENGINE
    rgb,visible=visible_rgb(image,ocr_background(image))
    if not visible.any():return []
    if not status()['ocr']:
        raise RuntimeError('本地 PaddleOCR 未就绪：请运行模型安装脚本，不会自动上传')
    # PaddleOCR 3.x accepts explicitly provisioned model directories.
    m = manifest()
    def runtime_path(relative):
        source=MODELS/relative
        if os.name!='nt' or str(source).isascii(): return str(source)
        # Paddle's Windows C++ file APIs cannot open Unicode model paths.
        # Use a model-only mirror, never copy a user's document to this cache.
        target=Path(tempfile.gettempdir())/'layerdeck-models'/hashlib.sha256(str(MODELS).encode()).hexdigest()[:12]/relative
        target.mkdir(parents=True,exist_ok=True)
        for file in source.iterdir():
            if file.is_file() and (not (target/file.name).exists() or (target/file.name).stat().st_size!=file.stat().st_size):
                shutil.copy2(file,target/file.name)
        return str(target)
    if _OCR_ENGINE is None:
        from paddleocr import PaddleOCR
        _OCR_ENGINE = PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',
                       text_recognition_model_name='PP-OCRv5_mobile_rec',
                       text_detection_model_dir=runtime_path(m['ocr_det']),
                       text_recognition_model_dir=runtime_path(m['ocr_rec']),
                       use_doc_orientation_classify=False, use_doc_unwarping=False,
                       use_textline_orientation=False, device='cpu')
    views=[rgb]
    if image.shape[2]==4 and np.mean(image[:,:,3]<250)>.2:
        colors=image[:,:,:3][image[:,:,3]>32]
        if len(colors) and (colors.min(axis=1)>175).sum()>=6 and (colors.max(axis=1)<70).sum()>=6:
            alternate=(28,35,48) if isinstance(ocr_background(image),int) else 255
            views.append(visible_rgb(image,alternate)[0])
    result=[]
    for view in views:result.extend(_OCR_ENGINE.predict(view[:,:,::-1]))
    records = []
    for res in result:
        values = res.json
        if isinstance(values, str):
            values = json.loads(values)
        values = values.get('res', values)
        for text, score, poly in zip(values.get('rec_texts',[]), values.get('rec_scores',[]), values.get('rec_polys',[])):
            if text and score >= .4:
                records.append((text,float(score),np.array(poly,dtype=np.int32)))
    return distinct_ocr_records(records) if len(views)>1 else records


def quarter_turn_points(points, turns, width, height):
    """Map continuous coordinates from a rotated canvas back to its source."""
    points=np.asarray(points,dtype=float)
    if turns==0:return points.copy()
    if turns==1:return np.column_stack((width-points[:,1],points[:,0]))
    if turns==3:return np.column_stack((points[:,1],height-points[:,0]))
    raise ValueError('Only upright and quarter-turn OCR passes are supported')


def ocr_passes(image):
    """Supplement upright OCR with confident vertical-baseline text, locally.

    Records keep their upright-pass coordinates. Only the selected pass owns a
    region, so repeated detections cannot create duplicate movable text.
    """
    height,width=image.shape[:2]
    base=ocr(image)
    candidates=[]
    for turns in (1,3):
        for record in ocr(np.rot90(image,turns).copy()):
            text,score,poly=record
            mapped=quarter_turn_points(poly,turns,width,height)
            if score>=.90 and len(text.strip())>=2 and np.ptp(mapped[:,1])>np.ptp(mapped[:,0])*1.3:
                candidates.append((turns,record,mapped))
    def overlap(a,b):
        low=np.maximum(a.min(axis=0),b.min(axis=0));high=np.minimum(a.max(axis=0),b.max(axis=0))
        intersection=float(np.prod(np.maximum(0,high-low)))
        area_a=float(np.prod(np.ptp(a,axis=0)));area_b=float(np.prod(np.ptp(b,axis=0)))
        return intersection/max(1,area_a+area_b-intersection)
    chosen=[]
    for item in sorted(candidates,key=lambda item:item[1][1],reverse=True):
        if not any(overlap(item[2],other[2])>.4 for other in chosen):chosen.append(item)
    base=[record for record in base if not any(overlap(np.asarray(record[2]),item[2])>.4 for item in chosen)]
    return [(0,base)]+[(turns,[item[1] for item in chosen if item[0]==turns]) for turns in (1,3) if any(item[0]==turns for item in chosen)]


def sam_mask(image, box=None, points=None, automatic=False):
    rgb,visible=visible_rgb(image)
    if not visible.any():return []
    if os.name!='nt':
        return [np.asarray(mask,dtype=bool)&visible for mask in _sam_mask_inprocess(rgb,box,points,automatic)]
    # Paddle and PyTorch load incompatible Windows DLLs in the same process.
    # A fresh local process also releases GPU memory after every operation.
    with tempfile.TemporaryDirectory(prefix='layerdeck-sam-') as directory:
        folder=Path(directory)
        np.save(folder/'image.npy',rgb,allow_pickle=False)
        (folder/'request.json').write_text(json.dumps({'box':box,'points':points,'automatic':automatic}),'utf-8')
        try:
            result=subprocess.run([sys.executable,'-m','backend.sam_worker',str(folder)],cwd=ROOT,
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:raise RuntimeError('本地分割超时，原素材保留') from exc
        if result.returncode:
            log=ROOT/'work'/'sam-worker-error.log';log.parent.mkdir(exist_ok=True)
            log.write_text(result.stderr[-12000:],'utf-8')
            raise RuntimeError('本地分割进程失败，详情见 work 中的 sam-worker-error.log，未使用云端')
        with np.load(folder/'masks.npz',allow_pickle=False) as data:
            masks=[data[key].astype(bool) for key in data.files]
        if any(mask.shape!=image.shape[:2] for mask in masks):raise ValueError('分割结果尺寸不正确')
        return [mask&visible for mask in masks if np.any(mask&visible)]


def _sam_mask_inprocess(image, box=None, points=None, automatic=False):
    if not status()['sam']:
        raise RuntimeError('本地 SAM 2.1 未就绪：请安装固定权重，不会自动上传')
    from sam2.build_sam import build_sam2
    import torch
    m = manifest()
    checkpoint = MODELS / m['sam_checkpoint']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != m['sam_sha256']:
        raise RuntimeError('SAM 权重校验失败')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml', str(checkpoint), device=device, apply_postprocessing=False)
    try:
        with torch.inference_mode():
            if automatic:
                from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
                generator = SAM2AutomaticMaskGenerator(model, points_per_side=16, points_per_batch=8,
                    pred_iou_thresh=.86, stability_score_thresh=.94, min_mask_region_area=100)
                return [r['segmentation'] for r in generator.generate(image[:,:,:3])]
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            predictor = SAM2ImagePredictor(model)
            predictor.set_image(image[:,:,:3])
            masks,scores,_ = predictor.predict(box=np.array(box) if box else None,
                point_coords=np.array(points) if points else None,
                point_labels=np.ones(len(points),dtype=int) if points else None,
                multimask_output=True)
            return [masks[int(np.argmax(scores))]]
    finally:
        del model
        if device == 'cuda':
            torch.cuda.empty_cache()
