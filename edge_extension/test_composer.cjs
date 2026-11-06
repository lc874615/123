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
