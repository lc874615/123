"""Durable, explicitly requested partial image jobs; original assets stay live until commit."""
import base64,copy,hashlib,io,json,secrets,shutil,threading,time
from pathlib import Path
from PIL import Image
from pricing_service import read,write
from asset_state import VISUAL,canonical
from image_prompts import generation_prompt,shared_prompt,reference_contract

DONE={'saved','cancelled'}
class ImageJobs:
 def __init__(self,store):
  self.store=store;self.path=store.folder/'image_jobs.json';self.jobs=read(self.path) if self.path.exists() else []
  for j in self.jobs:
   for ref in j.get('references') or []:
    name=Path(ref.get('path','').replace('\\','/')).name
    folders=[self.store.folder/'products'/str(ref.get('sku') or j['sku'])/'references',self.store.folder/'products'/j['sku']/'shared_references']
    if ref.get('purpose') in ('shared_detail','shared_gallery'):folders.reverse()
    for folder in folders:
     if (folder/name).is_file():ref['path']=str(folder/name);break
   for plan in j.get('plans') or []:
    for row in plan['rows']:row['file']=str(self.folder(plan['sku'])/'images'/Path(row['file'].replace('\\','/')).name)
   if j['state'] in ('claimed','sending','waiting'):j.update(state='needs_attention',resume_mode='inspect_only',message='重启后只读取本次图片结果，不重新发送')
  self.save()
 def save(self):write(self.path,self.jobs)
 def get(self,identifier):return next((j for j in self.jobs if j['id']==identifier),None)
 def next(self):return next((j for j in self.jobs if j['state']=='queued'),None)
 def active(self,skus):return [j for j in self.jobs if j['state'] not in DONE and any(t['sku'] in skus for t in j['targets'])]
 def folder(self,sku):return self.store.folder/'products'/sku
 def product(self,sku):
  value=next((t for t in self.store.tasks if t['sku']==sku and t.get('set_mode') and t['state']!='cancelled'),None)
  if not value:raise ValueError('商品任务不存在：'+sku)
  return value
 def rows(self,sku):
  folder=self.folder(sku);rows=read(folder/'image_manifest.json')
  if len(rows)!=8 or [r['order'] for r in rows]!=list(range(1,9)):raise ValueError(sku+'：需要完整8张图片后才能重做')
  for r in rows:
   p=folder/'images'/Path(r['file'].replace('\\','/')).name
   if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:raise ValueError(sku+'：原图片缺失或变化，请先恢复采集')
  return rows
 def basis(self,targets):
  values=[]
  for target in targets:
   sku=target['sku'];b=read(self.folder(sku)/'listing_bundle.json');p=b.get('variant_parameters') or {}
   values.append([sku,{k:canonical(k,p.get(k)) for k in sorted(VISUAL)},[(r['order'],r['sha256']) for r in self.rows(sku) if r['order'] in target['orders']]])
  return hashlib.sha256(json.dumps(values,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 def refs(self,tasks,kind):
  candidates=[]
  for t in tasks:
   own=t.get('main_references') or [r for r in t.get('references') or [] if r.get('purpose') not in ('shared_gallery','shared_detail')]
   for r in (own[:1] if kind=='shared_details' else own):candidates.append((t['sku'],r,'variant_main'))
  if kind=='shared_details':
   details=[(t['sku'],r,'shared_detail') for t in tasks for r in t.get('detail_references') or []]
   candidates=details+candidates
  result=[];seen=set();root=(self.store.folder/'products').resolve()
  for sku,r,purpose in candidates:
   path=Path(r.get('path',''))
   try:parts=path.resolve().relative_to(root).parts
   except (ValueError,OSError):continue
   if 'references' not in parts and 'shared_references' not in parts:continue
   if not path.is_file() or path.stat().st_size>3*1024*1024:continue
   raw=path.read_bytes()
   with Image.open(io.BytesIO(raw)) as image:
    image.verify();fmt=image.format
   mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(fmt)
   if not mime:continue
   digest=hashlib.sha256(raw).hexdigest()
   if digest in seen:continue
   seen.add(digest);result.append({**r,'mime':mime,'reference_sha256':digest,'purpose':purpose,'sku':sku,'name':sku+'_'+path.name})
   if len(result)>=8:break
  if not result:raise ValueError('缺少原始商品参考图，请先补充原图；不会用AI生成图替代原图')
  return result
 def prompt(self,sku,kind,addition=''):
  task=self.product(sku);leader=task.get('copy_leader',sku);group=[t for t in self.store.tasks if t.get('copy_leader',t['sku'])==leader and t['state']!='cancelled']
  facts='\n'.join(t['sku']+'：'+str(read(self.folder(t['sku'])/'listing_bundle.json').get('facts') or t['facts']) for t in group)
  own=read(self.folder(sku)/'listing_bundle.json').get('facts') or task['facts']
  return (shared_prompt(facts) if kind=='shared_details' else generation_prompt(own,facts,1))+'\n用户补充要求（不得改变参考商品款式、颜色、结构、参数与件数）：\n'+(addition.strip() or '无额外要求')
 def create(self,sku,kind,selected,addition):
  if kind not in ('shared_details','variant_main') or len(addition)>10000:raise ValueError('图片重做设置无效或补充要求过长')
  task=self.product(sku);leader=task.get('copy_leader',sku);group=[t for t in self.store.tasks if t.get('copy_leader',t['sku'])==leader and t['state']!='cancelled'];allowed={t['sku'] for t in group}
  selected=list(dict.fromkeys(selected))
  if kind=='variant_main' and (not selected or not set(selected)<=allowed):raise ValueError('请选择本组一个或多个变体')
  specs=[(leader,[{'sku':t['sku'],'orders':list(range(2,9)),'indices':list(range(7))} for t in group])] if kind=='shared_details' else [(s,[{'sku':s,'orders':[1],'indices':[0]}]) for s in selected]
  planned=[]
  for owner,targets in specs:
   for target in targets:
    for old in self.active([target['sku']]):
     if any(t['sku']==target['sku'] and set(t['orders'])&set(target['orders']) for t in old['targets']):raise ValueError(target['sku']+'：对应图片已有重做任务，请等候完成或停止本组重做')
   refs=self.refs(group if kind=='shared_details' else [self.product(owner)],kind);identity='image-'+secrets.token_hex(12)
   job={'id':identity,'sku':owner,'image_job':True,'set_mode':True,'auto_batch':True,'kind':kind,'state':'queued','targets':targets,'expected_images':7 if kind=='shared_details' else 1,'received_images':[],'references':refs,'prompt':self.prompt(owner,kind,addition),'addition':addition,'parameters':{t['sku']:copy.deepcopy(read(self.folder(t['sku'])/'listing_bundle.json').get('variant_parameters') or {}) for t in targets},'variants':[{'sku':t['sku'],'variant_parameters':copy.deepcopy(read(self.folder(t['sku'])/'listing_bundle.json').get('variant_parameters') or {})} for t in group],'basis':self.basis(targets),'created_at':time.time(),'message':'已备份，等待自动生成7张共用详情图' if kind=='shared_details' else '已备份，等待自动生成本变体主图'}
   planned.append(job)
  # Every backup succeeds before the queue or live drafts change.
  for job in planned:
   for target in job['targets']:
    folder=self.folder(target['sku']);backup=folder/'regeneration_backups'/job['id'];backup.mkdir(parents=True)
    for name in ('images','video','image_manifest.json','listing_bundle.json'):
     source=folder/name
     if source.is_dir():shutil.copytree(source,backup/name)
     elif source.exists():shutil.copy2(source,backup/name)
    write(backup/'task.json',self.product(target['sku']))
  self.jobs.extend(planned);self.save()
  for job in planned:
   for target in job['targets']:
    path=self.folder(target['sku'])/'listing_bundle.json';b=read(path);b['image_regeneration_jobs']=list(dict.fromkeys((b.get('image_regeneration_jobs') or [])+[job['id']]));b.setdefault('image_regeneration_options',{})[kind]=addition;write(path,b)
  self.store.set_paused(False);return [j['id'] for j in planned]
 def claim(self):
  job=self.next()
  if not job:raise ValueError('没有图片重做任务')
  for ref in job['references']:
   if ref.get('reference_sha256') and (not Path(ref['path']).is_file() or hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()!=ref['reference_sha256']):job.update(state='needs_attention',message='排队期间原始参考图已变化，未发送；请停止任务后重新启动');self.save();raise ValueError(job['message'])
  try:references=[{'name':r['name'],'mime':r['mime'],'purpose':r.get('purpose'),'base64':base64.b64encode(Path(r['path']).read_bytes()).decode()} for r in job['references']]
  except OSError:job.update(state='needs_attention',message='原始参考图已缺失或不可读，未发送作图请求');self.save();raise ValueError(job['message']) from None
  job.update(state='claimed',message='已领取图片重做任务；异常时不自动重发');self.save();result=copy.deepcopy(job)
  result['prompt']+='\n'+reference_contract(result);result['references']=references
  return result
 def recover(self,identifier):
  job=self.get(identifier)
  if not job or job['state'] in DONE:raise ValueError('图片重做任务不存在或已结束')
  job.update(state='waiting',message='自动读取已发送的图片重做结果，不重新发送');job.pop('resume_mode',None);self.save()
  return {'id':job['id'],'sku':job['sku'],'set_mode':True,'image_job':True,'automaticRecovery':True,'expected_images':job['expected_images'],'saved_count':len(job['received_images']),'source_marker':'【OZON_TASK:'+job.get('source_request_id',job['id'])+'】'}
 def reset(self,identifier):
  job=self.get(identifier);folder=self.store.folder/'image_job_staging'/identifier
  if folder.exists():shutil.copytree(folder,folder.parent/(identifier+'-order-backup-'+str(time.time_ns())))
  job.update(received_images=[],state='waiting');self.save();return {'ok':True,'backup_created':True}
 def accept(self,identifier,index,encoded):
  job=self.get(identifier)
  if job['state']=='saved':return {'complete':True,'saved_count':job['expected_images'],'message':job['message']}
  if job['state'] not in ('claimed','sending','waiting','processing'):raise ValueError('图片重做任务当前不接受图片')
  if type(index) is not int or not 0<=index<job['expected_images'] or index>len(job['received_images']):raise ValueError('重做图片序号无效')
  raw=base64.b64decode(encoded,validate=True)
  if len(raw)>20*1024*1024:raise ValueError('图片过大')
  with Image.open(io.BytesIO(raw)) as image:image.verify()
  with Image.open(io.BytesIO(raw)) as image:
   if min(image.size)<512 or image.format not in ('PNG','JPEG','WEBP'):raise ValueError('图片格式或分辨率不符合要求')
  from asset_guard import reject_reference
  from image_format import normalize
  reject_reference(raw,job['references']);raw,ext=normalize(raw,self.store.folder/'image_job_staging'/identifier/'originals');digest=hashlib.sha256(raw).hexdigest();rows=job['received_images']
  if index<len(rows):
   if rows[index]['sha256']!=digest:
    from local_bridge import ImageOrderConflict
    raise ImageOrderConflict('新图库顺序与已暂存图片不一致，原图和暂存文件均保留')
  else:
   if any(r['sha256']==digest for r in rows):raise ValueError('不同图片位置内容重复，未替换原图')
   folder=self.store.folder/'image_job_staging'/identifier;folder.mkdir(parents=True,exist_ok=True);path=folder/(str(index+1)+'.'+ext);path.write_bytes(raw);rows.append({'name':path.name,'sha256':digest})
  if len(rows)==job['expected_images']:job['state']='processing';job['message']='新图已收齐，正在校验并替换对应图片'
  self.save()
  if job['state']=='processing':
   try:self.commit(job)
   except Exception as error:job.update(state='committing' if job.get('plans') else 'needs_attention',message='图片替换待恢复，原始备份保留：'+str(error)[:180]);self.save()
  return {'complete':job['state']=='saved','saved_count':len(rows),'message':job['message'],'expected_images':job['expected_images']}
 def commit(self,job):
  if not job.get('plans'):
   for ref in job['references']:
    if ref.get('reference_sha256') and (not Path(ref['path']).is_file() or hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()!=ref['reference_sha256']):raise ValueError('生成期间原始参考图已变化，未替换旧图')
  for staged in job['received_images']:
   source=self.store.folder/'image_job_staging'/job['id']/staged['name']
   if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=staged['sha256']:raise ValueError('暂存新图校验失败，未开始替换；原图与备份保留')
  if any(t['sku'] in self.store.video_running for t in job['targets']):job['message']='新图已收齐，等待旧视频处理结束后替换';self.save();return
  if not job.get('plans'):
   if self.basis(job['targets'])!=job['basis']:job.update(state='needs_attention',message='生成期间目标图片或商品参数已变化；新图暂存保留，未覆盖原图');self.save();return
   plans=[]
   for target in job['targets']:
    rows=copy.deepcopy(self.rows(target['sku']))
    for row in rows:
     if not row.get('generation_task_id'):
      owner=self.product(target['sku']) if row['order']==1 else self.product(self.product(target['sku']).get('gallery_source') or target['sku'])
      row.update(generation_task_id=owner['id'],source_index=0 if row['order']==1 else row['order']-1,source_expected=(owner.get('expected_images',8) if row['order']==1 else 8))
    for order,index in zip(target['orders'],target['indices']):
     staged=job['received_images'][index];ext=Path(staged['name']).suffix;name=('01_main' if order==1 else ('%02d_detail'%order))+ext
     rows[order-1]={'file':str(self.folder(target['sku'])/'images'/name),'sha256':staged['sha256'],'order':order,'role':'primary' if order==1 else 'gallery','source':'assistant_generated','generation_task_id':job.get('source_request_id',job['id']),'source_index':index,'source_expected':job['expected_images']}
     if order>1:rows[order-1]['shared_from']=job['sku']
    plans.append({'sku':target['sku'],'rows':rows,'old_files':[Path(r['file'].replace('\\','/')).name for r in self.rows(target['sku'])]})
   job.update(plans=plans,state='committing');self.save()
  from listing_bundle import refresh_assets
  completed=[]
  for plan,target in zip(job['plans'],job['targets']):
   sku=plan['sku'];folder=self.folder(sku)
   for order,index in zip(target['orders'],target['indices']):
    source=self.store.folder/'image_job_staging'/job['id']/job['received_images'][index]['name'];raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=job['received_images'][index]['sha256']:raise ValueError('暂存新图校验失败，备份和原图保留')
    dest=folder/'images'/Path(plan['rows'][order-1]['file']).name;temp=dest.with_suffix(dest.suffix+'.tmp');temp.write_bytes(raw);temp.replace(dest)
   write(folder/'image_manifest.json',plan['rows']);product=self.product(sku);product['received_images']=copy.deepcopy(plan['rows']);product.pop('video',None);product['message']='图片已更新，视频及托管正在重新处理'
   live={Path(r['file']).name for r in plan['rows']}
   for name in plan['old_files']:
    if name not in live:(folder/'images'/name).unlink(missing_ok=True)
   if (folder/'video').exists():shutil.rmtree(folder/'video')
   refresh_assets(folder);b=read(folder/'listing_bundle.json');b['image_regeneration_jobs']=[x for x in b.get('image_regeneration_jobs') or [] if x!=job['id']]
   review=b.get('asset_review') or {}
   if job['kind']=='variant_main':
    from asset_state import differs
    b['asset_basis']=copy.deepcopy((job.get('parameters') or {}).get(sku) or b.get('variant_parameters') or {});review['main']=differs(b['asset_basis'],b.get('variant_parameters') or {},VISUAL)
   elif job['kind']=='shared_details':
    from asset_state import differs
    b['gallery_basis']=copy.deepcopy(job.get('variants') or []);review['gallery']=any(differs(r.get('variant_parameters') or {},read(self.folder(r['sku'])/'listing_bundle.json').get('variant_parameters') or {},VISUAL) for r in b['gallery_basis'])
   b['asset_review']=review;write(folder/'listing_bundle.json',b);completed.append((sku,not b['image_regeneration_jobs']))
  job.update(state='saved',message='共用7张详情图已替换并同步全组；视频与托管自动更新' if job['kind']=='shared_details' else '本变体主图已替换，7张详情保留；视频与托管自动更新' if job['kind']=='variant_main' else '已有图片已按来源更新到对应变体；视频与托管自动更新');self.store.save()
  for sku,ready in completed:
   if ready:threading.Thread(target=self.store.render_video,args=(sku,),daemon=True).start()
 def recollect(self,group):
  clusters={};skus=[t['sku'] for t in group]
  for task in group:
   for row in self.rows(task['sku']):
    source=row.get('generation_task_id')
    if not source:
     owner=task if row['order']==1 else self.product(task.get('gallery_source') or task['sku']);source=owner['id'];row={**row,'source_expected':owner.get('expected_images',8) if row['order']==1 else 8,'source_index':0 if row['order']==1 else row['order']-1}
    key=(source,int(row['source_expected']));cluster=clusters.setdefault(key,{})
    target=cluster.setdefault(task['sku'],{'sku':task['sku'],'orders':[],'indices':[]});target['orders'].append(row['order']);target['indices'].append(row['source_index'])
  operation='recollect-'+secrets.token_hex(8)
  for t in group:
   folder=self.folder(t['sku']);backup=folder/'regeneration_backups'/operation;backup.mkdir(parents=True)
   for name in ('images','video','image_manifest.json','listing_bundle.json'):
    source=folder/name
    if source.is_dir():shutil.copytree(source,backup/name)
    elif source.exists():shutil.copy2(source,backup/name)
   write(backup/'task.json',t)
  for (source,expected),mapping in clusters.items():
   targets=list(mapping.values());identity='image-'+secrets.token_hex(12);job={'id':identity,'sku':targets[0]['sku'],'image_job':True,'set_mode':True,'kind':'asset_recollection','state':'needs_attention','resume_mode':'inspect_only','source_request_id':source,'targets':targets,'expected_images':expected,'received_images':[],'references':[],'basis':self.basis(targets),'created_at':time.time(),'message':'已备份，自动按各图片实际来源重新采集；不重新作图'}
   self.jobs.append(job)
   for target in targets:
    path=self.folder(target['sku'])/'listing_bundle.json';b=read(path);b['image_regeneration_jobs']=list(dict.fromkeys((b.get('image_regeneration_jobs') or [])+[identity]));write(path,b)
  self.save();self.store.set_paused(False);return operation
 def tick(self):
  for j in self.jobs:
   if j['state'] in ('processing','committing'):
    try:self.commit(j)
    except Exception as error:j.update(state='committing' if j.get('plans') else 'needs_attention',message='图片替换待恢复：'+str(error)[:180]);self.save()
 def cancel(self,skus):
  jobs=self.active(skus)
  if any(j.get('pause_requested') and not j.get('pause_ack') or j['state'] in ('claimed','sending','waiting','committing') for j in jobs):raise ValueError('请等待插件停止回执后再停止重做')
  for j in jobs:
   j.update(state='cancelled',message='用户停止本组图片重做，原图和备份保留')
   for target in j['targets']:
    path=self.folder(target['sku'])/'listing_bundle.json';b=read(path);b['image_regeneration_jobs']=[x for x in b.get('image_regeneration_jobs') or [] if x!=j['id']];write(path,b)
  self.save();return len(jobs)
