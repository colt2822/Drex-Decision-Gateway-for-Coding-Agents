"""Synthetic clean environment acceptance using only public registry/GitHub + official MCP SDK.

Run from a newly created venv and an empty HOME; never counts as an external customer.
"""
import asyncio,json,os,subprocess,tempfile
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
 evidence={'synthetic':True,'independent_customer':False,'environment':{'empty_home':not any(Path.home().iterdir()),'mcp_sdk_only':True,'elyreon_tools_preinstalled':False}}
 assert evidence['environment']['empty_home']
 async with httpx.AsyncClient(timeout=12) as web:
  response=await web.get('https://registry.modelcontextprotocol.io/v0.1/servers',params={'search':'payload-validator'})
  response.raise_for_status();records=response.json()['servers']
  matches=[x['server'] for x in records if x['server']['name']=='co.com.elyraon/payload-validator']
  assert len(matches)==1
  manifest=matches[0];url=manifest['remotes'][0]['url'];base=url.rsplit('/',1)[0]
  evidence['directory_discovery']={'query':'payload-validator','name':manifest['name'],'version':manifest['version'],'endpoint_from_registry':url}
  home=Path.home();checkout=home/'checkout'
  subprocess.run(['git','clone','--depth','1',manifest['repository']['url']+'.git',str(checkout)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  source=checkout/manifest['repository']['subfolder']/'skills/elyreon-payload-validator/SKILL.md'
  target=home/'.agents/skills/elyreon-payload-validator/SKILL.md';target.parent.mkdir(parents=True);target.write_bytes(source.read_bytes())
  assert target.read_text().startswith('---\nname: elyreon-payload-validator')
  evidence['direct_installation']={'skill_installed':True,'git_commit':subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip(),'source':'anonymous public clone'}
  trial=await web.post(base+'/trial',json={'source':'mcp_registry','test':True});trial.raise_for_status();identity=trial.json();assert identity['synthetic']
  evidence['client_id']=identity['client_id']
  async with streamablehttp_client(url,headers={'Authorization':'Bearer '+identity['token']},timeout=15) as (read,write,_):
   async with ClientSession(read,write) as session:
    initialized=await session.initialize();tools=await session.list_tools()
    assert [t.name for t in tools.tools]==['validate_payload']
    evidence['connection']={'server':initialized.serverInfo.name,'protocol':initialized.protocolVersion,'tools':[t.name for t in tools.tools]}
    cases=[({'type':'integer','minimum':1},4,'PASS',False),({'type':'integer','minimum':1},'4','FAIL',False),({'$ref':'https://example.com/never-fetched'},1,'REJECTED',True),({'type':'integer'},5,'PASS',False)]
    results=[]
    for schema,payload,verdict,is_error in cases:
     r=await session.call_tool('validate_payload',{'schema':schema,'payload':payload})
     result=r.structuredContent
     assert result['verdict']==verdict and r.isError==is_error,(verdict,r)
     assert result['valid']==(verdict=='PASS')
     if verdict=='FAIL':assert result['errors'][0]['code']=='type'
     if verdict=='REJECTED':assert result['errors'][0]['code']=='unsupported_schema'
     results.append({'verdict':result['verdict'],'isError':r.isError,'receipt_id':result.get('receipt_id'),'errors':result['errors']})
    evidence['invocations']=results
  schema_response=await web.get(base+'/schemas/gateway-request.json');schema_response.raise_for_status()
  r=await web.post(base+'/validate',headers={'Authorization':'Bearer '+identity['token']},json={'schema':schema_response.json(),'payload':{'state':'Sanitized test context','question':{'type':'choice','instructions':'Choose tool','criteria':{'test':'Run tests'}}}})
  r.raise_for_status();assert r.json()['verdict']=='PASS'
  evidence['public_gateway_schema_reuse']={'verdict':r.json()['verdict'],'receipt_id':r.json()['receipt_id']}
  evidence['status']='PASS'
 print(json.dumps(evidence,indent=2))
asyncio.run(main())
