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
  if current.get('category',{}).get('confirmed'):return False
  if current.get('copy',{}).get('title_ru','').lower()!=title:return False
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
  if d.get('category',{}).get('confirmed'):return
  title=d['copy'].get('title_ru','').lower()
  req=urllib.request.Request('https://api-seller.ozon.ru/v1/description-category/tree',data=b'{"language":"DEFAULT"}',headers={'Content-Type':'application/json','Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY']})
  with urllib.request.urlopen(req,timeout=30) as response:tree=json.load(response)
  tokens=set(re.findall(r'[а-яё]{3,}',title));candidates=[]
  for item in leaves(tree.get('result',[])):
   words=set(re.findall(r'[а-яё]{3,}',item['name'].lower()));score=sum(any(a[:5]==b[:5] for b in tokens) for a in words)
   if score:candidates.append({**item,'score':score})
  candidates.sort(key=lambda c:(-c['score'],len(c['name'])))
  changes={'category_candidates':candidates[:10],'category_match_status':'待卖家确认或修改' if candidates else '未找到候选，请手动选择'}
  if candidates:changes['category']={**candidates[0],'confirmed':False,'method':'live_tree_keyword_suggestion'}
  commit(path,title,changes,lock)
 except Exception as e:
  if title is not None:
   try:commit(path,title,{'category_match_status':'自动推荐未完成：'+str(e)[:150]},lock)
   except (OSError,ValueError):pass
