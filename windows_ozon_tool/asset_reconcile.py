"""Reconcile stale status flags against checked files and known generation parameters."""
import copy,hashlib,json
from pathlib import Path
from asset_audit import inspect
from asset_state import VISUAL,COPY,canonical,differs
from listing_bundle import copy_complete
from pricing_service import read,write

LABELS={'name':'商品名称','color':'颜色','size':'规格','quantity':'每套件数','material':'主体材质','accessory_material':'配件/内衬材质','length':'商品长','width':'商品宽','height':'商品高','assembly':'组装方式','extra':'补充参数','net_weight':'净重','pack_length':'包装长','pack_width':'包装宽','pack_height':'包装高','pack_weight':'包装重','origin':'产地'}
def group_bundles(store,leader):
 result=[]
 for t in store.tasks:
  if t.get('copy_leader',t['sku'])!=leader or t.get('state')=='cancelled' or not t.get('set_mode'):continue
  path=store.folder/'products'/t['sku']/'listing_bundle.json';result.append(read(path) if path.exists() else {'sku':t['sku'],'variant_parameters':t.get('variant_parameters') or {},'facts':t.get('facts','')})
 return result
def copy_basis(bundles):
 return hashlib.sha256(json.dumps(sorted([(b['sku'],{k:canonical(k,(b.get('variant_parameters') or {}).get(k)) for k in sorted(COPY)}) for b in bundles]),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def checked(store,task):
 folder=store.folder/'products'/task['sku']
 try:
  paths=[folder/'image_manifest.json']+[folder/'images'/Path(r['file'].replace('\\','/')).name for r in task.get('received_images') or []];key=tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
 except (OSError,KeyError):return {'verified':False,'reason':'图片文件不完整'}
 cache=getattr(store,'_asset_check_cache',{});store._asset_check_cache=cache
 if cache.get(task['sku'],{}).get('key')!=key:cache[task['sku']]={'key':key,'audit':inspect(folder)}
 return cache[task['sku']]['audit']
def reconcile(store,accept_group=None):
 tasks=[t for t in store.tasks if t.get('set_mode') and t['state']!='cancelled'];groups={t.get('copy_leader',t['sku']) for t in tasks};changed=0
 for leader in groups:
  bundles=group_bundles(store,leader);by_sku={b['sku']:b for b in bundles};fingerprint=copy_basis(bundles);members=[t for t in tasks if t.get('copy_leader',t['sku'])==leader];leader_task=next((t for t in members if t['sku']==leader),None);leader_bundle=by_sku.get(leader) or {};accept=accept_group==leader
  audits={t['sku']:checked(store,t) for t in members}
  if accept and (any(t.get('state')!='saved' or not audits[t['sku']].get('verified') for t in members) or store.image_jobs.active(list(by_sku))):raise ValueError('本组图片尚未全部采集校验完成，不能沿用未完成的素材')
  for t in members:
   path=store.folder/'products'/t['sku']/'listing_bundle.json'
   if not path.exists():continue
   b=by_sku[t['sku']];before=copy.deepcopy(b);review=copy.deepcopy(b.get('asset_review') or {});p=b.get('variant_parameters') or {};fields=set(review.get('fields') or [])
   if t['state']=='saved' and audits[t['sku']].get('verified') and not b.get('image_regeneration_jobs'):
    validation=b.get('asset_validation') or {};hashes=[audits[t['sku']].get('primary_hash')]+audits[t['sku']].get('gallery_hashes',[]);accepted=validation.get('accepted_image_hashes')==hashes
    basis=(validation.get('accepted_parameters') if accepted else None) or b.get('asset_basis') or t.get('generation_parameters') or {};main_changes=[k for k in VISUAL if differs(basis,p,{k})] if basis else sorted(fields&VISUAL) if review.get('main') else []
    gallery_basis=(validation.get('accepted_gallery_basis') if accepted else None) or b.get('gallery_basis') or leader_bundle.get('gallery_basis') or (leader_task or {}).get('generation_variants') or []
    gallery_changes=[]
    if gallery_basis:
     original={r.get('sku'):r.get('variant_parameters') or {} for r in gallery_basis};current={row['sku']:row.get('variant_parameters') or {} for row in bundles}
     if set(original)!=set(current):gallery_changes.append('变体列表')
     for sku,params in original.items():
      for key in VISUAL:
       if differs(params,current.get(sku) or {},{key}):gallery_changes.append(sku+'：'+LABELS.get(key,key))
    elif review.get('gallery'):gallery_changes=[LABELS.get(k,k) for k in sorted(fields&VISUAL)]
    if t.get('gallery_source') and audits.get(t['gallery_source'],{}).get('verified') and audits[t['sku']].get('gallery_hashes')!=audits[t['gallery_source']].get('gallery_hashes'):gallery_changes.append('共用详情与首变体不一致')
    if accept:
     validation.update(accepted_image_hashes=hashes,accepted_parameters=copy.deepcopy(p),accepted_gallery_basis=[{'sku':row['sku'],'variant_parameters':copy.deepcopy(row.get('variant_parameters') or {})} for row in bundles]);accepted=True
     b['asset_basis']=copy.deepcopy(p);b['gallery_basis']=[{'sku':row['sku'],'variant_parameters':copy.deepcopy(row.get('variant_parameters') or {})} for row in bundles];main_changes=[];gallery_changes=[]
    for key,value in (('main',bool(main_changes)),('gallery',bool(gallery_changes))):
     if key in review or value or accept:review[key]=value
    if not main_changes and not gallery_changes:b.pop('regeneration_pending',None)
    b['asset_validation']={**{k:v for k,v in validation.items() if k.startswith('accepted_')},'verified':True,'main_changes':[LABELS.get(k,k) for k in sorted(main_changes)],'gallery_changes':sorted(set(gallery_changes)),'accepted_by_user':bool(accepted)}
   if b.get('copy_basis')==fingerprint and copy_complete(b.get('copy')):
    if review.get('copy'):review['copy']=False
   elif b.get('copy_basis') and b.get('copy_basis')!=fingerprint:review['copy']=True
   if copy_complete(b.get('copy')):
    from material_guard import conflict
    if conflict(b,b['copy']):review['copy']=True
   if review:b['asset_review']=review
   if b!=before:write(path,b);changed+=1
 return changed
