// Detect an explicit finished tool failure in the current request only.
(()=>{
 function inspect(doc,task,{marker,now=Date.now()}={}){
  const c=globalThis.OzonConversation;
  if(c.generating(doc)){task._failedReply=null;return null;}
  const replies=c.requestReplies(doc,marker);if(!replies?.length)return null;
  if(replies.some(r=>c.assistantImages(r).some(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512)))return null;
  if(replies.some(r=>[...(r.querySelectorAll?.('a[href],button,[role=link],[role=button]')||[])].some(n=>globalThis.OzonFiles?.allowedElement(n))))return null;
  const text=replies.map(r=>r.innerText||r.textContent||'').join('\n');
  if(/限额|额度|验证码|登录|quota|rate limit|sign in/i.test(text))return null;
  const failed=/(?:主图|图片|图像|image|generation)[\s\S]{0,24}(?:生成失败|生成工具返回错误|generation failed|generation error|failed to generate)|(?:图片|图像)生成失败/i.test(text);
  const absent=/未能交付|未能完成.{0,40}(?:图片|商品图|主图|详情图)|(?:暂时|目前)?无法提供.{0,80}(?:成品|下载链接)|没有可用|无法生成|未生成|(?:没有|未能|未)生成.{0,12}(?:有效|成品|文件|图片)|暂时无法交付|无.{0,8}成品|no (?:image|output)|failed to generate/i.test(text);
  if(!failed||!absent)return null;
  const signature=text.trim();if(task._failedReply?.signature!==signature){task._failedReply={signature,since:now};return null;}
  if(now-task._failedReply.since<3000)return null;
  return {marker,message:text.slice(0,1800),reply_finished:true,no_images:true};
 }
 function incomplete(doc,task,{marker}={}){
  const c=globalThis.OzonConversation;if(c.generating(doc))return null;
  const replies=c.requestReplies(doc,marker)||[];
  const last=[...replies].reverse().find(r=>(r.innerText||r.textContent||'').trim());if(!last)return null;
  const text=(last.innerText||last.textContent||'').trim();
  const missing=/(?:\d{1,2}\s*[—–至到-]\s*\d{1,2}|其余(?:图片|详情图)?|剩余(?:图片|详情图)?)[\s\S]{0,30}(?:未能|无法|尚未|未)[\s\S]{0,22}(?:生成|完成|交付)|(?:未能|无法|尚未)[\s\S]{0,20}(?:完成|生成|交付)[\s\S]{0,25}(?:全部|整套|其余|剩余)[\s\S]{0,12}(?:图片|成品|详情)|(?:本次|目前|最终)[，,\s]*(?:仅|只)(?:成功)?(?:生成|完成|交付)[\s\S]{0,12}(?:1|一)张/i.test(text);
  if(!missing)return null;
  const expected=Number(task.collection_expected||task.expected_images||8);
  if(expected===1&&!/拼图|联系表|不合格/.test(text))return null;
  return {message:'生成回复明确声明交付不完整：'+text.slice(0,900)+'；未把文件名或候选图数量当成整套合格，不自动补图或重发。',partial:true};
 }
 globalThis.OzonGenerationFailure={inspect,incomplete};
})();
