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
 copy_prompt='根据以下商品事实生成俄文Ozon标题、简介和标签。自然覆盖相关长尾词，禁止重复堆词和编造承重、认证、功能、品牌。未知留空。只输出JSON：title_ru、description_ru、tags_ru数组、missing_facts数组。商品事实：'+facts
 (folder/'copy_prompt.txt').write_text(copy_prompt,encoding='utf-8')
 bundle={'sku':task['sku'],'brand':'Нет бренда','stock':1000,'facts':facts,'images':checked,'video':{'local_file':'video/product_8s.mp4','exists':(folder/'video'/'product_8s.mp4').exists(),'https_url':None},'copy':{'title_ru':None,'description_ru':None,'tags_ru':[]},'category':{'description_category_id':None,'type_id':None},'price_cny':None,'status':'draft','blockers':['俄文文案待生成','类目及必填属性待匹配','实际定价待核验','图片HTTPS托管未配置']}
 target=folder/'listing_bundle.json'
 if target.exists():raise ValueError('上架草稿已存在，保留已有编辑，未覆盖')
 target.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8');return target
