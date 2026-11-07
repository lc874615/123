const assert=require('node:assert/strict');require('./copy_parser.js');const p=global.OzonCopy.parse;
const v={title_ru:'Корзины',description_ru:'Материал — картон. {detail}',tags_ru:['#корзины'],missing_facts:[]};
assert.deepEqual(p('```json\n'+JSON.stringify(v)+'\n```'),v);
assert.deepEqual(p('prefix {bad} '+JSON.stringify(v)+' trailing {other}'),v);
assert.equal(p('{"title_ru":"partial"}'),null);
assert.equal(p('{"title_ru":"unfinished'),null);
console.log('4 JSON extraction cases passed');
