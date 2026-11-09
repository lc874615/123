"""Explicit local queue restart with backups and fresh request identities."""
import copy,secrets,shutil,time
from pathlib import Path
from pricing_service import read,write

RUN_KEYS=('resume_mode','pause_requested','pause_ack','recollection_requested','recollection_backup','image_retry_attempts','sheet_layout','contact_sheet_sha256','contact_sheet_info','source_request_id','plans','video','generation_parameters','generation_variants')

def reset_fields(task):
 for key in RUN_KEYS:task.pop(key,None)
 task.update(id=secrets.token_hex(16),state='queued',auto_batch=True,received_images=[],message='本条队列已重启，等待自动领取',created_at=time.time())
 from image_retry import configure
 configure(task)
 return task

def choose(store,identifier):
 task=store.find(identifier)
 if task.get('image_job'):return task
 jobs=store.image_jobs.active([task['sku']])
 if len(jobs)>1:
  current=(getattr(store,'plugin_status',{}) or {}).get('task_id');matches=[j for j in jobs if j['id']==current]
  if len(matches)==1:return matches[0]
  running=[j for j in jobs if j['state'] in ('claimed','sending','waiting','processing','committing')]
  if len(running)==1:return running[0]
 if len(jobs)>1:raise ValueError('本变体有多个并行图片任务，请先在图片视频页核对并停止其他任务，再重启本条')
 return jobs[0] if jobs else task

def ready(store,task):
 skus=[t['sku'] for t in task['targets']] if task.get('image_job') else [task['sku']]
 related=[task]+[t for t in store.tasks if t['sku'] in skus]
 paused=store.tasks+(store.image_jobs.jobs if hasattr(store,'image_jobs') else [])
 if any(t.get('pause_requested') and not t.get('pause_ack') for t in paused):return False
 return not any(t.get('pause_requested') and not t.get('pause_ack') or t.get('copy_state')=='running' or t['sku'] in store.video_running for t in related)

def restart(store,identifier):
 target=choose(store,identifier)
 if not store.control.get('paused') or not ready(store,target):raise ValueError('等待插件停止确认和本地视频处理完成后再重启；原文件保留')
 if target['state'] in ('claimed','sending','waiting','committing','processing'):raise ValueError('原任务仍在处理，请等待停止确认')
 stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)
 backup=store.folder/'queue_restarts'/stamp;backup.mkdir(parents=True)
 skus=list(dict.fromkeys(t['sku'] for t in target['targets'])) if target.get('image_job') else [target['sku']]
 # Every backup must finish before the live queue, draft or assets change.
 write(backup/'queue_task.json',target)
 for sku in skus:
  source=store.folder/'products'/sku;dest=backup/sku;dest.mkdir()
  for name in ('images','video','image_manifest.json','listing_bundle.json','shared_copy.json','copy_prompt.txt'):
   path=source/name
   if path.is_dir():shutil.copytree(path,dest/name)
   elif path.exists():shutil.copy2(path,dest/name)
  product=next((t for t in store.tasks if t['sku']==sku),None)
  if product:write(dest/'task.json',product)
 staging=store.folder/'image_job_staging'/target['id']
 if target.get('image_job') and staging.exists():shutil.copytree(staging,backup/'staged_results')
 old_id=target['id'];fresh=reset_fields(copy.deepcopy(target));fresh.update(restarted_from=old_id,restart_backup=str(backup))
 if target.get('image_job'):
  jobs=store.image_jobs
  owner=jobs.product(target['sku']);leader=owner.get('copy_leader',owner['sku']);group=[t for t in store.tasks if t.get('copy_leader',t['sku'])==leader and t['state']!='cancelled']
  kind=target['kind']
  if kind=='asset_recollection':
   kind='shared_details' if target['expected_images']==7 else ('variant_main' if target['expected_images']==1 else 'full_set')
  fresh.update(id='image-'+fresh['id'],kind=kind,auto_batch=True,set_mode=True)
  fresh['references']=jobs.refs(group if kind=='shared_details' else [owner],'shared_details' if kind=='shared_details' else 'variant_main')
  if kind=='full_set':
   from image_prompts import generation_prompt
   fresh['prompt']=generation_prompt(owner['facts'],owner.get('group_facts',''),8)
  else:fresh['prompt']=jobs.prompt(owner['sku'],kind,target.get('addition',''))
  fresh['basis']=jobs.basis(fresh['targets'])
  fresh['parameters']={sku:copy.deepcopy(read(jobs.folder(sku)/'listing_bundle.json').get('variant_parameters') or {}) for sku in skus}
  fresh['variants']=[{'sku':t['sku'],'variant_parameters':copy.deepcopy(read(jobs.folder(t['sku'])/'listing_bundle.json').get('variant_parameters') or {})} for t in group]
  target.update(state='cancelled',message='本条已由用户重启，新队列：'+fresh['id'],superseded_by=fresh['id'])
  jobs.jobs.insert(0,fresh)
  for sku in skus:
   path=jobs.folder(sku)/'listing_bundle.json';b=read(path);b['image_regeneration_jobs']=[x for x in b.get('image_regeneration_jobs') or [] if x!=old_id]+[fresh['id']];write(path,b)
  jobs.save()
 else:
  folder=store.folder/'products'/target['sku'];path=folder/'listing_bundle.json'
  b=read(path) if path.exists() else None
  for key in list(fresh):
   if key.startswith('copy_') and key not in ('copy_leader','copy_source'):fresh.pop(key,None)
  if isinstance(b,dict):
   fresh.update(facts=b.get('facts') or fresh['facts'],variant_parameters=copy.deepcopy(b.get('variant_parameters') or fresh.get('variant_parameters') or {}))
   from listing_bundle import copy_complete
   if copy_complete(b.get('copy')):fresh['copy_state']='done'
   b.update(images=[],regeneration_pending=True,video={'local_file':'video/product_8s.mp4','exists':False,'https_url':None},hosting={'state':'waiting','verified_images':0,'message':'队列已重启，等待新图片'},video_hosting={'state':'waiting','message':'队列已重启，等待新视频'})
   b.pop('recollection_pending',None);b.pop('image_regeneration_jobs',None);write(path,b)
  group=[t for t in store.tasks if t.get('copy_leader',t['sku'])==fresh.get('copy_leader',fresh['sku']) and t['state']!='cancelled']
  variants=[];facts=[]
  for item in group:
   draft=store.folder/'products'/item['sku']/'listing_bundle.json';value=read(draft) if draft.exists() else {}
   variants.append({'sku':item['sku'],'variant_parameters':copy.deepcopy(value.get('variant_parameters') or item.get('variant_parameters') or {}),'facts':value.get('facts') or item.get('facts','')});facts.append(item['sku']+'：'+variants[-1]['facts'])
  fresh.update(group_variants=variants,group_facts='\n'.join(facts))
  from image_prompts import generation_prompt
  fresh['prompt']=generation_prompt(fresh['facts'],fresh.get('group_facts',''),fresh.get('expected_images',8))
  for name in ('images','video'):
   if (folder/name).exists():shutil.rmtree(folder/name)
  (folder/'image_manifest.json').unlink(missing_ok=True)
  # Keep group ordering so a follower never jumps ahead of a missing leader gallery.
  store.tasks[store.tasks.index(target)]=fresh
 store.save();store.set_paused(False)
 store.control['queue_restart']={'token':secrets.token_hex(16),'task_id':fresh['id'],'old_id':old_id,'sku':fresh['sku'],'created_at':time.time()}
 store.control.pop('queue_restart_ack',None);write(store.control_path,store.control)
 return {'old_id':old_id,'id':fresh['id'],'sku':fresh['sku'],'kind':fresh.get('kind','product'),'backup':str(backup),'target_skus':skus}
