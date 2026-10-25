import test from 'node:test';
import assert from 'node:assert/strict';
import {validate, checkSchema, InputError} from '../validation.mjs';
const schema={type:'object',properties:{id:{type:'integer',minimum:1},label:{type:'string',maxLength:8}},required:['id'],additionalProperties:false};
test('API payload valid and invalid with machine-readable errors',()=>{
 assert.equal(validate({schema,payload:{id:3}}).verdict,'PASS');
 for(const payload of [{id:'3'},{},{id:0},{id:1,x:true}]){
  const r=validate({schema,payload});assert.equal(r.verdict,'FAIL');assert.equal(r.errors.length,1);assert.ok(r.errors[0].code);assert.ok(r.errors[0].schema_path);
 }
});
test('reject dangerous and silently ignored schema features',()=>{
 for(const s of [{$ref:'https://example.com/a'},{$ref:'#'}, {pattern:'(a+)+$'},{anyOf:[true,false]},{format:'email'},{type:'nonsense'},{required:[1]},{minimum:'2'},{minItems:-1},{items:[]},{enum:[1,1]},{const:{x:1}}]) assert.throws(()=>validate({schema:s,payload:{}}),InputError);
});
test('bounds include primitive values; hostile keys and nesting rejected',()=>{
 assert.throws(()=>validate({schema:true,payload:Array(2048).fill(1)}),InputError);
 let p={};for(let i=0;i<20;i++)p={a:p};assert.throws(()=>validate({schema:true,payload:p}),InputError);
 assert.throws(()=>validate(JSON.parse('{"schema":true,"payload":{"__proto__":1}}')),InputError);
});
test('boolean schema and unicode length conform to schema semantics',()=>{
 assert.equal(validate({schema:true,payload:null}).valid,true);
 assert.equal(validate({schema:false,payload:1}).valid,false);
 assert.equal(validate({schema:{type:'string',maxLength:1},payload:'😀'}).valid,true);
 assert.equal(validate({schema:{type:'array',items:{type:'boolean'}},payload:[true,0]}).valid,false);
});
