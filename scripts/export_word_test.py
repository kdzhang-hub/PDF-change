from pathlib import Path
import argparse,json,sys,zipfile,collections,hashlib
import httpx,fitz
from lxml import etree as E

parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args();folder=args.folder
run=json.loads((folder/'run.json').read_text('utf-8'))
with httpx.Client(base_url='http://127.0.0.1:8765',timeout=240,trust_env=False) as client:
    response=client.post('/api/projects/'+run['project']+'/export-docx',json={'pages':[page-1 for page in run['pages']]});response.raise_for_status()
    (folder/'converted.docx').write_bytes(response.content)
with zipfile.ZipFile(folder/'converted.docx') as archive:
    document=E.fromstring(archive.read('word/document.xml'));text=''.join(document.xpath('//*[local-name()="txbxContent"]//*[local-name()="t"]/text()'))
with fitz.open(run['source_pdf']) as doc:expected=''.join(doc[page-1].get_text() for page in run['pages'])
normalize=lambda value:collections.Counter(c for c in value if not c.isspace())
stats={'native_textboxes':len(document.xpath('//*[local-name()="txbxContent"]')),'native_chars':sum(normalize(text).values()),'missing_pdf_chars':sum((normalize(expected)-normalize(text)).values()),'cloud_calls':run['cloud_calls_after']-run['cloud_calls_before']}
(folder/'docx-structure.json').write_text(json.dumps(stats,indent=2),'utf-8');print(stats)
