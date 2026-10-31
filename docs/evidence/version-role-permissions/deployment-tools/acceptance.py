"""Live HTTP multi-account acceptance, exclusively the retained test database."""
import json,uuid,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from app.core.database import engine
with engine.connect() as db:
 assert db.exec_driver_sql('SELECT DATABASE()').scalar()=='iterflow_acceptance'
 assert db.exec_driver_sql('SELECT version_num FROM alembic_version').scalar()=='mysql57_0006'
env=dict(l.split('=',1) for l in Path('/tmp/version-role-tests.env').read_text().splitlines() if '=' in l)
BASE='http://web:8080/api/v1';suffix=uuid.uuid4().hex[:6];checks=[];objects=[];accounts=[]
def call(method,path,token=None,data=None,expected=200):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 req=Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
 try:
  with urlopen(req,timeout=40) as r:status=r.status;raw=r.read()
 except HTTPError as e:status=e.code;raw=e.read()
 assert status==expected,method+' '+path+' expected '+str(expected)+' got '+str(status)
 return json.loads(raw) if raw else None
def login(name,password='ceshi123'):return call('POST','/auth/login',data={'username':name,'password':password})
def passed(name):checks.append(name);print('PASS',name,flush=True)
admin=login(env['INIT_ADMIN_USERNAME'],env['ITERFLOW_BROWSER_NEW_PASSWORD'])['access_token']
roles={r['code']:r['id'] for r in call('GET','/roles',admin)}
users=call('GET','/users?page_size=100',admin)['items'];used={u['username'] for u in users}
def create(code):
 existing=next((u for u in users if u['display_name']=='发版验收-'+code),None)
 if existing:
  assert existing['role_ids']==[roles[code]]
  token=login(existing['username'])['access_token'];me=call('GET','/auth/me',token)
  assert set(me['permission_codes']) >= {'rd.version.'+x for x in ('view','create','edit','status','publish')}
  assert me['data_scope']==('ALL' if code=='PRODUCT_MANAGER' else 'SELF')
  accounts.append({'username':existing['username'],'id':existing['id'],'role':code})
  return existing['id'],token,existing['username']
 number=14
 while 'ceshi%03d'%number in used:number+=1
 name='ceshi%03d'%number;used.add(name)
 u=call('POST','/users',admin,{'username':name,'display_name':'发版验收-'+code,'password':'ceshiInitial123','role_ids':[roles[code]]})
 pair=login(name,'ceshiInitial123');assert pair['must_change_password']
 call('GET','/versions',pair['access_token'],expected=403)
 pair=call('POST','/auth/change-password',pair['access_token'],{'current_password':'ceshiInitial123','new_password':'ceshi123'})
 token=pair['access_token'];me=call('GET','/auth/me',token)
 assert set(me['permission_codes']) >= {'rd.version.'+x for x in ('view','create','edit','status','publish')}
 assert me['data_scope']==('ALL' if code=='PRODUCT_MANAGER' else 'SELF')
 accounts.append({'username':name,'id':u['id'],'role':code})
 return u['id'],token,name
actors=[(code,*create(code)) for code in ('DEVELOPER','PRODUCT_MANAGER','DEVELOPMENT_LEAD')]
devs=[]
for name in ('ceshi008','ceshi009'):
 token=login(name)['access_token'];devs.append((call('GET','/auth/me',token)['id'],token))
member=login('ceshi012')['access_token']
passed('三类纯角色账号与首次改密、原数据范围')
foreign=call('POST','/versions',admin,{'version_no':'VR-foreign-'+suffix,'name':'范围隔离对照'})
for name in ('ceshi001','ceshi007','ceshi010'):
 denied=login(name)['access_token']
 call('POST','/versions',denied,{'version_no':'denied-'+suffix,'name':'禁止创建'},expected=403)
 call('POST','/versions/%s/publish/check'%foreign['id'],denied,expected=403)
passed('成员、设计、测试角色不能创建或发布版本')
for code,uid,actor,name in actors:
 f=call('POST','/feedbacks',member,{'title':'角色发布反馈-'+code+'-'+suffix,'feedback_type':'NEW_FEATURE','description':'隔离测试环境，验证通知与上线同步'})
 f=call('PATCH','/feedbacks/%s/status'%f['id'],admin,{'status':'ACCEPTED','revision':f['revision']})
 r=call('POST','/feedbacks/%s/convert'%f['id'],admin,{'type':'CREATE_NEW','revision':f['revision'],'requirement_title':'完整发版-'+code+'-'+suffix,'requirement_type':'FEATURE','priority':'P1','description':'多角色完整发布验收'})
 rp='/requirements/%s'%r['id'];r=call('PATCH',rp,admin,{'owner_id':uid,'revision':r['revision']})
 v1=call('POST','/versions',actor,{'version_no':'VR-A-'+code+'-'+suffix,'name':'待迁移版本'})
 v2=call('POST','/versions',actor,{'version_no':'VR-B-'+code+'-'+suffix,'name':'完整版本流程'})
 vp='/versions/%s'%v2['id']
 if code!='PRODUCT_MANAGER':
  for method,path,data in [('GET','/versions/%s'%foreign['id'],None),('POST','/versions/%s/publish/check'%foreign['id'],None),('PATCH','/versions/%s'%foreign['id'],{'name':'越权','revision':foreign['revision']})]:call(method,path,actor,data,expected=404)
 else:call('GET','/versions/%s'%foreign['id'],actor)
 old=v2['revision'];v2=call('PATCH',vp,actor,{'name':'角色独立管理-'+code,'revision':old})
 call('PATCH',vp,actor,{'name':'过期编辑','revision':old},expected=409)
 call('POST','/versions/%s/requirements'%v1['id'],actor,{'requirement_id':r['id'],'revision':r['revision'],'version_revision':v1['revision']})
 r=call('GET',rp,admin)
 call('POST',vp+'/requirements/move',actor,{'requirement_id':r['id'],'revision':r['revision'],'version_revision':v2['revision'],'reason':'多角色迁移验收'})
 r=call('GET',rp,admin);v2=call('GET',vp,actor)
 call('DELETE',vp+'/requirements/%s'%r['id'],actor,{'revision':r['revision'],'version_revision':v2['revision'],'reason':'移出重加验收'})
 r=call('GET',rp,admin);v2=call('GET',vp,actor)
 call('POST',vp+'/requirements',actor,{'requirement_id':r['id'],'revision':r['revision'],'version_revision':v2['revision']})
 r=call('GET',rp,admin)
 r=call('POST',rp+'/start-stage',admin,{'status':'DEVELOPING','revision':r['revision'],'user_ids':[d[0] for d in devs]})
 r=call('PATCH',rp+'/status',admin,{'status':'TESTING','revision':r['revision']})
 v2=call('GET',vp,actor)
 for status in ('DEVELOPING','TESTING','READY'):v2=call('PATCH',vp+'/status',actor,{'status':status,'revision':v2['revision']})
 body={'released_at':datetime.now(timezone.utc).isoformat(),'release_notes':'真实多账号发版验收-'+code,'revision':v2['revision']}
 for count in (0,1):
  call('PATCH',rp+'/status',admin,{'status':'DONE','revision':r['revision']},expected=409)
  call('POST',vp+'/publish/check',actor,expected=409)
  call('POST',vp+'/publish',actor,body,expected=409)
  call('POST',rp+'/development-completion',devs[count][1],{'revision':r['revision']})
  r=call('GET',rp,admin)
 r=call('PATCH',rp+'/status',admin,{'status':'DONE','revision':r['revision']})
 call('POST',vp+'/publish/check',actor)
 call('POST',vp+'/publish',actor,dict(body,revision=1),expected=409)
 result=call('POST',vp+'/publish',actor,body)
 call('POST',vp+'/publish',actor,body,expected=409)
 assert call('GET',vp,actor)['status']=='RELEASED'
 assert call('GET',rp,admin)['status']=='ONLINE'
 assert call('GET','/feedbacks/%s'%f['id'],member)['status']=='ONLINE'
 notes=call('GET','/notifications',member)
 assert any(n['entity_id']==f['id'] and n['entity_type']=='FEEDBACK' for n in notes)
 with engine.connect() as db:
  assert db.exec_driver_sql('SELECT COUNT(*) FROM rd_release WHERE version_id=%s',(v2['id'],)).scalar()==1
  assert db.exec_driver_sql("SELECT COUNT(*) FROM sys_operation_log WHERE entity_type='VERSION' AND action='VERSION_PUBLISH' AND entity_id=%s AND operator_id=%s",(v2['id'],uid)).scalar()==1
  history=db.exec_driver_sql('SELECT active FROM rd_version_requirement WHERE requirement_id=%s ORDER BY id',(r['id'],)).scalars().all()
  assert list(history)==[0,0,1]
 objects.append({'role':code,'username':name,'version_id':v2['id'],'requirement_id':r['id'],'feedback_id':f['id']})
 passed(code+'：创建编辑、安排迁移移出重加、历史、状态、确认门禁、CAS、发布、通知审计')
receipt={'status':'PASS','source':'198f831d67e8b475975915b1824d711b949fb998','database':'iterflow_acceptance','transport':'live HTTP via deployed Web/API; no mocks','checks':checks,'accounts':accounts,'objects':objects}
Path('/tmp/version-role-acceptance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print('MULTI_ACCOUNT_ACCEPTANCE_PASS',json.dumps(receipt,ensure_ascii=False),flush=True)
