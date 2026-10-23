from pathlib import Path
import sys
sys.argv=['upgrade.py','test']
p=Path('/opt/iterflow/upgrade-evidence/version-roles-198f831/upgrade.py')
exec(compile(p.read_text().split('oldenv=')[0],str(p),'exec'))
a=json.loads((BASE/'test-before.json').read_text());b=json.loads((BASE/'test-after.json').read_text());preservation=proof(a,b)
assert snapshot()==b
mounts=record(project+'-api-1')['mounts']
assert len(mounts)==2
u=next(m for m in mounts if m['Destination']=='/app/data/uploads');assert u['Type']=='volume' and u['Name']==project+'_uploads' and u['RW']
t=next(m for m in mounts if m['Destination']=='/run/iterflow/tls');assert t['Type']=='bind' and t['Source']==str(root/'tls') and not t['RW']
assert record(project+'-web-1')['mounts']==[]
v=json.loads(run(['docker','volume','inspect',project+'_uploads']))[0];assert v['CreatedAt'][:10]<'2026-10-23'
for name,old in s['baseline']['containers'].items():
 i=inspect(name);actual=' '.join([i['Id'],i['Image'],i['State']['StartedAt'],str(i['State']['Running']).lower()]);assert actual==old,name
assert hashlib.sha256(Path('/www/server/panel/vhost/nginx/sx-kc.xyz.conf').read_bytes()).hexdigest()==s['baseline']['vhost_sha256']
backups={}
for label in ('pre','post'):
 paths=list(Path('/opt/iterflow/backups').glob('version-roles-test-'+label+'-*'));assert len(paths)==1
 q=paths[0];m=json.loads((q/'manifest.json').read_text());assert m['source']==SOURCE and m['database']==database
 for n,d in m['sha256'].items():assert hashlib.sha256((q/n).read_bytes()).hexdigest()==d
 backups[label+'_backup']={'path':str(q),'sha256':m['sha256']}
old={x:record(project+'-'+x+'-1') for x in ('api','web')}
keep={n:record(n) for n in list(s['baseline']['containers'])+[project+'-db-1',project+'-redis-1']}
for n in (project+'-db-1',project+'-redis-1'):assert keep[n]['started'][:10]<'2026-10-23'
healthy()
run(cmd+['stop','web','api'])
for x in ('api','web'):run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','240',x])
healthy()
for x in ('api','web'):
 now=record(project+'-'+x+'-1');assert now['mounts']==old[x]['mounts'] and now['restart']==old[x]['restart']
assert {n:record(n) for n in keep}==keep
receipt=dict(source=SOURCE,mode='test',status='PASS',restart='PASS',preservation=preservation,mount_validation='Existing Compose volume and TLS targets, original volume creation date, before/after attachment digests, normalized mount equality through additional restart. Original pre-upgrade inspect was not persisted; initial assertion failure retained.',completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**backups)
write(BASE/'test-upgrade.json',receipt);print('TEST_UPGRADE_VERIFIED_PASS',json.dumps(preservation),flush=True)
