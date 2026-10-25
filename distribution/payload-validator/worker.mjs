import { validate, LIMITS, InputError } from './validation.mjs';
import server from './server.json' with { type: 'json' };
import skill from './skills/elyreon-payload-validator/SKILL.md';
import gatewaySchema from './gateway-request.schema.json' with { type: 'json' };
const enc = new TextEncoder();
const json = (v, status=200, extra={}) => new Response(JSON.stringify(v), {status,headers:{'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff',...extra}});
const fail = (code,message,status) => { throw new InputError(code,message,status); };
const sha = async s => [...new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(s)))].map(x=>x.toString(16).padStart(2,'0')).join('');
const now = () => Math.floor(Date.now()/1000);
export const TOOL = {name:'validate_payload',description:'Validate JSON API payload against a bounded JSON Schema 2020-12 subset. Deterministic PASS/FAIL, one structured error. No code execution or network access. Get a free token at POST /trial; 20 calls per token per day. Maximum 32 KiB, depth 12, 2048 values, 128 schema nodes. References, regex, formats and combinators rejected.',inputSchema:{type:'object',properties:{schema:{type:['object','boolean']},payload:{}},required:['schema','payload'],additionalProperties:false},annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:false}};
async function read(req) {
  if (!req.headers.get('content-type')?.startsWith('application/json')) fail('content_type','Use application/json',415);
  if (Number(req.headers.get('content-length')) > LIMITS.bytes) fail('input_limit','Maximum 32 KiB',413);
  const reader=req.body?.getReader(); if(!reader) fail('invalid_json','JSON body required',400);
  let timer; const chunks=[]; let size=0;
  try {
    await Promise.race([(async()=>{ while(true){ const {done,value}=await reader.read(); if(done) break; size+=value.length; if(size>LIMITS.bytes) fail('input_limit','Maximum 32 KiB',413); chunks.push(value); } })(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new InputError('read_timeout','Body read exceeded 3 seconds',408)),LIMITS.read_ms);})]);
  } catch(e) { void reader.cancel(); throw e; } finally {clearTimeout(timer);}
  const all=new Uint8Array(size); let offset=0; for(const c of chunks){all.set(c,offset);offset+=c.length;}
  try {return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(all));} catch{fail('invalid_json','Invalid UTF-8 JSON',400);}
}
async function quota(env, bucket, maximum, seconds=86400) {
  const expires=(Math.floor(now()/seconds)+1)*seconds;
  const r=await env.DB.prepare('INSERT INTO pv_quota VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET n=n+1 WHERE n < ? RETURNING n').bind(`${bucket}:${expires}`,expires,maximum).first();
  if(!r) fail('rate_limit','Free quota reached; retry next window',429);
}
async function log(env,c,stage,valid=null,elapsed=null,id=crypto.randomUUID()) {
  await env.DB.prepare('INSERT INTO pv_event(id,client_id,stage,source,synthetic,valid,elapsed_ms,at) VALUES(?,?,?,?,?,?,?,?)').bind(id,c?.id||null,stage,c?.source||'direct',c?.synthetic??0,valid,elapsed,now()).run();
}
async function client(req,env) {
  const t=req.headers.get('authorization')?.match(/^Bearer (pv_[a-f0-9]{64})$/)?.[1];
  if(!t) fail('token_required','POST /trial with JSON {"source":"mcp_registry"} for a free token',401);
  const c=await env.DB.prepare('SELECT * FROM pv_client WHERE token_hash=?').bind(await sha(t)).first();
  if(!c || c.created < now()-30*86400) fail('invalid_token','Token unknown or expired',401);
  return c;
}
async function invoke(req,env,input) {
  const c=await client(req,env);
  await quota(env,`call:${c.id}`,20); await quota(env,'global:calls',1000);
  const start=performance.now();
  try {
    const result=validate(input),receipt=crypto.randomUUID();
    await log(env,c,'INVOCATION',Number(result.valid),performance.now()-start,receipt);
    return {...result,receipt_id:receipt,client_id:c.id,charged_usd:0};
  } catch(e) {await log(env,c,'REJECTED',0,performance.now()-start);throw e;}
}
const errorResult=e=>({valid:false,verdict:'REJECTED',errors:[{code:e.code||'unavailable',message:e instanceof InputError?e.message:'Service unavailable'}]});
async function rpc(req,env,b) {
  if(!b || typeof b!=='object' || Array.isArray(b) || b.jsonrpc!=='2.0' || typeof b.method!=='string') return json({jsonrpc:'2.0',id:null,error:{code:-32600,message:'Invalid request'}},400);
  const id=b.id??null,ok=result=>json({jsonrpc:'2.0',id,result});
  if(b.id===undefined && b.method.startsWith('notifications/')) return new Response(null,{status:202});
  if(b.id===undefined) return json({jsonrpc:'2.0',id:null,error:{code:-32600,message:'Request id required'}},400);
  if(b.method==='initialize') {
    const c=await client(req,env); await log(env,c,'CONNECTED');
    const requested=b.params?.protocolVersion;
    return ok({protocolVersion:['2025-03-26','2025-06-18','2025-11-25'].includes(requested)?requested:'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'elyreon-payload-validator',version:'1.0.0'},instructions:TOOL.description});
  }
  if(b.method==='ping') return ok({});
  if(b.method==='tools/list') return ok({tools:[TOOL]});
  if(b.method==='tools/call') {
    if(b.params?.name!==TOOL.name) return json({jsonrpc:'2.0',id,error:{code:-32602,message:'Unknown tool'}});
    try {const r=await invoke(req,env,b.params.arguments);return ok({content:[{type:'text',text:JSON.stringify(r)}],structuredContent:r,isError:false});}
    catch(e){const r=errorResult(e);return ok({content:[{type:'text',text:JSON.stringify(r)}],structuredContent:r,isError:true});}
  }
  return json({jsonrpc:'2.0',id,error:{code:-32601,message:'Method not found'}});
}
export default {async fetch(req,env){
  try {
    const u=new URL(req.url),p=u.pathname;
    const ip=req.headers.get('cf-connecting-ip')||'local';
    if(!await env.EDGE_LIMIT.limit({key:ip}).then(x=>x.success)) fail('rate_limit','30 requests per minute per location',429);
    if(p==='/health' && req.method==='GET') return json({ok:true,capability:'validate_payload',version:'1.0.0',limits:LIMITS,paid_enabled:false});
    if(p==='/operator/events' && req.method==='GET') {
      if(!env.SYNC_TOKEN || req.headers.get('authorization')!==`Bearer ${env.SYNC_TOKEN}`) fail('unauthorized','Operator token required',401);
      const after=Number(u.searchParams.get('after')||0); if(!Number.isSafeInteger(after)||after<0) fail('invalid_cursor','Invalid cursor',400);
      return json({events:(await env.DB.prepare('SELECT * FROM pv_event WHERE seq>? ORDER BY seq LIMIT 500').bind(after).all()).results});
    }
    if(p==='/operator/maintenance' && req.method==='POST') {
      if(!env.SYNC_TOKEN || req.headers.get('authorization')!==`Bearer ${env.SYNC_TOKEN}`) fail('unauthorized','Operator token required',401);
      await env.DB.batch([env.DB.prepare('DELETE FROM pv_quota WHERE expires<?').bind(now()),env.DB.prepare('DELETE FROM pv_event WHERE at<?').bind(now()-30*86400),env.DB.prepare('DELETE FROM pv_client WHERE created<?').bind(now()-30*86400)]);
      return json({ok:true,retention_days:30});
    }
    if(p==='/trial' && req.method==='POST') {
      const b=await read(req); if(!b || Array.isArray(b) || typeof b!=='object') fail('invalid_input','Expected object',400);
      await quota(env,`enroll:${await sha(env.PRIVACY_SALT+ip)}`,5,3600);await quota(env,'global:enroll',100);
      const token='pv_'+crypto.randomUUID().replaceAll('-','')+crypto.randomUUID().replaceAll('-','');
      const sources=['mcp_registry','github','skill_directory','direct','other'];
      const c={id:crypto.randomUUID(),source:sources.includes(b.source)?b.source:'other',synthetic:Number(b.test===true || Boolean(env.TEST_TOKEN && req.headers.get('x-elyreon-test')===env.TEST_TOKEN))};
      await env.DB.prepare('INSERT INTO pv_client VALUES(?,?,?,?,?)').bind(c.id,await sha(token),c.source,c.synthetic,now()).run();
      await log(env,c,'TOKEN_ISSUED');return json({token,client_id:c.id,limits:{calls_per_day:20},expires_days:30,source_attribution:'client-claimed',synthetic:Boolean(c.synthetic)},201);
    }
    if(p==='/validate' && req.method==='POST') return json(await invoke(req,env,await read(req)));
    if(p==='/mcp') {
      const origin=req.headers.get('origin');if(origin && origin!==env.PUBLIC_ORIGIN) fail('origin_forbidden','Origin not allowed',403);
      if(req.method!=='POST') return json({error:'POST JSON-RPC required'},405,{allow:'POST'});
      return await rpc(req,env,await read(req));
    }
    if(req.method==='GET') {
      if(p==='/server.json') return json(server);
      if(p==='/schemas/gateway-request.json') return json(gatewaySchema);
      if(p==='/SKILL.md') return new Response(skill,{headers:{'content-type':'text/markdown; charset=utf-8'}});
      if(p==='/.well-known/ai-catalog.json') return json({name:'ELYREON Payload Validator',mcp:env.PUBLIC_ORIGIN+'/mcp',skill:env.PUBLIC_ORIGIN+'/SKILL.md',server:env.PUBLIC_ORIGIN+'/server.json',capabilities:[TOOL],payments_enabled:false});
      if(p==='/x402-bazaar.json') return json({status:'PREPARED_NOT_ACTIVE',x402Version:2,resource:{url:env.PUBLIC_ORIGIN+'/validate',description:TOOL.description,mimeType:'application/json'},accepts:[],extensions:{bazaar:{info:{input:{type:'http',method:'POST',bodyType:'json',body:{schema:{type:'object'},payload:{}}},output:{type:'json',example:{valid:true,verdict:'PASS',errors:[]}}}}},blockers:['No approved receiving wallet, price, network or settlement flow; no payment activation authorized']});
      if(p==='/') return json({name:'ELYREON Payload Validator',capability:TOOL,install:{mcp:env.PUBLIC_ORIGIN+'/mcp',skill:env.PUBLIC_ORIGIN+'/SKILL.md',trial:env.PUBLIC_ORIGIN+'/trial'},privacy:'No payloads or schemas stored. Token hash, client-claimed source, test flag, stage, outcome and latency retained 30 days. Cloudflare processes network metadata.',payments_enabled:false});
    }
    return json({error:'Not found'},404);
  }catch(e){return json(errorResult(e),e.status||503,e.status===429?{'retry-after':'3600'}:{});}
}};
