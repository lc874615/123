"""Bounded, persisted follow-up generation after a confirmed completed reply."""
import secrets,time
from image_prompts import ROLES

def configure(task):
 task.pop('sheet_layout',None)
 task.update(delivery_policy='independent_images',auto_image_retry=True)

def plan(task):
 attempt=(task.get('image_retry_attempts') or [{}])[-1]
 return {'sheet_layout':None,'expected_images':task.get('expected_images',8),'delivery_policy':'independent_images','auto_image_retry':True,'collection_expected':attempt.get('count',task.get('expected_images',8)),'collection_offset':attempt.get('offset',0),'recovery_marker':('【OZON_TASK:'+attempt['request_id']+'】') if attempt.get('request_id') else None}

def reserve(store,identifier,body):
 task=store.find(identifier)
 if store.control.get('paused') or task.get('pause_requested'):raise ValueError('制作已暂停，未补生成')
 if task['state'] not in ('claimed','sending','waiting'):raise ValueError('任务未在等待图片，未补生成')
 if body.get('reply_finished') is not True or body.get('no_collectable_result') is not True:raise ValueError('尚未确认回复完成及缺少可采集成图，未补生成')
 attempts=task.setdefault('image_retry_attempts',[]);previous=attempts[-1] if attempts else {}
 expected_marker='【OZON_TASK:'+str(previous.get('request_id') or task.get('source_request_id') or task['id'])+'】'
 if body.get('source_marker')!=expected_marker:raise ValueError('原回复标记不匹配或本次补图结果尚未确认，不重复发送')
 if len(attempts)>=2:raise ValueError('已自动补生成2次，仍无完整可采集图片；请检查作图额度、原对话及成图情况，已有图片保留')
 offset=len(task.get('received_images') or []);count=task.get('expected_images',8)-offset
 if count<=0:return {'done':True}
 request_id=task['id']+'-retry-'+secrets.token_hex(6)
 shared=task.get('kind')=='shared_details' or task.get('expected_images')==7;start=offset+(1 if shared else 0)
 roles=ROLES[start:start+count]
 from image_prompts import DETAIL_STYLE,FIDELITY,MAIN_STYLE
 fidelity=FIDELITY.replace('本次附件中该变体的原始商品参考图','原任务已上传且对应当前变体的原始商品参考图').replace('历史对话、其他变体或AI生成图中的商品','其他商品历史对话、其他变体或AI生成图中的商品')
 prompt=('请继续本商品任务，上一回复已经结束但没有收齐可采集的独立成品。参考本对话预览中对应图片内容，保留相应商品、人物、背景、构图、文字与真实卖点，不改成简化目录版；参数有冲突时以本品原图及已提供真实参数为准。只补下列'+str(count)+'张独立3:4高清图片，每张至少750×1000。不要再次提供整套预览，不把多个海报合成一个图片，不只列文件名或虚假下载链接。使用图像生成能力实际产出各张图片，直接提供对应原图或独立下载文件，不用程序重画另一套。此次交付编号01至'+str(count).zfill(2)+'，按下列顺序逐一对应原位置，不修改已完成位置：'+'；'.join('%02d'%(i+1)+'：'+brief for i,(name,brief) in enumerate(roles))+'。以下只约束本次已列图片的风格，不增加交付数量：'+(MAIN_STYLE if len(roles)==1 and roles[0][0]=='01_main' else DETAIL_STYLE)+fidelity+'用户原补充：'+str(task.get('addition') or '无'))
 attempt={'request_id':request_id,'source_marker':expected_marker,'count':count,'offset':offset,'reserved_at':time.time(),'prompt':prompt}
 attempts.append(attempt);configure(task);task.update(state='waiting',message='回复已完成但成品缺失，自动补生成第'+str(len(attempts))+'次；已保存图片保留')
 if task.get('image_job'):store.image_jobs.save()
 else:store.save()
 return {'done':False,'prompt':prompt,'marker':'【OZON_TASK:'+request_id+'】','count':count,'offset':offset,'attempt':len(attempts)}
