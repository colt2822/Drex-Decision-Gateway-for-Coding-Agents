"""Local acceptance: exercise the actual workerd HTTP server and local D1."""
import json,urllib.request,urllib.error
from pathlib import Path
base='http://127.0.0.1:18741'
def call(path,body=None,token=None,headers=None):
 h={'Content-Type':'application/json',**(headers or {})}
 if token:h['Authorization']='Bearer '+token
 data=json.dumps(body).encode() if body is not None else None
 try:r=urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=h),timeout=6)
 except urllib.error.HTTPError as e:r=e
 return r.status,json.loads(r.read())
checks=[]
def check(name,cond):
 assert cond,name
 checks.append(name)
s,r=call('/trial',{'test':True,'source':'github'});check('test enrollment',s==201 and r['synthetic']);token=r['token']
s,r=call('/validate',{'schema':{'type':'integer'},'payload':3},token);check('pass',s==200 and r['verdict']=='PASS')
s,r=call('/validate',{'schema':{'type':'integer'},'payload':'3'},token);check('fail',s==200 and r['verdict']=='FAIL' and r['errors'][0]['code']=='type')
s,r=call('/validate',{'schema':{'$ref':'http://127.0.0.1'},'payload':{}},token);check('network reference rejected',s==400 and r['verdict']=='REJECTED')
s,r=call('/validate',{'schema':True,'payload':'x'*32768},token);check('byte limit',s==413)
s,r=call('/mcp',{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},token);check('MCP initialize',r['result']['protocolVersion']=='2025-06-18')
s,r=call('/mcp',{'jsonrpc':'2.0','id':2,'method':'tools/list'},token);check('MCP tool discovery',r['result']['tools'][0]['name']=='validate_payload')
s,r=call('/mcp',{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'validate_payload','arguments':{'schema':False,'payload':1}}},token);check('structured fail is completed check',r['result']['structuredContent']['verdict']=='FAIL' and not r['result']['isError'])
s,r=call('/mcp',{'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'validate_payload','arguments':{'schema':{'pattern':'x'},'payload':'x'}}},token);check('structured rejected is tool error',r['result']['structuredContent']['verdict']=='REJECTED' and r['result']['isError'])
s,r=call('/mcp',{'jsonrpc':'2.0','id':5,'method':'ping'},token,{'Origin':'https://evil.example'});check('origin rejection',s==403)
s,r=call('/operator/events');check('private telemetry',s==401)
s,r=call('/operator/events',headers={'Authorization':'Bearer local-only'});check('attribution and test exclusion',len(r['events'])>=6 and all(e['synthetic']==1 for e in r['events']))
for _ in range(20):s,r=call('/validate',{'schema':True,'payload':1},token)
check('enforced rate limit',s==429)
Path('evidence/local-http.json').write_text(json.dumps({'checks':checks,'passed':len(checks)},indent=2)+'\n');print('passed',len(checks),checks)
