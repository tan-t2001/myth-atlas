"""Verify every visible image in the built content is local and decodable."""
import json
from pathlib import Path
from xml.etree import ElementTree
from PIL import Image

root=Path(__file__).resolve().parents[1]
bundle=(root/'dist/data/bundle.js').read_text(encoding='utf-8')
data=json.loads(bundle.removeprefix('window.MYTH_ATLAS_CONTENT=').rstrip(';\n'))
images=[image for part in ('china','core','others','cthulhu') for t in data[part] for image in t.get('images',[])]
images += [image for records in data['images'].values() for image in records]
images += [image for item in data['enrichment'].values() for image in item.get('images',[])]
errors=[]
paths={image.get('local','') for image in images}
for relative in paths:
    path=(root/'dist'/relative).resolve()
    try:
        if not relative or not path.is_relative_to((root/'dist').resolve()): raise ValueError('invalid local path')
        raw=path.read_bytes()
        if b'<svg' in raw[:1000]:
            svg=ElementTree.fromstring(raw)
            if not svg.tag.endswith('svg'): raise ValueError('not SVG')
        else:
            with Image.open(path) as img:
                if img.width<8 or img.height<8: raise ValueError('unexpected tiny image')
                img.verify()
    except Exception as error: errors.append({'file':relative,'error':str(error)})
report={'referenced_image_files':len(paths),'image_records':len(images),'errors':errors}
(root/'research/media-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
if errors: raise SystemExit(1)
