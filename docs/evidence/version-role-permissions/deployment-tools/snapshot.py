"""Server-only read proof: no credentials or user/business row values emitted."""
import hashlib,json,re,sys
from pathlib import Path
from app.core.database import engine

def digest(rows):
    values=sorted(json.dumps(dict(r),sort_keys=True,ensure_ascii=False,default=str) for r in rows)
    return hashlib.sha256('\n'.join(values).encode()).hexdigest()
def decode(v): return v.decode() if isinstance(v,bytes) else v
out={'tables':{},'files':{},'roles':{},'links':[],'audits':{}}
with engine.connect() as c:
    c.exec_driver_sql('START TRANSACTION READ ONLY')
    out['database']=c.exec_driver_sql('SELECT DATABASE()').scalar()
    assert out['database']==sys.argv[1]
    out['version']=c.exec_driver_sql('SELECT VERSION()').scalar()
    out['head']=c.exec_driver_sql('SELECT version_num FROM alembic_version').scalar()
    out['triggers']=c.exec_driver_sql('SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE()').scalar()
    for table in c.exec_driver_sql('SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() ORDER BY table_name').scalars():
        assert re.fullmatch(r'[A-Za-z0-9_]+',table)
        rows=c.exec_driver_sql('SELECT * FROM `'+table+'`').mappings().all()
        out['tables'][table]={'count':len(rows),'sha256':digest(rows)}
        if table=='sys_role':
            for r in rows:
                stable={k:v for k,v in r.items() if k not in ('revision','updated_at','updated_by')}
                out['roles'][str(r['id'])]={'code':decode(r['code']),'revision':r['revision'],'stable':digest([stable]),'full':digest([r])}
        if table=='sys_role_permission':out['links']=sorted([r['role_id'],r['permission_id']] for r in rows)
        if table=='sys_permission':out['permissions']={decode(r['code']):r['id'] for r in rows}
        if table=='sys_operation_log':
            for r in rows:
                out['audits'][str(r['id'])]={'hash':digest([r]),'action':r['action'],'request_id':r['request_id'],'entity_id':r['entity_id'],'operator_id':r['operator_id']}
    c.rollback()
root=Path('/app/data/uploads')
for p in sorted(root.rglob('*')):
    if p.is_file():
        assert not p.is_symlink() and p.resolve().is_relative_to(root.resolve())
        out['files'][str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(out,sort_keys=True,default=str))
