import { Validator } from '@cfworker/json-schema';

export const LIMITS = { bytes: 32768, depth: 12, values: 2048, schemas: 128, errors: 1, read_ms: 3000 };
export class InputError extends Error {
  constructor(code, message, status = 400) { super(message); this.code = code; this.status = status; }
}
const bad = (message) => { throw new InputError('unsupported_schema', message); };
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const own = (v, k) => Object.hasOwn(v, k);
export function bound(value) {
  const todo = [[value, 0]]; let n = 0;
  while (todo.length) {
    const [v, d] = todo.pop();
    if (++n > LIMITS.values || d > LIMITS.depth) throw new InputError('input_limit', 'Maximum 2048 values and depth 12', 413);
    if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) {
      if (['__proto__', 'constructor', 'prototype'].includes(k)) throw new InputError('unsafe_key', 'Reserved object key');
      todo.push([x, d + 1]);
    }
  }
}
const keywords = new Set(['$schema','title','description','type','properties','required','additionalProperties','items','enum','const','minimum','maximum','exclusiveMinimum','exclusiveMaximum','minLength','maxLength','minItems','maxItems','minProperties','maxProperties']);
const types = new Set(['object','array','string','number','integer','boolean','null']);
export function checkSchema(schema) {
  const todo = [schema]; let n = 0;
  while (todo.length) {
    const s = todo.pop();
    if (++n > LIMITS.schemas) bad('Maximum 128 schema nodes');
    if (typeof s === 'boolean') continue;
    if (!object(s)) bad('Each schema must be an object or boolean');
    for (const [k, v] of Object.entries(s)) {
      if (!keywords.has(k)) bad(`Unsupported keyword: ${k}. References, regex, formats and combinators are disabled.`);
      if (k === '$schema' && v !== 'https://json-schema.org/draft/2020-12/schema') bad('Only draft 2020-12 is accepted');
      if (['title','description'].includes(k) && typeof v !== 'string') bad(`${k} must be a string`);
      if (k === 'type' && !(types.has(v) || (Array.isArray(v) && v.length > 0 && new Set(v).size === v.length && v.every(t=>types.has(t))))) bad('Invalid type');
      if (k === 'properties') {
        if (!object(v)) bad('properties must be an object');
        todo.push(...Object.values(v));
      }
      if (k === 'required' && !(Array.isArray(v) && v.every(x=>typeof x==='string') && new Set(v).size === v.length)) bad('required must be unique strings');
      if (k === 'items' || k === 'additionalProperties') todo.push(v);
      if (k === 'enum' && !(Array.isArray(v) && v.length > 0 && v.length <= 32 && v.every(x=>x===null || ['string','number','boolean'].includes(typeof x)) && new Set(v.map(x=>JSON.stringify(x))).size === v.length)) bad('enum must contain 1-32 unique scalar values');
      if (k === 'const' && !(v===null || ['string','number','boolean'].includes(typeof v))) bad('const must be scalar');
      if (/^(minimum|maximum|exclusiveMinimum|exclusiveMaximum)$/.test(k) && (typeof v !== 'number' || !Number.isFinite(v))) bad(`${k} must be finite numeric`);
      if (/^(min|max)(Length|Items|Properties)$/.test(k) && (!Number.isSafeInteger(v) || v < 0)) bad(`${k} must be a nonnegative integer`);
    }
  }
}
export function validate(input) {
  bound(input);
  if (!object(input) || !own(input, 'schema') || !own(input, 'payload') || Object.keys(input).some(k=>!['schema','payload'].includes(k))) throw new InputError('invalid_input', 'Expected exactly {schema, payload}');
  checkSchema(input.schema);
  const r = new Validator(input.schema, '2020-12', true).validate(input.payload);
  return { valid: r.valid, verdict: r.valid ? 'PASS' : 'FAIL', errors: r.errors.slice(-1).map(e=>({ code: e.keyword, instance_path: e.instanceLocation, schema_path: e.keywordLocation, message: e.error })), dialect: '2020-12-bounded', limitations: 'Supported keywords only; no refs, regex, formats, combinators, coercion, defaults or network access.' };
}
