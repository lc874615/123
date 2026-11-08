"""Read original reference pictures through the bound ChatGPT task, never generated art."""
import base64,hashlib,json,re
from pathlib import Path
from prefill_rules import VERSION,FIELDS,NUMERIC,basis
from pricing_service import read,write

def group(store,leader):return [t for t in store.tasks if t.get('copy_leader',t['sku'])==leader and t.get('set_mode') and t.get('state')!='cancelled']
def parameters(store,task):
 path=store.folder/'products'/task['sku']/'listing_bundle.json'
 return (read(path).get('variant_parameters') or {}) if path.exists() else task.get('variant_parameters') or {}
def original_references(store,task):
 result=[];root=(store.folder/'products').resolve()
 for ref in task.get('main_references') or task.get('references') or []:
  path=Path(ref.get('path',''))
  try:relative=path.resolve().relative_to(root)
  except (OSError,ValueError):continue
  if not any(part in ('references','shared_references') for part in relative.parts) or 'images' in relative.parts:continue
  if path.is_file() and path.stat().st_size<=3*1024*1024:result.append(ref)
 return result
def needed(store,task):
 if task.get('copy_leader',task['sku'])!=task['sku'] or task.get('copy_state') in ('running','needs_attention'):return False
 tasks=group(store,task['sku'])
 if not any(original_references(store,t) for t in tasks):return False
 return any((t.get('attribute_attempt') or {}).get('basis')!=basis(parameters(store,t)) or (t.get('attribute_attempt') or {}).get('version')!=VERSION for t in tasks)
def build(store,leader,inspect_only=False):
 tasks=group(store,leader);owner=next(t for t in tasks if t['sku']==leader)
 if inspect_only and owner.get('attribute_context'):return owner['attribute_context'],[]
 selected=[];hashes={}
 candidates=[]
 for t in tasks:
  own=[r for r in original_references(store,t) if r.get('purpose') not in ('shared_gallery','shared_detail')]
  if own:candidates.append((own[0],[t['sku']]))
 for t in tasks:
  for r in t.get('detail_references') or []:candidates.append((r,[x['sku'] for x in tasks]))
 for t in tasks:
  for r in original_references(store,t)[1:]:candidates.append((r,[t['sku']]))
 root=(store.folder/'products').resolve()
 for ref,skus in candidates:
  path=Path(ref['path'])
  try:relative=path.resolve().relative_to(root)
  except (OSError,ValueError):continue
  if not any(p in ('references','shared_references') for p in relative.parts) or 'images' in relative.parts or not path.is_file():continue
  raw=path.read_bytes()
  if len(raw)>3*1024*1024:continue
  digest=hashlib.sha256(raw).hexdigest()
  if digest in hashes:hashes[digest]['skus']=sorted(set(hashes[digest]['skus'])|set(skus));continue
  if len(selected)>=8:continue
  stat=path.stat();item={'id':'R'+str(len(selected)+1),'path':str(path),'sha256':digest,'stat':[stat.st_size,stat.st_mtime_ns],'skus':skus,'mime':ref.get('mime') or 'image/jpeg','base64':base64.b64encode(raw).decode(),'name':'R'+str(len(selected)+1)+'_'+path.name};selected.append(item);hashes[digest]=item
 context={'version':VERSION,'variants':{t['sku']:{'basis':basis(parameters(store,t)),'parameters':parameters(store,t)} for t in tasks},'references':[{k:r[k] for k in ('id','path','sha256','stat','skus')} for r in selected]}
 owner['attribute_context']=context
 for t in tasks:t['attribute_attempt']={'version':VERSION,'basis':context['variants'][t['sku']]['basis']}
 return context,[{k:r[k] for k in ('name','mime','base64')} for r in selected]
def prompt(context):
 mapping=[{'id':r['id'],'skus':r['skus']} for r in context.get('references',[])]
 return ('同时读取本次附件中的原始参考图，按R1、R2…顺序对应附件。严禁使用对话中的AI生成图片作为属性依据。参数明确提供的内容优先，图中看不清或没有的信息不填写；不能根据总高/总宽推算座高、座宽、座深、靠背尺寸，不估计承重/填充/涂层。只有原图清楚标注的数字才能读取尺寸；承重、填充和涂层只允许读取原图清晰文字，不能凭外观猜测。颜色必须沿用各SKU参数中的全部颜色，不丢弃第二个颜色。为JSON增加variant_attributes对象，键为SKU，值为记录数组；每条包含key、value（俄语字符串或房间/特点的俄语数组）、source（parameters/reference_image/reference_image_text）、evidence（简短原始依据）、reference_ids（R编号数组）。只允许这些key：'+','.join(FIELDS)+'。没有依据的key省略，找不到信息时返回空数组。不能填品牌、海关编码、标记要求或官方字典ID。仅对附件映射允许的SKU使用该图。附件映射：'+json.dumps(mapping,ensure_ascii=False)+'；各变体参数：'+json.dumps(context['variants'],ensure_ascii=False))
def save(store,leader,value):
 owner=next(t for t in store.tasks if t['sku']==leader);context=owner.get('attribute_context') or {};raw=value.get('variant_attributes') or {};count=0
 if not isinstance(raw,dict):raise ValueError('图片属性记录应按SKU分组')
 for task in group(store,leader):
  sku=task['sku'];snapshot=(context.get('variants') or {}).get(sku)
  if not snapshot or snapshot['basis']!=basis(parameters(store,task)):continue
  refs=[r for r in context.get('references',[]) if sku in r['skus']];allowed={r['id'] for r in refs};records={}
  for row in (raw.get(sku) or [])[:40] if isinstance(raw.get(sku,[]),list) else []:
   if not isinstance(row,dict):continue
   key=row.get('key');source=row.get('source');evidence=str(row.get('evidence') or '')[:400];item=row.get('value');ref_ids=row.get('reference_ids') or []
   if key not in FIELDS or not evidence or source not in ('parameters','reference_image','reference_image_text'):continue
   if not isinstance(item,(str,list)) or len(str(item))>600:continue
   if isinstance(item,list) and (key not in ('features','rooms') or any(not isinstance(v,str) for v in item)):continue
   if source=='parameters':
    text=' '.join(str(v) for v in snapshot['parameters'].values())
    if evidence not in text:continue
   elif not isinstance(ref_ids,list) or not ref_ids or any(not isinstance(r,str) for r in ref_ids) or not set(ref_ids)<=allowed:continue
   if key in ('max_load','fill_material','coating') and source=='reference_image':continue
   if key in NUMERIC:
    text=str(item)
    if not re.fullmatch(r'\d+(?:\.\d+)?',text) or not re.search(r'(?<!\d)'+re.escape(text)+r'(?!\d)',evidence):continue
    if source=='reference_image':continue
   records[key]={'value':item,'evidence':evidence,'source':source,'reference_ids':ref_ids};count+=1
  data={'sku':sku,'version':VERSION,'basis':snapshot['basis'],'references':refs,'records':records}
  folder=store.folder/'products'/sku;write(folder/'attribute_observations.json',data)
  path=folder/'listing_bundle.json'
  if path.exists():bundle=read(path);bundle['reference_attributes']=data;write(path,bundle)
  task['attribute_extract_state']='done'
 return count
