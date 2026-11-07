"""Rank live Ozon leaf types; suggestions require seller confirmation."""
import json,re,os,urllib.request,secrets
from contextlib import nullcontext
from pathlib import Path

def leaves(nodes,category=None,path=()):
 for node in nodes:
  name=node.get('category_name') or node.get('type_name','');route=path+(name,)
  cat=node.get('description_category_id',category)
  if node.get('type_id') and not node.get('disabled'):yield {'description_category_id':cat,'type_id':node['type_id'],'name':name,'path':' / '.join(route)}
  yield from leaves(node.get('children',[]),cat,route)

def commit(path,title,changes,lock=None):
 with lock if lock is not None else nullcontext():
  current=json.loads(path.read_text(encoding='utf-8-sig'))
  if (current.get('category') or {}).get('confirmed'):return False
  if (current.get('copy') or {}).get('title_ru','').lower()!=title:return False
  current.update(changes)
  temp=path.with_name(path.name+'.'+secrets.token_hex(5)+'.tmp')
  try:temp.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
  finally:
   if temp.exists():temp.unlink()
  return True

def suggest(folder,lock=None):
 path=Path(folder)/'listing_bundle.json';title=None
 try:
  with lock if lock is not None else nullcontext():
   d=json.loads(path.read_text(encoding='utf-8-sig'))
  if (d.get('category') or {}).get('confirmed'):return
  title=(d.get('copy') or {}).get('title_ru','').lower()
  if not title:return
  if not os.environ.get('OZON_CLIENT_ID') or not os.environ.get('OZON_API_KEY'):
   raise ValueError('未连接Ozon API。请点击“连接Ozon API / 重新匹配类目”，填写Client-Id与Api-Key；也可在类目窗口手动填写官方ID')
  req=urllib.request.Request('https://api-seller.ozon.ru/v1/description-category/tree',data=b'{"language":"DEFAULT"}',headers={'Content-Type':'application/json','Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY']})
  with urllib.request.urlopen(req,timeout=30) as response:tree=json.load(response)
  tokens=set(re.findall(r'[а-яё]{3,}',title));candidates=[]
  for item in leaves(tree.get('result',[])):
   words=set(re.findall(r'[а-яё]{3,}',item['name'].lower()));score=sum(any(a[:5]==b[:5] for b in tokens) for a in words)
   if score:candidates.append({**item,'score':score})
  candidates.sort(key=lambda c:(-c['score'],len(c['name'])))
  changes={'category_candidates':candidates[:10],'category_match_status':'待卖家确认或修改' if candidates else '未找到候选，请手动选择'}
  if candidates:changes['category']={**candidates[0],'confirmed':False,'method':'live_tree_keyword_suggestion'}
  if commit(path,title,changes,lock):sync_group(folder,lock)
 except Exception as e:
  if title is not None:
   try:commit(path,title,{'category_match_status':'自动推荐未完成：'+str(e)[:150]},lock)
   except (OSError,ValueError):pass

def group_key(data):
 return data.get('base_article') or data.get('copy_source') or data.get('sku')

def sync_group(folder,lock=None):
 """Share a suggested category, never overwrite another confirmed variant."""
 folder=Path(folder);source_path=folder/'listing_bundle.json';changed=0
 with lock if lock is not None else nullcontext():
  source=json.loads(source_path.read_text(encoding='utf-8-sig'));category=source.get('category') or {}
  if not category.get('type_id') or not category.get('description_category_id'):return 0
  for path in folder.parent.glob('*/listing_bundle.json'):
   if path==source_path:continue
   try:
    current=json.loads(path.read_text(encoding='utf-8-sig'))
    if not group_key(source) or group_key(current)!=group_key(source) or (current.get('category') or {}).get('confirmed'):continue
    # Different titles can mean an old task whose copy has not yet been synchronized.
    if (current.get('copy') or {}).get('title_ru')!=(source.get('copy') or {}).get('title_ru'):continue
    value={**category,'confirmed':bool(category.get('confirmed') and category.get('group_confirmed')),'method':'shared_group_suggestion','source_sku':source.get('sku')}
    changes={'category':value,'category_candidates':source.get('category_candidates') or [category],'category_match_status':'整组类目已由卖家确认' if value['confirmed'] else '已沿用同组类目，待卖家确认或修改'}
    if all(current.get(k)==v for k,v in changes.items()):continue
    current.update(changes);atomic_write(path,current);changed+=1
   except (OSError,ValueError,TypeError):continue
 return changed

def atomic_write(path,data):
 path=Path(path);temp=path.with_name(path.name+'.'+secrets.token_hex(5)+'.tmp')
 try:temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
 finally:
  if temp.exists():temp.unlink()

def confirm_group(folder,category,apply_group=True,lock=None):
 folder=Path(folder);target=folder/'listing_bundle.json';changed=0
 if not all(isinstance(category.get(k),int) and category[k]>0 for k in ('description_category_id','type_id')):raise ValueError('类目ID和商品类型ID须为正整数')
 with lock if lock is not None else nullcontext():
  selected=json.loads(target.read_text(encoding='utf-8-sig'));key=group_key(selected)
  paths=[target]+([p for p in folder.parent.glob('*/listing_bundle.json') if p!=target] if apply_group and key else [])
  for path in paths:
   try:data=json.loads(path.read_text(encoding='utf-8-sig'))
   except (OSError,ValueError):
    if path==target:raise
    continue
   if path!=target and (group_key(data)!=key or (data.get('category') or {}).get('confirmed')):continue
   data['category']={**category,'confirmed':True,'group_confirmed':bool(apply_group),'attributes_revalidation_required':True}
   data['category_match_status']='卖家已确认类目；发布前仍须核验必填属性'
   data.pop('pricing_fingerprint',None);data.pop('pricing_confirmed_fingerprint',None)
   prior=(data.get('auto_pricing') or {}).get('price_cny')
   if data.get('price_cny') is not None and str(data['price_cny'])==str(prior):data['price_cny']=None
   data['auto_pricing']=None
   atomic_write(path,data);changed+=1
 return changed

def repair_groups(products,lock=None,allow_network=True):
 """Resume old groups after restart, one live suggestion per product group."""
 products=Path(products);groups={}
 with lock if lock is not None else nullcontext():
  for path in products.glob('*/listing_bundle.json'):
   try:
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data,dict):groups.setdefault(group_key(data) or str(path),[]).append((path,data))
   except (OSError,ValueError):continue
 for rows in groups.values():
  available=next(((p,d) for p,d in sorted(rows,key=lambda row:(not bool((row[1].get('category') or {}).get('confirmed')),row[1].get('variant_index') or 1)) if (d.get('category') or {}).get('type_id')),None)
  if available:sync_group(available[0].parent,lock);continue
  path,data=min(rows,key=lambda row:row[1].get('variant_index') or 1)
  if allow_network and (data.get('copy') or {}).get('title_ru'):suggest(path.parent,lock)
