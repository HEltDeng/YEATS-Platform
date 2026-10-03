"""Import only the explicitly YEATS-labelled desktop file; never echo secrets."""
from pathlib import Path
import os,re,sys,json,subprocess
root=Path(__file__).resolve().parents[1]
desktop=Path(subprocess.check_output(['powershell','-NoProfile','-Command',"[Environment]::GetFolderPath('Desktop')"],text=True).strip())
files=[p for p in desktop.glob('*.txt') if re.search(r'YEATS|叶芝|叶子',p.name,re.I)]
if len(files)!=1:raise SystemExit('Ambiguous or missing YEATS credential file; manual filename confirmation required')
raw=files[0].read_bytes()
for encoding in ['utf-8-sig','utf-16','gb18030']:
    try:
        value=raw.decode(encoding)
        if '\x00' not in value:break
    except UnicodeError:continue
appids=set(re.findall(r'\bwx[0-9a-fA-F]{16}\b',value))
secrets=set(re.findall(r'(?<![0-9a-zA-Z])[0-9a-fA-F]{32}(?![0-9a-zA-Z])',value))
if len(appids)!=1 or len(secrets)!=1:raise SystemExit('Credential structure ambiguous; no values printed or imported')
appid=appids.pop();secret=secrets.pop()
target=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets/wechat.dev.env'
if not target.parent.is_dir():raise SystemExit('Protected credential directory missing; run setup-secrets.ps1 first')
target.write_text('YEATS_WECHAT_APPID='+appid+'\nYEATS_WECHAT_SECRET='+secret+'\n',encoding='utf-8')
print(json.dumps({'found':True,'loaded_to_protected_file':True,'source_filename':files[0].name,'values_displayed':False},ensure_ascii=False))
