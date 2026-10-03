from pathlib import Path
import urllib.request,re,zipfile,hashlib,json
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]/'runtime/postgres-toolchain'
root.mkdir(parents=True,exist_ok=True)
html=urllib.request.urlopen('https://www.enterprisedb.com/download-postgresql-binaries').read().decode()
soup=BeautifulSoup(html,'html.parser')
version=soup.find(string=lambda x:x and x.strip().startswith('17.'))
links=[a['href'] for a in version.parent.parent.select('a[href]') if a.find('img',alt='Windows x86-64')] if version else []
if not links:raise SystemExit('No official PostgreSQL 17 binary link found')
url=links[0].replace('&amp;','&');print('Official binary URL:',url)
archive=root/'postgres.zip'
if not archive.exists():urllib.request.urlretrieve(url,archive)
print('Download bytes:',archive.stat().st_size)
with zipfile.ZipFile(archive) as z:
 for n in z.namelist():
  if n.startswith(('pgsql/bin/','pgsql/lib/','pgsql/share/')) and not n.endswith('/'):
   target=(root/n).resolve()
   if not target.is_relative_to(root.resolve()):raise RuntimeError('Invalid archive path')
   target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(n))
(root/'provenance.json').write_text(json.dumps({'url':url,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2))
print('Extracted PostgreSQL runtime only')
