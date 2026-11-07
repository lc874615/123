"""Rank live Ozon leaf types; suggestions require seller confirmation."""
import json,re,os,urllib.request
from pathlib import Path

def leaves(nodes,category=None,path=()):
 for node in nodes:
  name=node.get('category_name') or node.get('type_name','');route=path+(name,)
  cat=node.get('description_category_id',category)
  if node.get('type_id') and not node.get('disabled'):yield {'description_category_id':cat,'type_id':node['type_id'],'name':name,'path':' / '.join(route)}
  yield from leaves(node.get('children',[]),cat,route)

def suggest(folder):
 path=Path(folder)/'listing_bundle.json'
 try:
  d=json.loads(path.read_text(encoding='utf-8-sig'))
  req=urllib.request.Request('https://api-seller.ozon.ru/v1/description-category/tree',data=b'{"language":"DEFAULT"}',headers={'Content-Type':'application/json','Client-Id':os.environ['OZON_CLIENT_ID'],'Api-Key':os.environ['OZON_API_KEY']})
  with urllib.request.urlopen(req,timeout=30) as response:tree=json.load(response)
  title=d['copy'].get('title_ru','').lower();tokens=set(re.findall(r'[а-яё]{3,}',title))
  candidates=[]
  for item in leaves(tree.get('result',[])):
   words=set(re.findall(r'[а-яё]{3,}',item['name'].lower()));score=sum(any(a[:5]==b[:5] for b in tokens) for a in words)
   if score:candidates.append({**item,'score':score})
  candidates.sort(key=lambda c:(-c['score'],len(c['name'])))
  d=json.loads(path.read_text(encoding='utf-8-sig'));d['category_candidates']=candidates[:10]
  if candidates:d['category']={**candidates[0],'confirmed':False,'method':'live_tree_keyword_suggestion'}
  d['category_match_status']='待卖家确认或修改' if candidates else '未找到候选，请手动选择'
  path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 except Exception as e:
  d=json.loads(path.read_text(encoding='utf-8-sig'));d['category_match_status']='自动推荐未完成：'+str(e)[:150];path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
