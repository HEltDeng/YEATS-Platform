import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from yeats.db import SessionLocal
from yeats.fixtures import seed
with SessionLocal() as db:seed(db)
print('Initialized controlled synthetic fixtures. No real student data imported.')
