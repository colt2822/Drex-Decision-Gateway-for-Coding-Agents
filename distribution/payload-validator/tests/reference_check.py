"""Compare the JS validator with Python jsonschema, with independently computed expected values."""
import itertools,json,subprocess
from pathlib import Path
from jsonschema import Draft202012Validator
schemas=[True,False,{'type':'integer','minimum':1}, {'type':'number','exclusiveMaximum':2}, {'type':['string','null'],'maxLength':2}, {'type':'array','items':{'type':'integer'},'minItems':1,'maxItems':3}, {'type':'object','properties':{'id':{'type':'integer','minimum':1}},'required':['id'],'additionalProperties':False}, {'enum':[1,True,None,'a']}, {'const':False}, {'type':'object','additionalProperties':{'type':'boolean'}}, {'type':'string','minLength':1,'maxLength':1}]
payloads=[None,False,True,-1,0,1,1.5,2,'','a','😀','abc',[],[1],[1,2,3,4],[1,'a'],{}, {'id':1},{'id':'1'},{'id':1,'x':1},{'x':True},{'x':False},{'x':0}]
cases=[{'schema':s,'payload':p} for s,p in itertools.product(schemas,payloads)]
expected=[Draft202012Validator(c['schema']).is_valid(c['payload']) for c in cases]
code="import {validate} from './validation.mjs';let s='';for await(const c of process.stdin)s+=c;process.stdout.write(JSON.stringify(JSON.parse(s).map(x=>validate(x).valid)));"
actual=json.loads(subprocess.check_output(['node','--input-type=module','-e',code],input=json.dumps(cases).encode()))
assert actual==expected, [(cases[i],expected[i],actual[i]) for i in range(len(cases)) if actual[i]!=expected[i]]
result={'independent_reference':'python jsonschema Draft202012Validator','cases':len(cases),'matches':len(actual),'all_passed':True}
Path('evidence/reference-check.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
