"""Explicitly scoped upgrade; no seed/restore/credential changes; Python 3.6 host."""
import hashlib,json,os,subprocess,sys,tarfile,time,traceback
from pathlib import Path
from urllib.request import urlopen
os.umask(0o077)
SOURCE='198f831d67e8b475975915b1824d711b949fb998'
BASE=Path('/opt/iterflow/upgrade-evidence/version-roles-198f831')
BUNDLE=BASE/'bundle'
STATE=Path('/opt/iterflow/acceptance-control/20261012/state.json')
s=json.loads(STATE.read_text());assert s['retention']['keep'] and s['cleanup_hold']
mode=sys.argv[1];assert mode in ('test','production')
root=Path(s['stage'] if mode=='test' else s['production_release_directory'])
project=s['project'] if mode=='test' else 'iterflow-mysql57'
database='iterflow_acceptance' if mode=='test' else 'iterflow'
assert root.parent==Path('/opt/iterflow/acceptance' if mode=='test' else '/opt/iterflow/releases')
assert root.is_dir() and not root.is_symlink()
cmd=['docker','compose','-p',project,'--env-file',str(root/'images.env'),'-f',str(root/'compose.yml')]
if mode=='test':cmd+=['-f',str(root/'acceptance.yml')]
log=BASE/(mode+'-commands.log')
def run(args,stdin=None,output=None):
    with log.open('ab') as f:
        r=subprocess.run(args,input=stdin,stdout=output or subprocess.PIPE,stderr=f,universal_newlines=output is None,timeout=900)
    if r.returncode:raise RuntimeError('Command failed; inspect protected '+str(log))
    return r.stdout if output is None else None

def write(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True));path.chmod(0o600)
def inspect(name):return json.loads(run(['docker','inspect',name]))[0]
def record(name):
    i=inspect(name)
    return {'id':i['Id'],'image':i['Image'],'started':i['State']['StartedAt'],'mounts':i['Mounts'],'restart':i['HostConfig']['RestartPolicy']}
def snapshot():return json.loads(run(cmd+['run','--rm','--no-deps','-T','api','python','-',database],stdin=(BASE/'snapshot.py').read_text()))
def backup(label):
    p=Path('/opt/iterflow/backups')/('version-roles-'+mode+'-'+label+'-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    p.mkdir(mode=0o700)
    for name,service in [('database.sql','client'),('uploads.tar','storage-backup')]:
        with (p/name).open('xb') as f:run(cmd+['--profile','ops','run','--rm','--no-deps','-T',service],output=f)
    sql=(p/'database.sql').read_bytes()
    assert len(sql)>1024 and b'CREATE TABLE' in sql and b'TRIGGER' in sql
    with tarfile.open(str(p/'uploads.tar')) as t:assert all(not m.name.startswith('/') and '..' not in m.name.split('/') for m in t)
    hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('database.sql','uploads.tar')}
    write(p/'manifest.json',{'database':database,'sha256':hashes,'source':SOURCE})
    (p/'SHA256SUMS').write_text(''.join(v+'  '+k+'\n' for k,v in sorted(hashes.items())))
    return {'path':str(p),'sha256':hashes}
def proof(a,b):
    assert a['head']=='mysql57_0005' and b['head']=='mysql57_0006'
    assert a['database']==b['database']==database and a['version']==b['version']
    assert a['triggers']==b['triggers']==73 and a['files']==b['files']
    assert set(a['tables'])==set(b['tables'])
    for t in a['tables']:
        if t not in ('sys_role','sys_role_permission','sys_operation_log','alembic_version'):assert a['tables'][t]==b['tables'][t],t
    assert a['permissions']==b['permissions'] and set(a['roles'])==set(b['roles'])
    wanted={a['permissions']['rd.version.'+x] for x in ('create','edit','status','publish')}
    links={tuple(x) for x in a['links']};changed=[]
    for rid,r in a['roles'].items():
        now=b['roles'][rid];assert r['stable']==now['stable']
        extra={(int(rid),p) for p in wanted}-links if r['code'] in ('DEVELOPER','PRODUCT_MANAGER','DEVELOPMENT_LEAD') else set()
        if extra:links|=extra;changed.append(int(rid));assert now['revision']==r['revision']+1
        else:assert now['full']==r['full']
    assert links=={tuple(x) for x in b['links']}
    for k,v in a['audits'].items():assert b['audits'][k]==v
    new=[v for k,v in b['audits'].items() if k not in a['audits']]
    assert sorted(v['entity_id'] for v in new)==sorted(changed)
    assert all(v['action']=='ROLE_PERMISSION_UPDATE' and v['request_id']=='migration-version-role-permissions-v1' and v['operator_id'] is None for v in new)
    return {'changed_roles':changed,'added_role_permissions':len(b['links'])-len(a['links']),'added_audits':len(new),'all_other_tables_and_files_unchanged':True}
def healthy():
    for service in ('api','web'):
        i=inspect(project+'-'+service+'-1');assert i['State']['Health']['Status']=='healthy'
        assert i['HostConfig']['RestartPolicy']['Name']=='unless-stopped'
    code="import json;from urllib.request import urlopen;h=json.load(urlopen('http://127.0.0.1:8000/health'));r=json.load(urlopen('http://127.0.0.1:8000/ready'));assert h['build_sha']=="+repr(SOURCE)+";assert h['status']==r['status']=='ok';print('HEALTH_READY_PASS')"
    run(['docker','exec',project+'-api-1','python','-c',code])
    if mode=='test':run(['systemctl','reload','iterflow-test-nginx'])
    with urlopen('https://sx-kc.xyz:'+('8444' if mode=='test' else '8443')+'/',timeout=30) as r:assert r.status==200
manifest=json.loads((BUNDLE/'manifest.json').read_text());assert manifest['source_commit']==SOURCE
images={i['tag']:i for i in manifest['images']}
api_tag='iterflow-api:mysql57-'+SOURCE[:12];web_tag='iterflow-web:mysql57-'+SOURCE[:12]
for tag in (api_tag,web_tag):
    i=json.loads(run(['docker','image','inspect',tag]))[0]
    assert i['Architecture']=='amd64' and i['Os']=='linux'
    # docker image IDs can be OCI index IDs locally; config + layers transferred separately.
    expected=json.loads((BASE/'image-identities.json').read_text())[tag]
    assert i['Id']==expected['config'] and i['RootFS']['Layers']==expected['layers']
gate=json.loads((BASE/'master-ci.json').read_text())
assert gate['headSha']==SOURCE and gate['conclusion']=='success' and len(gate['jobs'])==8 and all(j['conclusion']=='success' for j in gate['jobs'])
if mode=='production':
    assert json.loads((BASE/'test-upgrade.json').read_text())['status']=='PASS'
    assert json.loads((BASE/'acceptance.json').read_text())['status']=='PASS'
    assert json.loads((BASE/'browser-acceptance.json').read_text())['status']=='PASS'
result=BASE/(mode+'-upgrade.json');assert not result.exists()
oldenv=(root/'images.env').read_text();(BASE/(mode+'-images.env.before')).write_text(oldenv)
assert all(sum(l.startswith(k+'=') for l in oldenv.splitlines())==1 for k in ('API_IMAGE','WEB_IMAGE','BUILD_SHA'))
old={x:record(project+'-'+x+'-1') for x in ('api','web')}
for x in ('api','web'):
    lab=inspect(project+'-'+x+'-1')['Config']['Labels'];assert lab['com.docker.compose.project.working_dir']==str(root)
preserved=[project+'-redis-1','iterflow-production-redis']
if mode=='test':preserved+=['iterflow-mysql57-'+x+'-1' for x in ('api','web','redis')]+[project+'-db-1']
else:preserved+=[s['project']+'-'+x+'-1' for x in ('api','web','db','redis')]
base={n:record(n) for n in preserved}
vhost=Path('/www/server/panel/vhost/nginx/sx-kc.xyz.conf');vhost_hash=hashlib.sha256(vhost.read_bytes()).hexdigest()
receipt={'source':SOURCE,'mode':mode,'old':old,'preserved':base};migration_attempted=False
try:
    run(cmd+['stop','web','api'])
    before=snapshot();write(BASE/(mode+'-before.json'),before)
    assert before['head']=='mysql57_0005' and before['triggers']==73
    receipt['pre_backup']=backup('pre')
    replacements={'API_IMAGE':api_tag,'WEB_IMAGE':web_tag,'BUILD_SHA':SOURCE}
    lines=[]
    for line in oldenv.splitlines():
        key=line.split('=',1)[0]
        lines.append(key+'='+replacements[key] if key in replacements else line)
    newenv='\n'.join(lines)+'\n'
    (root/'images.env').write_text(newenv)
    run(cmd+['config','--quiet'])
    migration_attempted=True
    run(cmd+['--profile','init','run','--rm','--no-deps','-T','migrate'])
    after=snapshot();write(BASE/(mode+'-after.json'),after);receipt['preservation']=proof(before,after)
    run(cmd+['--profile','init','run','--rm','--no-deps','-T','migrate','python','-m','app.cli.mysql_preflight'])
    receipt['post_backup']=backup('post')
    run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','240','api'])
    run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','240','web'])
    healthy()
    run(cmd+['stop','web','api'])
    run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','240','api'])
    run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','240','web']);healthy()
    for service in ('api','web'):
        current=record(project+'-'+service+'-1')
        assert current['mounts']==old[service]['mounts'] and current['restart']==old[service]['restart']
    assert {n:record(n) for n in preserved}==base
    assert hashlib.sha256(vhost.read_bytes()).hexdigest()==vhost_hash
    receipt.update(status='PASS',restart='PASS',completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    write(result,receipt);print(mode.upper()+'_UPGRADE_PASS',json.dumps(receipt['preservation']),flush=True)
except Exception:
    (BASE/(mode+'-failure.txt')).write_text(traceback.format_exc())
    if not migration_attempted:
        (root/'images.env').write_text(oldenv)
        run(cmd+['start','api']);run(cmd+['start','web'])
    print('UPGRADE_STOPPED; no automatic downgrade or restore; inspect protected evidence',flush=True)
    sys.exit(1)
