import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('monitor',Path(__file__).resolve().parents[1]/'ops/phoenix_monitor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MonitorTest(unittest.TestCase):
 def test_existing_seats_and_synthetic_usage_stay_separate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'crm.sqlite3';c=sqlite3.connect(p)
   c.executescript('CREATE TABLE phoenix_kv(key TEXT PRIMARY KEY,value TEXT,updated_at REAL);CREATE TABLE phoenix_instance(instance_id TEXT,slot TEXT,synthetic INTEGER,status TEXT);CREATE TABLE phoenix_event(instance_id TEXT,slot TEXT,kind TEXT,detail TEXT,evidence TEXT,synthetic INTEGER,at REAL);CREATE TABLE phoenix_opportunity(source TEXT,stage TEXT,synthetic INTEGER,summary TEXT);')
   c.executemany('INSERT INTO phoenix_instance VALUES(?,?,0,?)',[(str(i),slot,'HUNTING') for i,slot in enumerate(m.ROLES)])
   c.commit();before=c.execute('SELECT * FROM phoenix_instance').fetchall();c.close()
   def transport(url,token=None):
    if '/operator/events' in url:return {'events':[{'seq':1,'id':'test-receipt','client_id':'test-client','stage':'INVOCATION','source':'mcp_registry','synthetic':1,'valid':1,'elapsed_ms':1,'at':1000}]}
    if '/health' in url:return {'ok':True}
    return {'servers':[{'server':{'name':m.NAME,'version':'1.0.0'}}]}
   config={'enabled':True,'origin':'https://example.com','sync_token':'local'}
   r=m.run(config,p,transport,lambda:1000)
   self.assertNotIn('error',r);self.assertEqual(r['verified_external_users'],0);self.assertEqual(r['public_repeat_tokens'],0)
   c=sqlite3.connect(p);self.assertEqual(c.execute('SELECT * FROM phoenix_instance').fetchall(),before)
   self.assertEqual(c.execute('SELECT count(*) FROM phoenix_event').fetchone()[0],5)
   self.assertTrue(m.run(config,p,transport,lambda:1001)['throttled'])
   self.assertEqual(c.execute('SELECT count(*) FROM phoenix_payload_usage').fetchone()[0],1)
   c.close()
if __name__=='__main__':unittest.main()
