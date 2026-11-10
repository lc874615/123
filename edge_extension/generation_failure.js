// Detect an explicit finished tool failure in the current request only.
(()=>{
 function inspect(doc,task,{marker,now=Date.now()}={}){
  const c=globalThis.OzonConversation;
  if(c.generating(doc)){task._failedReply=null;return null;}
  if(globalThis.__ozonDeliveryInfo?.fileCount>0)return null;
  const replies=c.requestReplies(doc,marker);if(!replies?.length)return null;
  if(replies.some(r=>c.assistantImages(r).some(i=>i.complete&&i.naturalWidth>=512&&i.naturalHeight>=512)))return null;
  const text=replies.map(r=>r.innerText||r.textContent||'').join('\n');
  if(/限额|额度|验证码|登录|quota|rate limit|sign in/i.test(text))return null;
  const failed=/(?:主图|图片|图像|image|generation)[\s\S]{0,24}(?:生成失败|生成工具返回错误|generation failed|generation error|failed to generate)|(?:图片|图像)生成失败/i.test(text);
  const absent=/未能交付|没有可用|无法生成|未生成|无.{0,8}成品|no (?:image|output)|failed to generate/i.test(text);
  if(!failed||!absent)return null;
  const signature=text.trim();if(task._failedReply?.signature!==signature){task._failedReply={signature,since:now};return null;}
  if(now-task._failedReply.since<3000)return null;
  return {marker,message:text.slice(0,1800),reply_finished:true,no_images:true};
 }
 globalThis.OzonGenerationFailure={inspect};
})();
