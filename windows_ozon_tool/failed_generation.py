"""Restart only a positively failed generation request, never a mere missing result."""
import json,re,time
from pathlib import Path
from pricing_service import read,write
from queue_restart import restart,ready

def explicit_failure(text):
 text=str(text or '')
 if re.search(r'限额|额度|验证码|登录|quota|rate limit|sign in',text,re.I):return False
 return bool(re.search(r'(?:主图|图片|图像|image|generation).{0,24}(?:生成失败|生成工具返回错误|生成工具.*错误|generation failed|generation error|failed to generate)|(?:图片|图像)生成失败',text,re.I|re.S)) and bool(re.search(r'未能交付|没有可用|无法生成|未生成|(?:没有|未能|未)生成.{0,12}(?:有效|成品|文件|图片)|暂时无法交付|无.*成品|no (?:image|output)|failed to generate',text,re.I))

def request(store,identifier,body):
 if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',identifier):raise ValueError('任务标记无效')
 receipt=store.folder/'automatic_restarts'/(identifier+'.json')
 if receipt.exists():return read(receipt)
 task=store.find(identifier)
 if body.get('reply_finished') is not True or body.get('no_images') is not True or body.get('collector_stopped') is not True or not explicit_failure(body.get('message')):raise ValueError('没有确认作图明确失败及采集已停止，未自动重启')
 from image_retry import plan
 marker=plan(task).get('recovery_marker') or '【OZON_TASK:'+task.get('source_request_id',task['id'])+'】'
 if body.get('marker')!=marker:raise ValueError('失败回复不属于当前任务，未自动重启')
 if task.get('received_images'):raise ValueError('本任务已有成图，先保留并采集现有结果，未自动重启')
 count=task.get('automatic_failure_restarts',0)
 if count>=2:raise ValueError('明确作图失败已自动重启2次，请核对作图服务/额度；未继续重发')
 pending=task.get('automatic_failure_pending')
 if not pending:
  if store.control.get('paused'):raise ValueError('用户已暂停制作，未自动重启')
  if task.get('state') not in ('claimed','sending','waiting'):raise ValueError('原任务不在作图阶段，未自动重启')
  store.set_paused(True);task.update(pause_ack=True,automatic_failure_pending={'serial':store.control['serial'],'created_at':time.time()},message='已确认作图工具失败，正在自动重启本条队列')
  store.save();pending=task['automatic_failure_pending']
 elif store.control.get('serial')!=pending['serial']:raise ValueError('期间制作控制已改变，取消自动重启，保留原任务')
 if time.time()-pending['created_at']>90:raise ValueError('自动重启等待停止确认超时，原队列和文件保留')
 if not ready(store,task):return {'pending':True,'message':'等待旧视频/其他任务停止确认后自动重启'}
 result=restart(store,identifier);fresh=store.find(result['id']);fresh.pop('automatic_failure_pending',None);fresh['automatic_failure_restarts']=count+1
 result.update(pending=False,restart_count=count+1)
 write(receipt,result);store.save()
 return result
