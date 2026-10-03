"""Read supplied files without editing originals. No workbook authoring."""
from pathlib import Path
import json, hashlib, zipfile, xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / '00_Reference-需求与原型'
DOC = ROOT / '01_Source-当前源码/docs'
ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
manifest = []
for f in REF.iterdir():
    manifest.append({'filename': f.name, 'bytes': f.stat().st_size, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'version': 'user attachment 2026-10-03'})
(DOC/'reference-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
with zipfile.ZipFile(next(REF.glob('*.xlsx'))) as z:
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        strings = [''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {x.attrib['Id']: x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    lines=[]
    for sh in wb.find('s:sheets', ns):
        target=rels[sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        lines.append('# '+sh.attrib['name'])
        for row in ET.fromstring(z.read(path)).findall('.//s:row', ns):
            cells=[]
            for c in row:
                v=c.find('s:v',ns)
                value=v.text if v is not None else ''.join(c.find('s:is',ns).itertext()) if c.find('s:is',ns) is not None else ''
                if c.attrib.get('t')=='s': value=strings[int(value)]
                if value: cells.append(c.attrib['r']+': '+value)
            if cells: lines.append(' | '.join(cells))
    (DOC/'requirements-extracted.txt').write_text('\n'.join(lines),encoding='utf-8')
    print('\n'.join(lines))
