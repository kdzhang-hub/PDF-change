"""Find counterexamples to full coverage; never infer it from object counts."""
from pathlib import Path
import hashlib,json,argparse,re,collections
from pptx import Presentation

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'deliverables'/'v3-movement-20261028'
# Manually checked against the supplied first-page PDF. These are semantic
# title fragments, not every visible text region and not converter input.
TITLE=['以','代','码','回应一线','让','智','能','走进生活']
TITLE_BOX=[40,70,860,335]


def badge_text_complete(texts):
    normalized=''.join(texts).replace('溫','温').replace('學','学').upper()
    needed=collections.Counter('温州大学WENZHOUUNIVERSITY')
    return not (needed-collections.Counter(re.sub(r'\s+','',normalized)))


def preserved_brand_mark(scene):
    # Explicit user policy: this known university mark remains a whole image.
    # An arbitrary raster label or a cleaned bitmap is not an exemption.
    for layer in scene['layers']:
        if layer['kind']!='image' or layer.get('content_role')!='logo' or not layer['visible']:continue
        if not layer.get('asset') or layer['asset']!=layer.get('restoration_asset'):continue
        x=layer['x']+layer['width']/2;y=layer['y']+layer['height']/2
        if not (790<=x<=950 and 10<=y<=80):continue
        if any(child.get('parent_id')==layer['id'] for child in scene['layers']):continue
        return True
    return False


def text_shapes(shapes):
    for shape in shapes:
        if shape.shape_type==6:yield from text_shapes(shape.shapes)
        elif shape.has_text_frame and shape.text.strip():yield shape


def audit(folder):
    run=json.loads((folder/'run.json').read_text('utf-8'))
    scenes=json.loads((folder/'scenes.json').read_text('utf-8'))
    deck=Presentation(folder/'converted.pptx')
    first=list(text_shapes(deck.slides[0].shapes));title=[]
    left,top,right,bottom=TITLE_BOX
    for shape in first:
        x=(shape.left+shape.width/2)/12700;y=(shape.top+shape.height/2)/12700
        if left<=x<=right and top<=y<=bottom:title.append(shape.text)
    # Location matters: the same characters in the bottom label 人工智能
    # must never count as editable title characters 智 and 能.
    absent=[text for text in TITLE if not any(text in native for native in title)]
    logo=[]
    for shape in first:
        x=(shape.left+shape.width/2)/12700;y=(shape.top+shape.height/2)/12700
        if 760<=x<=950 and 10<=y<=100:logo.append(shape.text)
    logo_chinese_present=any(alias in native for alias in ('温州大学','溫州大學') for native in logo)
    badge=[]
    for shape in first:
        x=(shape.left+shape.width/2)/12700;y=(shape.top+shape.height/2)/12700
        if 790<=x<=842 and 15<=y<=74:badge.append(shape.text)
    badge_complete=badge_text_complete(badge)
    brand_preserved=preserved_brand_mark(scenes[0])
    edits=json.loads((folder/'font-edit-validation.json').read_text('utf-8-sig'))
    checks=('textChanged','fontChanged','sizeChanged','reopened')
    source=Path(run['source_pdf'])
    return {
        'case':folder.name,'project':run['project'],'pages_checked':run['pages'],
        'export_sha256':hashlib.sha256((folder/'converted.pptx').read_bytes()).hexdigest(),
        'source_unchanged_since_conversion':hashlib.sha256(source.read_bytes()).hexdigest()==run['source_sha256'],
        'native_text_objects':sum(1 for slide in deck.slides for _ in text_shapes(slide.shapes)),
        'prior_powerpoint_edit_checks':len(edits),
        'prior_powerpoint_edit_checks_passed':all(all(row[k] for k in checks) for row in edits),
        'first_page_title_native_text':title,'known_title_fragments_without_native_text':absent,
        'first_page_university_logo_native_text':logo,'university_logo_chinese_editable':logo_chinese_present,
        'first_page_circular_badge_native_text':badge,'circular_badge_small_text_editable':badge_complete,
        'university_brand_preserved_as_whole_image':brand_preserved,
        'brand_text_exception':'User requested intact brand marks on 2026-10-30; ordinary text still requires editable text',
        'all_visible_text_coverage_percent':None,
        'text_100_gate':'failed_known_counterexamples' if absent or (not brand_preserved and (not logo_chinese_present or not badge_complete)) else 'unverified',
        'decoration_coverage_percent':None,'decoration_100_gate':'unverified_no_complete_semantic_inventory',
        'image_layers_in_checked_pages':sum(l['kind']=='image' for s in scenes for l in s['layers']),
        'scope':'Existing conversion outputs re-inspected; no fresh conversion or Office edit replay in this audit',
    }


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',action='append');parser.add_argument('--output',default='coverage-audit-20261029.json');args=parser.parse_args()
    result={
        'targets':{'all_visible_text_editable':1.0,'independent_background_decoration_objects_editable':1.0},
        'text_pass_requires':['all ordinary text regions inventoried; explicitly preserved brand marks excluded','native editable text including small labels and artistic text',
            'change text font and size in PowerPoint','save and reopen','no old glyphs or effects after movement'],
        'decoration_pass_requires':['complete inventory of visible semantic objects','independent selection movement resizing deletion',
            'no duplicate object beneath','background reconstruction reviewed','save and reopen'],
        'denominator_rule':'Count original visible semantic objects, never extracted paint fragments or whole-page bitmap containers',
        'pptx_direct_import':'not_implemented_pdf_and_image_upload',
        'cases':[audit(BASE/name) for name in (args.case or ['ordinary-round-03','image-round-04'])],
        'overall_pass':False,
    }
    out=BASE/args.output
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
