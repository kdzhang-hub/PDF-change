from pathlib import Path
import json
import numpy as np
from PIL import Image
from backend.models import PageScene
import backend.text_shadows as shadows

folder=Path('deliverables/v3-movement-20261028/ordinary-round-02')
run=json.loads((folder/'run.json').read_text('utf-8'));scene=PageScene.model_validate(json.loads((folder/'scenes.json').read_text('utf-8'))[0])
original=shadows.fit_shadow;rows=[]
def trace(glyph,target,scale,font_size):
    fit=original(glyph,target,scale,font_size,min_agreement=0)
    index=len(rows);rows.append({'index':index,'score':fit[1] if fit else None,'shadow':fit[0].model_dump() if fit else None})
    Image.fromarray(glyph).save(f'work/shadow-glyph-{index}.png');Image.fromarray(target).save(f'work/shadow-target-{index}.png')
    return fit if fit and fit[1]>=.84 else None
shadows.fit_shadow=trace
_,accepted=shadows.restore_text_shadows(run['project'],scene)
Path('work/shadow-fit-diagnostic.json').write_text(json.dumps(rows,indent=2),'utf-8')
print(rows)
