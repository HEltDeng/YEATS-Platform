from pathlib import Path
from bs4 import BeautifulSoup
import json
root=Path(__file__).resolve().parents[1]
soup=BeautifulSoup(next((root.parent/'00_Reference-需求与原型').glob('*.html')).read_text(encoding='utf-8'),'html.parser')
screens=[]
for s in soup.select('.phone-screen,.pc-screen'):
    screens.append({'id':s['id'],'text':s.get_text(' ',strip=True),'controls':[{'tag':x.name,'text':x.get_text(' ',strip=True),'attributes':dict(x.attrs)} for x in s.select('button,[data-goto],[data-open],[data-close],[data-tab],input,select,textarea,.nav-act,.p-more,.op')],'overlays':[x.get('id') for x in s.select('.overlay')]})
(root/'docs/prototype-inventory.json').write_text(json.dumps(screens,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'docs/prototype-styles.css').write_text(soup.style.string,encoding='utf-8')
for x in screens: print(x['id'],len(x['controls']),x['overlays'])
print('Screens:',len(screens),'controls:',sum(len(x['controls']) for x in screens))
