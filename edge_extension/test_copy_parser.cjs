const assert=require('node:assert/strict');require('./copy_parser.js');const p=global.OzonCopy.parse;
const v={title_ru:'Корзины',description_ru:'Материал — картон. {detail}',tags_ru:['#корзины'],missing_facts:[]};
assert.deepEqual(p('```json\n'+JSON.stringify(v)+'\n```'),v);
assert.deepEqual(p('prefix {bad} '+JSON.stringify(v)+' trailing {other}'),v);
assert.equal(p('{"title_ru":"partial"}'),null);
assert.equal(p('{"title_ru":"unfinished'),null);
console.log('4 JSON extraction cases passed');
function node(value){return {innerText:typeof value==='string'?value:JSON.stringify(value),textContent:typeof value==='string'?value:JSON.stringify(value),querySelectorAll:()=>[]};}
function doc(nodes){return {querySelectorAll:sel=>sel==='[data-message-author-role="assistant"]'?nodes:[]};}
const old=node({...v,sku:'OLD'}),fresh=node({...v,title_ru:'Новый'}),before=new Set([old]);
assert.deepEqual(global.OzonCopy.latest(doc([old,fresh]),{sku:'NEW(1)',before}),{...v,title_ru:'Новый',sku:'NEW(1)'});
assert.equal(global.OzonCopy.latest(doc([old]),{sku:'OLD',before}),null);
assert.equal(global.OzonCopy.latest(doc([fresh]),{sku:'NEW(1)'}),null);
assert.equal(global.OzonCopy.latest(doc([node({...v,sku:'WRONG'})]),{sku:'NEW(1)',before}),null);
const second={...v,sku:'SECOND'};
assert.deepEqual(global.OzonCopy.latest(doc([node(JSON.stringify({...v,sku:'FIRST'})+'\n'+JSON.stringify(second))]),{sku:'SECOND'}),second);
const excluded=new Set([JSON.stringify(v)]);
assert.equal(global.OzonCopy.latest(doc([node(v)]),{sku:'NEW',before:new Set(),exclude:excluded}),null);
console.log('6 reply isolation and task binding cases passed');

assert.deepEqual(global.OzonCopy.latest(doc([old,fresh]),{sku:'NEW',bindLatest:true}),{...v,title_ru:'Новый',sku:'NEW'});
assert.equal(global.OzonCopy.latest(doc([node({...v,sku:'NEW'}),node('unfinished')]),{sku:'NEW',bindLatest:true}),null);
console.log('2 explicit recovery cases passed');
