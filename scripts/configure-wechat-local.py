"""Generate the ignored native project config from the protected local AppID."""
from pathlib import Path
import sys,json,os,re
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/api'))
from yeats.config import settings
if not re.fullmatch(r'wx[0-9a-fA-F]{16}',settings.wechat_appid):raise SystemExit('Valid local YEATS AppID required')
directory=root.parent/'YEATS-Parent'
config=json.loads((directory/'project.config.template.json').read_text(encoding='utf-8-sig'))
if config['projectname']!='YEATS-叶芝英语':raise SystemExit('Project identity mismatch')
config['appid']=settings.wechat_appid
(directory/'project.config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('YEATS local AppID injected. AppSecret excluded from native configuration. Values not displayed.')
