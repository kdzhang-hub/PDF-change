"""Normalize supported local files into the shared PDF/page pipeline."""
import io,json
from pathlib import Path
import fitz
from PIL import Image,ImageOps,UnidentifiedImageError

IMAGE_FORMATS={'PNG','JPEG','WEBP','TIFF','BMP'}


def imported_image_frame(project,index):
    """Read original image pixels, before a PDF backdrop can hide white paint."""
    from .store import project_dir
    folder=project_dir(project);record=folder/'import.json'
    if not record.exists():return None  # Older PDF-only projects have no record.
    metadata=json.loads(record.read_text('utf-8'))
    if metadata.get('kind')!='image':return None
    original=folder/'original-input.bin'
    if not original.is_file():raise ValueError('原始图片文件缺失，请重新导入；不能用白底预览替代原像素')
    try:
        with Image.open(original) as source:
            if source.format not in IMAGE_FORMATS:raise ValueError('原始图片格式已改变，请重新导入')
            if not 0<=index<getattr(source,'n_frames',1):raise ValueError('原始图片页数已改变，请重新导入')
            source.seek(index)
            if source.width*source.height>36_000_000:raise ValueError('单张图片超过3600万像素，请先缩小')
            image=ImageOps.exif_transpose(source).convert('RGBA')
            if list(image.size)!=metadata['frames'][index]['pixels']:
                raise ValueError('原始图片尺寸与导入记录不一致，请重新导入')
            return image
    except (UnidentifiedImageError,Image.DecompressionBombError,OSError) as exc:
        raise ValueError('原始图片无法读取，请重新导入') from exc


def normalize_input(data,name):
    if bytes(data[:1024]).lstrip().startswith(b'%PDF-') or Path(name).suffix.lower()=='.pdf':
        try:
            with fitz.open(stream=data,filetype='pdf') as document:
                if document.needs_pass:raise ValueError('请先解除 PDF 密码')
                if not 0<len(document)<=500:raise ValueError('需要 1 至 500 页文档')
                return bytes(data),{'kind':'pdf','pages':len(document)}
        except (fitz.FileDataError,RuntimeError) as exc:raise ValueError('文件不是可读取的 PDF') from exc
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in IMAGE_FORMATS:raise ValueError('支持 PDF、PNG、JPEG、WebP、TIFF 和 BMP')
            frames=getattr(source,'n_frames',1)
            if not 0<frames<=500:raise ValueError('图片需要 1 至 500 页')
            pixels=0;details=[]
            with fitz.open() as document:
                for index in range(frames):
                    source.seek(index)
                    if source.width*source.height>36_000_000:raise ValueError('单张图片超过3600万像素，请先缩小')
                    pixels+=source.width*source.height
                    if pixels>72_000_000:raise ValueError('这组图片总像素过大，请分批导入')
                    image=ImageOps.exif_transpose(source).convert('RGBA')
                    scale=min(1,960/max(image.size));width=image.width*scale;height=image.height*scale
                    page=document.new_page(width=width,height=height)
                    buffer=io.BytesIO();image.save(buffer,format='PNG')
                    page.insert_image(page.rect,stream=buffer.getvalue())
                    details.append({'pixels':[image.width,image.height],'page_points':[width,height]})
                return document.tobytes(deflate=True),{'kind':'image','format':source.format,'pages':frames,'frames':details}
    except (UnidentifiedImageError,Image.DecompressionBombError,OSError) as exc:
        raise ValueError('图片无法读取，请选择 PDF、PNG、JPEG、WebP、TIFF 或 BMP') from exc
