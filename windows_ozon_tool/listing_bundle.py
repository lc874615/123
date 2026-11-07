"""Prepare a local handoff without mistaking local paths for hosted Ozon images."""
import json,hashlib
from pathlib import Path

def copy_prompt_for(task):
 copy_facts=task.get('group_facts') or task.get('facts','')
 return '以下为同一商品全部变体，标题、简介和标签统一一套。标题以全组共同商品名称、用途和共同卖点为主，不得只写某一个变体的颜色或尺寸。简介完整覆盖全部变体，颜色、尺寸、材质和套装数量差异按选项分别说明，明确购买时选择一个变体，不得写成所有颜色或规格一并发货。标签统一覆盖全组真实用途和变体相关长尾词，不得重复堆砌。根据以下商品事实生成俄文Ozon标题、简介和标签。自然覆盖相关长尾词，禁止重复堆词和编造承重、认证、功能、品牌。品牌固定无品牌（Нет бренда），不要将品牌列为缺失项。严格区分主体材质和配件/内衬材质，例如主体为聚丙烯而内衬为纸板时，两者均可描述，但不得将纸板写成主体材质。未知部件材质不得推测。未知留空。只输出JSON：title_ru、description_ru、tags_ru数组、missing_facts数组。商品事实：'+copy_facts

def prepare(folder,task):
 folder=Path(folder);manifest=folder/'image_manifest.json'
 if not manifest.exists():raise ValueError('未找到8图清单')
 images=json.loads(manifest.read_text(encoding='utf-8-sig'))
 if len(images)!=8:raise ValueError('需要8张图片')
 images=sorted(images,key=lambda x:x['order'])
 if [x['order'] for x in images]!=list(range(1,9)):raise ValueError('图片顺序不完整')
 checked=[]
 for row in images:
  # Relative assets survive moving the complete product directory on Windows.
  path=folder/'images'/Path(row['file'].replace('\\','/')).name
  if not path.is_file():raise ValueError('缺少图片 '+path.name)
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if digest!=row['sha256']:raise ValueError('图片已变化，请重新审核 '+path.name)
  checked.append({'order':row['order'],'role':'primary' if row['order']==1 else 'gallery','local_file':'images/'+path.name,'sha256':digest,'https_url':None})
 facts=task.get('facts') or task.get('prompt','').split('商品事实：')[-1]
 copy_facts=task.get('group_facts',facts)
 copy_prompt=copy_prompt_for(task)
 (folder/'copy_prompt.txt').write_text(copy_prompt,encoding='utf-8')
 bundle={'sku':task['sku'],'offer_id':task['sku'],'base_article':task.get('base_article',task['sku']),'model':task.get('model'),'variant_index':task.get('variant_index'),'variant_parameters':task.get('variant_parameters',{}),'brand':'Нет бренда','stock':int(task.get('variant_parameters',{}).get('stock','1000')),'facts':facts,'group_facts':task.get('group_facts',facts),'group_variants':task.get('group_variants',[]),'images':checked,'video':{'local_file':'video/product_8s.mp4','exists':(folder/'video'/'product_8s.mp4').exists(),'https_url':None},'copy':{'title_ru':None,'description_ru':None,'tags_ru':[]},'category':{'description_category_id':None,'type_id':None},'price_cny':None,'status':'draft','blockers':['俄文文案待生成','类目及必填属性待匹配','实际定价待核验','图片HTTPS托管未配置']}
 target=folder/'listing_bundle.json'
 if target.exists():raise ValueError('上架草稿已存在，保留已有编辑，未覆盖')
 target.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8');return target

def save_copy(folder,value):
 folder=Path(folder);target=folder/'listing_bundle.json'
 data=json.loads(target.read_text(encoding='utf-8-sig'))
 for key in ('title_ru','description_ru'):
  if not isinstance(value.get(key),str) or not value[key].strip():raise ValueError('文案字段无效 '+key)
 for key in ('tags_ru','missing_facts'):
  if not isinstance(value.get(key),list) or any(not isinstance(t,str) for t in value[key]):raise ValueError('文案列表无效 '+key)
 if len(value['title_ru'])>500 or len(value['description_ru'])>20000 or len(value['tags_ru'])>50:raise ValueError('文案超出本地校验上限')
 if value.get('sku')!=data['sku']:raise ValueError('文案SKU不匹配或缺失，拒绝历史文案；请生成带SKU的新文案')
 from material_guard import validate,conflict
 validate(data,value)
 value=dict(value);value['missing_facts']=[x for x in value['missing_facts'] if x.strip().lower() not in ('бренд','brand','品牌')]
 if data['copy']==value:return {'saved':True,'review_status':data.get('copy_review_status','pending_human_review')}
 if data['copy'].get('title_ru'):
  old=data['copy'];oldtext=(old.get('title_ru','')+' '+old.get('description_ru','')).lower()
  if not conflict(data,old):raise ValueError('文案已有内容，不自动覆盖')
  backup=folder/'copy_before_material_fix.json'
  if not backup.exists():backup.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
 data['copy']=value;data['copy_review_status']='pending_human_review';data['blockers']=[x for x in data['blockers'] if x!='俄文文案待生成']
 tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
 return {'saved':True,'review_status':'pending_human_review'}

def copy_complete(value):
 return isinstance(value,dict) and all(isinstance(value.get(k),str) and value[k].strip() for k in ('title_ru','description_ru')) and all(isinstance(value.get(k),list) and all(isinstance(x,str) for x in value[k]) for k in ('tags_ru','missing_facts'))

def copy_hash(value):
 return hashlib.sha256(json.dumps({k:value.get(k) for k in ('title_ru','description_ru','tags_ru')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def share_copy(folder,source,value):
 import secrets
 folder=Path(folder);target=folder/'listing_bundle.json';data=json.loads(target.read_text(encoding='utf-8-sig'))
 if not copy_complete(value):raise ValueError('首变体共用文案不完整')
 expected={**value,'sku':data['sku']};old=data.get('copy',{})
 if old.get('title_ru') and copy_hash(old)!=copy_hash(expected):
  backup=folder/('copy_before_shared_sync_'+secrets.token_hex(6)+'.json');backup.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
 data.update(copy=expected,copy_source=source,copy_shared_hash=copy_hash(value),copy_review_status='pending_human_review')
 data['blockers']=[b for b in data.get('blockers',[]) if b!='俄文文案待生成']
 tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
 return data

def refresh_assets(folder):
 folder=Path(folder);target=folder/'listing_bundle.json'
 if not target.exists():return
 data=json.loads(target.read_text(encoding='utf-8-sig'));rows=json.loads((folder/'image_manifest.json').read_text(encoding='utf-8-sig'))
 if len(rows)!=8 or [r['order'] for r in rows]!=list(range(1,9)):raise ValueError('更新草稿时图片顺序不完整')
 images=[];previous={r.get('order'):r for r in data.get('images',[])};changed=False
 for row in rows:
  name=Path(row['file'].replace('\\','/')).name;path=folder/'images'/name
  if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('更新草稿时图片校验失败')
  image={'order':row['order'],'role':row['role'],'local_file':'images/'+name,'sha256':row['sha256'],'https_url':None}
  old=previous.get(row['order'],{})
  if all(old.get(k)==image[k] for k in ('order','role','local_file','sha256')):
   image.update({k:v for k,v in old.items() if k=='https_url' or k.startswith('hosting_')})
  else:changed=True
  images.append(image)
 data['images']=images;data['video']={'local_file':'video/product_8s.mp4','exists':(folder/'video'/'product_8s.mp4').exists(),'https_url':None}
 if changed and data.get('hosting'):
  count=sum(bool(r.get('https_url')) and r.get('hosting_sha256')==r['sha256'] for r in images)
  data['hosting']={**data['hosting'],'state':'pending','verified_images':count,'message':'生成图已更新，等待自动补齐新图片链接'}
  if '图片HTTPS链接待校验' not in data.get('blockers',[]):data.setdefault('blockers',[]).append('图片HTTPS链接待校验')
 data.pop('recollection_pending',None);data['blockers']=[b for b in data.get('blockers',[]) if b!='图片重新采集中']
 tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
