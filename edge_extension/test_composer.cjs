const assert=require('node:assert/strict');require('./composer.js');
function button({disabled=false,ariaDisabled=null,show=true,type='button',label=''}={}){return {disabled,type,textContent:'',getClientRects:()=>show?[{}]:[],getAttribute:k=>k==='aria-disabled'?ariaDisabled:k==='aria-label'?label:null};}
const form=items=>({querySelectorAll:()=>items});const editor=f=>({closest:()=>f});const doc=items=>({querySelectorAll:()=>items});const find=global.OzonComposer.findSend;
const hidden=button({show:false}),send=button({label:'发送'});
assert.equal(find(editor(null),doc([hidden,send])),send);
assert.equal(find(editor(null),doc([button({ariaDisabled:'true'})])),null);
const submit=button({type:'submit'});assert.equal(find(editor(form([submit])),doc([])),submit);
assert.equal(find(editor(form([submit,button({type:'submit'})])),doc([])),null);
assert.equal(find(editor(null),doc([])),null);
console.log('5 composer selector cases passed');
const test=require('node:test');
test('copy waits for a delayed enabled send button',async()=>{
 let clock=0,ticks=0;const send=button({disabled:true});const result=await global.OzonComposer.waitSend(editor(null),{doc:doc([send]),now:()=>clock,sleep:async ms=>{clock+=ms;if(++ticks===3)send.disabled=false;},timeout:2000});assert.equal(result,send);assert.equal(ticks,3);
});
test('copy send wait respects pause and expires without clicking',async()=>{
 let clock=0;assert.equal(await global.OzonComposer.waitSend(editor(null),{doc:doc([]),now:()=>clock,sleep:async ms=>clock+=ms,timeout:500}),null);await assert.rejects(global.OzonComposer.waitSend(editor(null),{doc:doc([]),stopped:()=>true}),/暂停/);
});
test('only the exact previous unsent prompt may be replaced',()=>{
 assert.equal(global.OzonComposer.sameDraft('【OWN】\r\ntext','【OWN】\ntext'),true);assert.equal(global.OzonComposer.sameDraft('【OWN】\ntext edited','【OWN】\ntext'),false);assert.equal(global.OzonComposer.sameDraft('unrelated',''),false);
});
