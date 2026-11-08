"""One source of user-facing stage labels for local tasks and publication receipts."""
import time
from asset_state import pending
from listing_bundle import copy_complete

def stage(task,bundle,jobs):
 if bundle.get('image_regeneration_jobs'):return '图片重做与自动采集中（原图已备份）'
 if task.get('recollection_requested'):
  if task.get('state')=='waiting':return '自动采集已有图片：'+task.get('message','正在定位并下载')
  if task.get('resume_mode')=='inspect_only':return '等待自动定位原始图片（无需操作插件）'
 offer=task['sku'];job=next((j for j in jobs if offer in j.get('items',{})),None)
 if pending(bundle):
  review=bundle.get('asset_review') or {};validation=bundle.get('asset_validation') or {}
  if review.get('main') or review.get('gallery') or bundle.get('regeneration_pending'):return '图片待核对：'+'、'.join(validation.get('main_changes',[])+validation.get('gallery_changes',[])) if validation.get('main_changes') or validation.get('gallery_changes') else '图片待核对：外观参数已变化'
  return '整组文案待自动采集/更新'
 if job:
  item=job['items'][offer];state=job['state']
  if item.get('on_sale'):return '已上架'
  if state=='validation_failed' or item.get('import_state')=='failed':return '需修改：'+str(item.get('error_summary') or item.get('status') or job.get('message',''))
  if state in ('import_uncertain','local_changed'):return '需处理：'+job.get('message','')
  if state not in ('cancelled_followup','rejected','failed','superseded'):
   return ('等待较久：' if job.get('needs_attention') else '')+(item.get('status') or job.get('message','上架处理中'))
 if task.get('state')=='cancelled':return '已停止制作'
 if task.get('state')=='queued':return '排队中'
 if task.get('state') in ('claimed','sending','waiting'):return '作图与采集中'
 if task.get('state')=='needs_attention':return '需处理：'+task.get('message','请检查作图页')
 if not task.get('video'):
  if len(task.get('received_images') or [])!=8:return '等待图片'
  return '文案生成中 · 视频合成中' if task.get('copy_state')=='running' else '合成视频中'
 if not copy_complete(bundle.get('copy')):return '文案处理中'
 if not (bundle.get('category') or {}).get('confirmed'):return '待确认类目'
 if not bundle.get('price_cny'):return '待补充定价资料'
 if (bundle.get('hosting') or {}).get('state')!='done' or (bundle.get('video_hosting') or {}).get('state')!='done':return '托管上传中'
 if job and job['state']=='cancelled_followup':return '上架跟进已停止'
 if job and job['state'] in ('rejected','failed'):return '需修改：'+job.get('message','')
 return '待预览提交'

def group_summary(stages):
 total=len(stages);done=sum(x=='已上架' for x in stages);issues=sum(x.startswith(('需','素材待','图片待核对')) for x in stages)
 if done==total and total:return '整组已上架'
 if done:return f'已上架 {done}/{total}'+(f' · 需处理 {issues}' if issues else ' · 其余处理中')
 if issues:return f'需处理 {issues}/{total}'
 return '待预览提交' if stages and all(x=='待预览提交' for x in stages) else '处理中'

def wait_details(job):
 now=time.time();start=job.get('last_progress_at') or job.get('created_at') or now;last=job.get('last_success_at')
 text='无进展 '+str(max(0,int(now-start)))+'秒'
 if last:text+=' · 上次成功查询 '+time.strftime('%H:%M:%S',time.localtime(last))
 return text
