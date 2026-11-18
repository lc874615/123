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
def category_context(store,task):
 from category_prefill import schema
 path=store.folder/'products'/task['sku']/'listing_bundle.json'
 b=read(path) if path.exists() else {}
 fields,digest=schema(b)
 return fields,digest if fields else ''
def pending_task(store,task):
 attempt=task.get('attribute_attempt') or {};fields,digest=category_context(store,task)
 return attempt.get('basis')!=basis(parameters(store,task)) or attempt.get('version')!=VERSION or attempt.get('schema_basis','')!=digest
def needed(store,task):
 if task.get('copy_leader',task['sku'])!=task['sku'] or task.get('copy_state') in ('running','needs_attention'):return False
 return any(any(r.get('purpose') not in ('shared_gallery','shared_detail','shared_information') for r in original_references(store,t)) and pending_task(store,t) for t in group(store,task['sku']))
def build(store,leader,inspect_only=False):
 tasks=group(store,leader);owner=next(t for t in tasks if t['sku']==leader)
 tasks=sorted(tasks,key=lambda t:not pending_task(store,t))
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
  digest=hashlib.sha256(raw).hexdigest();identity=(digest,str(path.resolve()))
  if identity in hashes:hashes[identity]['skus']=sorted(set(hashes[identity]['skus'])|set(skus));continue
  if len(selected)>=8:continue
  stat=path.stat();item={'id':'R'+str(len(selected)+1),'path':str(path),'sha256':digest,'stat':[stat.st_size,stat.st_mtime_ns],'skus':skus,'mime':ref.get('mime') or 'image/jpeg','base64':base64.b64encode(raw).decode(),'name':'R'+str(len(selected)+1)+'_'+path.name};selected.append(item);hashes[identity]=item
 covered=[t for t in tasks if {str(Path(r['path']).resolve()) for r in original_references(store,t) if r.get('purpose') not in ('shared_gallery','shared_detail','shared_information')} & {str(Path(r['path']).resolve()) for r in selected}]
 context={'version':VERSION,'variants':{t['sku']:{'basis':basis(parameters(store,t)),'parameters':parameters(store,t),'category_fields':category_context(store,t)[0],'schema_basis':category_context(store,t)[1]} for t in covered},'references':[{k:r[k] for k in ('id','path','sha256','stat','skus')} for r in selected]}
 owner['attribute_context']=context
 for t in tasks:
  own_paths={str(Path(r['path']).resolve()) for r in original_references(store,t) if r.get('purpose') not in ('shared_gallery','shared_detail','shared_information')}
  if own_paths & {str(Path(r['path']).resolve()) for r in selected}:t['attribute_attempt']={'version':VERSION,'basis':context['variants'][t['sku']]['basis'],'schema_basis':context['variants'][t['sku']]['schema_basis']}
 return context,[{k:r[k] for k in ('name','mime','base64')} for r in selected]
def prompt(context):
 mapping=[{'id':r['id'],'skus':r['skus']} for r in context.get('references',[])]
 from category_prefill import key as category_key
 fields={sku:[{**f,'field_key':category_key(f)} for f in data.get('category_fields',[])] for sku,data in context.get('variants',{}).items()}
 category_rules='另外按各SKU当前官方字段补充 category_attributes 对象，键为SKU，值为记录数组。每条为field_key、value、source、evidence、reference_ids；field_key必须从下面给定清单原样选择，不能添加或猜测字段ID、官方字典ID。仅填写明确已填参数或原图清晰文字能证明的值；数值保留原始数字和单位，不自行换算，不由图片比例计算尺寸、体积或重量。普通文本翻译为俄语，布尔值用true/false，多选使用数组。认证、条码、品牌、海关和保修信息不自动补写。没有本SKU依据的字段省略，不套用其他变体资料。官方字段清单：'+json.dumps(fields,ensure_ascii=False)+'。'
 return category_rules+('同时读取本次附件中的原始参考图，按R1、R2…顺序对应附件。严禁使用对话中的AI生成图片作为属性依据。参数明确提供的内容优先，图中看不清或没有的信息不填写；不能根据总高/总宽推算座高、座宽、座深、靠背尺寸，不估计承重/填充/涂层。只有原图清楚标注的数字才能读取尺寸；承重、填充和涂层只允许读取原图清晰文字，不能凭外观猜测。颜色必须沿用各SKU参数中的全部颜色，不丢弃第二个颜色。为JSON增加variant_attributes对象，键为SKU，值为记录数组；每条包含key、value（俄语字符串或房间/特点的俄语数组）、source（parameters/reference_image/reference_image_text）、evidence（简短原始依据）、reference_ids（R编号数组）。只允许这些key：'+','.join(FIELDS)+'。没有依据的key省略，找不到信息时返回空数组。不能填品牌、海关编码、标记要求或官方字典ID。仅对附件映射允许的SKU使用该图。附件映射：'+json.dumps(mapping,ensure_ascii=False)+'；各变体参数：'+json.dumps(context['variants'],ensure_ascii=False))
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
  folder=store.folder/'products'/sku;path=folder/'listing_bundle.json'
  if sku in raw:
   write(folder/'attribute_observations.json',data)
   if path.exists():bundle=read(path);bundle['reference_attributes']=data;write(path,bundle)
  from category_prefill import schema as category_schema,key as category_key,typed as category_typed,numeric_field as category_numeric
  target=read(path) if path.exists() else {}
  current_fields,current_digest=category_schema(target);allowed_fields={category_key(f):f for f in snapshot.get('category_fields',[])};category_records={};conflicts=set()
  if snapshot.get('schema_basis') and current_digest==snapshot['schema_basis']:
   for row in (value.get('category_attributes') or {}).get(sku,[]) if isinstance(value.get('category_attributes'),dict) and isinstance(value['category_attributes'].get(sku),list) else []:
    if not isinstance(row,dict):continue
    field=allowed_fields.get(row.get('field_key'));source=row.get('source');evidence=str(row.get('evidence') or '')[:400];ref_ids=row.get('reference_ids') or [];raw=row.get('value')
    if not field or not evidence or not isinstance(raw,(str,list)) or len(str(raw))>600:continue
    if source=='parameters':
     if evidence not in ' '.join(str(v) for v in snapshot['parameters'].values()):continue
    elif source=='reference_image_text':
     if not isinstance(ref_ids,list) or not ref_ids or any(not isinstance(r,str) for r in ref_ids) or not set(ref_ids)<=allowed:continue
    else:continue
    if category_numeric(field):
     numbers=re.findall(r'\d+(?:[.,]\d+)?',str(raw))
     if not numbers or any(not re.search(r'(?<!\d)'+re.escape(n)+r'(?!\d)',evidence) for n in numbers):continue
    item=category_typed(field,raw)
    if item is None:continue
    field_id=category_key(field)
    if field_id in conflicts:continue
    if field_id in category_records and category_records[field_id]['value']==item:continue
    if field_id in category_records and category_records[field_id]['value']!=item:
     category_records.pop(field_id);conflicts.add(field_id);count-=1;continue
    category_records[field_id]={'value':item,'evidence':evidence,'source':source,'reference_ids':ref_ids};count+=1
   target['reference_category_attributes']={'version':VERSION,'basis':snapshot['basis'],'schema_basis':current_digest,'references':refs,'records':category_records}
   write(path,target)
  task['attribute_extract_state']='done'
 return count
