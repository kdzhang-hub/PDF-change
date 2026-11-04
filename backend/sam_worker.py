"""Isolate local PyTorch inference from Paddle's Windows DLLs."""
from pathlib import Path
import json,sys
import numpy as np
from .local_models import _sam_mask_inprocess


def run(folder):
    folder=Path(folder)
    image=np.load(folder/'image.npy',allow_pickle=False)
    if image.ndim!=3 or image.shape[2] not in (3,4):raise ValueError('Invalid image shape')
    request=json.loads((folder/'request.json').read_text('utf-8'))
    masks=_sam_mask_inprocess(image,**request)
    np.savez_compressed(folder/'masks.npz',**{f'mask_{i}':m for i,m in enumerate(masks)})


if __name__=='__main__':run(sys.argv[1])
