"""One-way copy into EMPTY local PostgreSQL; preserve source SQLite unchanged."""
from pathlib import Path
import sys,json
from sqlalchemy import create_engine,select,func
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'services/api'))
from yeats.db import engine,Base
from yeats import models
if engine.url.host!='127.0.0.1' or engine.url.database!='yeats_development':raise SystemExit('Only independent local development destination allowed')
source=create_engine('sqlite:///'+str(root/'runtime/yeats-development.db'))
counts={}
with source.connect() as src,engine.begin() as dst:
    for table in Base.metadata.sorted_tables:
        if dst.scalar(select(func.count()).select_from(table)):raise SystemExit('Destination is not empty; no copy performed')
    for table in Base.metadata.sorted_tables:
        rows=[dict(r) for r in src.execute(select(table).order_by(table.c.created_at) if 'created_at' in table.c else select(table)).mappings()]
        if rows:dst.execute(table.insert(),rows)
        count=dst.scalar(select(func.count()).select_from(table))
        if count!=len(rows):raise RuntimeError('Row count mismatch')
        counts[table.name]=count
(root/'runtime/postgres-migration-counts.json').write_text(json.dumps(counts,indent=2),encoding='utf8')
print(json.dumps({'tables_verified':len(counts),'rows_preserved':sum(counts.values()),'source_sqlite_unchanged':True}))
