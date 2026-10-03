"""Run the existing local API; optional credential validation in the same process."""
from pathlib import Path
import os,sys
root=Path(__file__).resolve().parents[1]
os.chdir(root);sys.path.insert(0,str(root/'services/api'))
from yeats.main import app
if '--verify-wechat' in sys.argv:
    from yeats.wechat import wechat
    try:
        wechat.token()
        print('YEATS backend: protected WeChat credentials loaded; official token validation PASS.',flush=True)
    except Exception:
        print('YEATS backend: WeChat validation failed; no response body or secrets logged.',flush=True)
        raise SystemExit(1)
import uvicorn
uvicorn.run(app,host='127.0.0.1',port=8930,access_log=False)
