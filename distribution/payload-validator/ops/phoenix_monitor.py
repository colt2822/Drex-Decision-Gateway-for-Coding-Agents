"""Read-only distribution monitoring inside the existing PHOENIX controller timer.

Writes additive observation tables and per-seat work records to the existing CRM.
Never sends outreach, calls inference, admits customers, or attests revenue.
"""
import json
import os
from pathlib import Path
import sqlite3
import time
import httpx

ROLES = {"PHOENIX-01": "CLOSER: conversion tracking", "PHOENIX-02": "BROKER: MCP and skill integrations",
         "PHOENIX-03": "BOUNTY HUNTER: payable technical work", "PHOENIX-04": "GUERRILLA: distribution",
         "PHOENIX-05": "OPPORTUNIST: agent demand"}
NAME = 'co.com.elyraon/payload-validator'

def get(url, token=None):
    headers={}
    if token: headers['Authorization']='Bearer '+token
    r=httpx.get(url,headers=headers,timeout=3)
    r.raise_for_status()
    if len(r.content)>500_000: raise ValueError('Response size exceeded')
    return r.json()

def run(config=None, db=None, transport=get, clock=time.time):
    config=config or json.loads((Path.home()/'.config/elyreon/payload-validator.json').read_text())
    if not config.get('enabled'): return {'enabled':False}
    db=db or Path(os.environ.get('PHOENIX_DB',Path.home()/'elyraon-revenue-hunter-20261015/data/crm.sqlite3'))
    c=sqlite3.connect(db,timeout=3);c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=3000')
    c.executescript('''CREATE TABLE IF NOT EXISTS phoenix_payload_usage(
      event_id TEXT PRIMARY KEY, client_id TEXT, stage TEXT NOT NULL, source TEXT NOT NULL,
      synthetic INTEGER NOT NULL, valid INTEGER, elapsed_ms REAL, at INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS ix_phoenix_payload_client ON phoenix_payload_usage(client_id,at);
      CREATE TABLE IF NOT EXISTS phoenix_payload_evidence(
      evidence_id TEXT PRIMARY KEY,kind TEXT NOT NULL,client_id TEXT,synthetic INTEGER NOT NULL,
      evidence TEXT NOT NULL,at REAL NOT NULL);''')
    def kv(key, value=None):
        key='payload_distribution:'+key
        if value is None:
            r=c.execute('SELECT value FROM phoenix_kv WHERE key=?',(key,)).fetchone()
            return json.loads(r[0]) if r else None
        c.execute('INSERT INTO phoenix_kv VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(key,json.dumps(value),clock()))
    if (kv('due') or 0)>clock(): return {'throttled':True}
    origin=config['origin']; result={'at':clock(),'outreach':'STOP preserved; no sender invoked','paid_enabled':False}
    try:
        rows=transport(origin+'/operator/events?after='+str(kv('cursor') or 0),config['sync_token'])['events']
        for r in rows:
            if r['stage'] not in ('TOKEN_ISSUED','CONNECTED','INVOCATION','REJECTED'): continue
            c.execute('INSERT OR IGNORE INTO phoenix_payload_usage VALUES(?,?,?,?,?,?,?,?)',
                      (r['id'],r['client_id'],r['stage'],r['source'],int(bool(r['synthetic'])),r['valid'],r['elapsed_ms'],r['at']))
        if rows:kv('cursor',max(r['seq'] for r in rows))
        result['imported_events']=len(rows)
        result['health']=transport(origin+'/health')['ok']
        registry=transport('https://registry.modelcontextprotocol.io/v0.1/servers?search=co.com.elyraon%2Fpayload-validator')
        result['registry_verified']=any(x['server']['name']==NAME and x['server']['version']=='1.0.1' for x in registry.get('servers',[]))
        result['usage']=[dict(r) for r in c.execute('SELECT stage,source,synthetic,count(*) events,count(DISTINCT client_id) clients FROM phoenix_payload_usage GROUP BY stage,source,synthetic')]
        result['public_repeat_tokens']=c.execute("SELECT count(*) FROM (SELECT client_id FROM phoenix_payload_usage WHERE synthetic=0 AND stage='INVOCATION' GROUP BY client_id HAVING count(*)>1)").fetchone()[0]
        result['verified_external_users']=c.execute("SELECT count(DISTINCT e.client_id) FROM phoenix_payload_evidence e JOIN phoenix_payload_usage u USING(client_id) WHERE e.kind='VERIFIED_EXTERNAL_IDENTITY' AND e.synthetic=0 AND u.synthetic=0 AND u.stage='INVOCATION'").fetchone()[0]
        result['verified_installations']=c.execute("SELECT count(DISTINCT client_id) FROM phoenix_payload_evidence WHERE kind='INSTALLATION' AND synthetic=0").fetchone()[0]
        result['verified_repeat_users']=c.execute("SELECT count(*) FROM (SELECT u.client_id FROM phoenix_payload_usage u WHERE u.synthetic=0 AND u.stage='INVOCATION' AND EXISTS (SELECT 1 FROM phoenix_payload_evidence e WHERE e.client_id=u.client_id AND e.synthetic=0 AND e.kind='VERIFIED_EXTERNAL_IDENTITY') GROUP BY u.client_id HAVING count(*)>1)").fetchone()[0]
        result['actual_external_installations']=None
        result['actual_external_users']=None
        result['observability']='Verified counts reflect admitted evidence only; unobserved installations and anonymous identity remain UNKNOWN.'
        result['verified_revenue_cents']=0 # Payments disabled. Never create phoenix_outcome rows.
        result['provider_inference_cost_usd']=0
        result['hosting_cost_usd']=None # Requires provider billing evidence; request counts are not invoices.
        result['attribution']='Token source is client-claimed; installation and identity require independent evidence.'
        c.execute('DELETE FROM phoenix_payload_usage WHERE at<?',(clock()-30*86400,))
        # Query existing demand feeds only; no scraping, messages, applications or claims.
        demand=[dict(r) for r in c.execute("SELECT source,stage,count(*) opportunities FROM phoenix_opportunity WHERE synthetic=0 AND (lower(summary) LIKE '%api%' OR lower(summary) LIKE '%validat%' OR lower(summary) LIKE '%agent%') GROUP BY source,stage")]
        for slot,role in ROLES.items():
            inst=c.execute("SELECT instance_id FROM phoenix_instance WHERE slot=? AND synthetic=0 AND status NOT IN ('SURVIVED','FAILED')",(slot,)).fetchone()
            if not inst: continue
            detail={'role':role,'owner_instance':inst[0],'at':clock(),'endpoint':origin}
            if slot=='PHOENIX-01':detail.update(usage=result['usage'],verified_external_users=result['verified_external_users'],verified_installations=result['verified_installations'],verified_repeat_users=result['verified_repeat_users'],verified_revenue_cents=0)
            elif slot=='PHOENIX-02':detail.update(interfaces=['MCP Streamable HTTP','Agent Skills','JSON HTTP'],next_action='Investigate observed integration failures' if any(x['stage']=='REJECTED' for x in result['usage']) else 'Await independent integration evidence')
            elif slot=='PHOENIX-03':detail.update(existing_demand=demand,next_action='Verify funding and eligibility in existing opportunity workflow before claiming work')
            elif slot=='PHOENIX-04':detail.update(registry_verified=result['registry_verified'],next_action='Monitor registry readback and service health')
            else:detail.update(existing_demand=demand,next_action='Compare independent public invocations and requested schema features')
            kv('work:'+slot,detail)
            c.execute('INSERT INTO phoenix_event(instance_id,slot,kind,detail,evidence,synthetic,at) VALUES(?,?,?,?,?,0,?)',(inst[0],slot,'PAYLOAD_DISTRIBUTION',role,json.dumps(detail),clock()))
        kv('last_tick',result);kv('due',clock()+900);c.commit()
        # Bounded retention runs only after durable local ingestion.
        if transport is get:
            r=httpx.post(origin+'/operator/maintenance',json={},headers={'Authorization':'Bearer '+config['sync_token']},timeout=3)
            r.raise_for_status()
    except Exception as e:
        result['error']=type(e).__name__+': '+str(e)[:160]
        kv('last_error',result);kv('due',clock()+900);c.commit()
    finally:c.close()
    return result

if __name__=='__main__': print(json.dumps(run()))
