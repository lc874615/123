"""One copy pipeline: inspect safely first, generate only when needed, share to every SKU."""
import secrets
from pathlib import Path
from variants import valid_article
from pricing_service import read,write
from asset_reconcile import group_bundles,copy_basis
from listing_bundle import copy_complete,copy_prompt_for,save_copy

def prepare(store,body):
 sku=body['sku']
 if not valid_article(sku):raise ValueError('货号格式无效')
 selected=next((t for t in store.tasks if t['sku']==sku),None)
 if not selected:raise ValueError('货号不存在')
 sku=selected.get('copy_leader',sku);owner=next(t for t in store.tasks if t['sku']==sku);folder=store.folder/'products'/sku;path=folder/'listing_bundle.json'
 if not path.exists():raise ValueError('请先在本地准备上架草稿')
 bundles=group_bundles(store,sku);fingerprint=copy_basis(bundles);b=read(path);refresh=bool((b.get('asset_review') or {}).get('copy')) and copy_complete(b.get('copy'))
 if refresh and owner.get('copy_mode')!='attributes':owner['copy_mode']='copy_refresh'
 dispatched=owner.get('copy_phase')=='generating' and owner.get('copy_state') in ('running','needs_attention') or owner.get('resume_mode')=='copy_inspect_only' and not owner.get('copy_phase')
 if body.get('prepare_only') and not dispatched and owner.get('copy_mode')!='attributes' and copy_complete(b.get('copy')) and not refresh:
  store.sync_shared_copies();return {'id':'copy:'+sku,'sku':sku,'local_ready':True,'fingerprint':fingerprint}
 if body.get('prepare_only'):
  if not dispatched:owner.update(copy_phase='inspecting',copy_context_basis=fingerprint,copy_source_revision=b.get('copy_user_revision'))
  owner['copy_state']='running';store.save()
  marker=owner.get('copy_request_marker')
  return {'id':'copy:'+sku,'sku':sku,'fingerprint':owner.get('copy_context_basis') or fingerprint,'needsRefresh':refresh,'group_skus':[row['sku'] for row in bundles],'attributesOnly':owner.get('copy_mode')=='attributes','dispatched':bool(dispatched),'copy_phase':owner.get('copy_phase'),'marker':marker,'resume_marker':bool(marker),'previous_marker':marker if owner.get('copy_context_basis')==fingerprint else None}
 read_only=bool(body.get('inspect_only'))
 previous_prompt=None;prompt_file=folder/'copy_prompt.txt'
 if not read_only and owner.get('copy_phase')=='inspecting' and owner.get('copy_request_marker') and prompt_file.exists():
  previous=prompt_file.read_text(encoding='utf-8');previous_prompt=previous if previous.startswith(owner['copy_request_marker']) else None
 if dispatched and not read_only:raise ValueError('已有文案请求等待结果，先自动采集，不重新发送')
 context={'group_facts':'\n'.join(row['sku']+'：'+str(row.get('facts') or '') for row in bundles),'group_variants':[{'sku':row['sku'],'facts':row.get('facts',''),'variant_parameters':row.get('variant_parameters') or {}} for row in bundles]};b.update(context);write(path,b)
 from reference_prefill import build,prompt as attribute_prompt
 photo_context,references=build(store,sku,inspect_only=read_only)
 marker=owner.get('copy_request_marker') if read_only else '【OZON_COPY:'+secrets.token_hex(12)+'】'
 if not read_only:owner.update(copy_phase='generating',copy_context_basis=fingerprint,copy_request_marker=marker,copy_source_revision=b.get('copy_user_revision'))
 owner['copy_state']='running';store.save()
 prompt=(marker or '')+'\n本次商品组文案保存货号：'+sku+'。输出JSON额外包含sku字段，值为'+sku+'，以及facts_fingerprint字段，值为'+fingerprint+'。'+copy_prompt_for(context)
 if owner.get('copy_mode')=='attributes':prompt=(marker or '')+'\n只读取属性，不改写已有文案。仅输出JSON，包含sku字段（值为'+sku+'）和variant_attributes。'
 prompt+='\n'+attribute_prompt(photo_context)+'\n再次强调：sku、facts_fingerprint、variant_attributes的SKU键仅为内部关联元数据；title_ru、description_ru、tags_ru不得含任何货号、卖家代码或SKU。';(folder/'copy_prompt.txt').write_text(prompt,encoding='utf-8')
 return {'id':'copy:'+sku,'sku':sku,'marker':marker,'prompt':prompt,'references':references,'fingerprint':fingerprint,'copy_phase':owner.get('copy_phase'),'replace_unsent_prompt':previous_prompt}
def save(store,body):
 sku=body['sku']
 if not valid_article(sku):raise ValueError('货号格式无效')
 owner=next(t for t in store.tasks if t['sku']==sku);path=store.folder/'products'/sku/'listing_bundle.json';value=body['copy'];attributes=owner.get('copy_mode')=='attributes'
 if attributes:
  if value.get('sku')!=sku:raise ValueError('属性结果货号与当前任务不一致')
  result={'ok':True}
 else:
  bundles=group_bundles(store,sku);fingerprint=copy_basis(bundles);current=read(path);refresh=owner.get('copy_mode')=='copy_refresh' or bool((current.get('asset_review') or {}).get('copy')) and copy_complete(current.get('copy'));manual=bool(body.get('manual'))
  if not manual and current.get('copy_user_revision')!=owner.get('copy_source_revision'):raise ValueError('本地共用文案已保存更新，忽略此前自动生成结果，未覆盖已保存文案')
  if not manual and owner.get('copy_context_basis') and owner['copy_context_basis']!=fingerprint:raise ValueError('文案处理期间商品参数已变化，未保存旧文案，请重新读取当前资料')
  if not manual and value.get('facts_fingerprint') and value['facts_fingerprint']!=fingerprint:raise ValueError('已有文案对应的商品参数已变化，需按最新资料生成')
  if refresh and not manual and (body.get('existing') or owner.get('copy_phase')=='inspecting') and value.get('facts_fingerprint')!=fingerprint:raise ValueError('已有文案缺少当前整组参数依据，不沿用旧文案')
  normalized={k:v for k,v in value.items() if k not in ('variant_attributes','facts_fingerprint')}
  result=save_copy(path.parent,normalized,replace=refresh or manual);current=read(path);current['copy_basis']=fingerprint
  if current.get('asset_review'):current['asset_review']['copy']=False
  write(path,current)
 if 'variant_attributes' in value and owner.get('attribute_context'):
  from reference_prefill import save as save_attributes
  save_attributes(store,sku,value)
 owner.pop('copy_mode',None);owner.pop('resume_mode',None);owner['copy_phase']='done';store.sync_shared_copies();owner.update(copy_state='done',message='整组文案已自动保存并同步全部变体；视频与托管继续处理');store.save();return result
