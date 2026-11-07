"""Prepare a local handoff without mistaking local paths for hosted Ozon images."""
import json,hashlib
from pathlib import Path

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
 copy_prompt='以下为同一商品全部变体，标题、简介和标签统一一套。只描述共同属性，差异按选项分别说明，不要把某一颜色或尺寸当作全部规格。根据以下商品事实生成俄文Ozon标题、简介和标签。自然覆盖相关长尾词，禁止重复堆词和编造承重、认证、功能、品牌。品牌固定无品牌（Нет бренда），不要将品牌列为缺失项。未知留空。只输出JSON：title_ru、description_ru、tags_ru数组、missing_facts数组。商品事实：'+copy_facts
 (folder/'copy_prompt.txt').write_text(copy_prompt,encoding='utf-8')
 bundle={'sku':task['sku'],'offer_id':task['sku'],'base_article':task.get('base_article',task['sku']),'model':task.get('model'),'variant_index':task.get('variant_index'),'variant_parameters':task.get('variant_parameters',{}),'brand':'Нет бренда','stock':int(task.get('variant_parameters',{}).get('stock','1000')),'facts':facts,'images':checked,'video':{'local_file':'video/product_8s.mp4','exists':(folder/'video'/'product_8s.mp4').exists(),'https_url':None},'copy':{'title_ru':None,'description_ru':None,'tags_ru':[]},'category':{'description_category_id':None,'type_id':None},'price_cny':None,'status':'draft','blockers':['俄文文案待生成','类目及必填属性待匹配','实际定价待核验','图片HTTPS托管未配置']}
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
 material_text=(value['title_ru']+' '+value['description_ru']).lower()
 if '聚丙烯' in data['facts'] and ('картон' in material_text or 'бумаг' in material_text):raise ValueError('材质冲突：商品为聚丙烯，文案含纸板或纸材')
 if '纸板' in data['facts'] and 'полипропилен' in material_text:raise ValueError('材质冲突：商品为纸板，文案含聚丙烯')
 value=dict(value);value['missing_facts']=[x for x in value['missing_facts'] if x.strip().lower() not in ('бренд','brand','品牌')]
 if data['copy']==value:return {'saved':True,'review_status':data.get('copy_review_status','pending_human_review')}
 if data['copy'].get('title_ru'):
  old=data['copy'];oldtext=(old.get('title_ru','')+' '+old.get('description_ru','')).lower()
  conflict=('聚丙烯' in data['facts'] and 'картон' in oldtext) or ('纸板' in data['facts'] and 'полипропилен' in oldtext)
  if not conflict:raise ValueError('文案已有内容，不自动覆盖')
  backup=folder/'copy_before_material_fix.json'
  if not backup.exists():backup.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
 data['copy']=value;data['copy_review_status']='pending_human_review';data['blockers']=[x for x in data['blockers'] if x!='俄文文案待生成']
 tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
 return {'saved':True,'review_status':'pending_human_review'}
