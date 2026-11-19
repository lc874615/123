"""Complete category-specific official color dictionaries; no guessed IDs."""
import copy,time
from pricing_service import write
from contextlib import nullcontext
from attribute_service import field_key,category_key
from color_selection import is_color_field

def _key(value):return str(value or '').strip().casefold().replace('ё','е')

def pages(service,bundle,field,language,force=False):
 cursor=0;seen=set();rows={}
 for _ in range(1000):
  response=service.dictionary(bundle,field,last_value_id=cursor,force=force,language=language)
  batch=response.get('result') or []
  for row in batch:
   if type(row.get('id')) is not int or row['id']<=0:raise ValueError('官方颜色存在无效记录，未确认读取完整')
   rows[row['id']]=copy.deepcopy(row)
  more=response.get('has_next',False)
  if more is False or more is None or str(more).casefold()=='false':return rows
  if more is not True and str(more).casefold()!='true':raise ValueError('官方颜色分页标志异常，未确认读取完整')
  next_cursor=batch[-1].get('id') if batch else None
  if type(next_cursor) is not int or next_cursor<=0 or next_cursor==cursor or next_cursor in seen:raise ValueError('官方颜色分页未前进，未确认读取完整')
  seen.add(next_cursor);cursor=next_cursor
 raise ValueError('官方颜色分页超过保护上限，未确认读取完整')

def fields(service,bundle,force=False):
 category,type_id=category_key(bundle)
 base={'description_category_id':category,'type_id':type_id}
 cached=service.schema_cache.get((category,type_id))
 if cached and not force and 0<=time.time()-cached[0]<86400:
  zh,ru=copy.deepcopy(cached[1:]);names={field_key(f):f for f in ru}
  return [{**f,'name_ru':names.get(field_key(f),{}).get('name',f.get('name',''))} for f in zh]
 zh=service.caller('/v1/description-category/attribute',{**base,'language':'ZH_HANS'})['result']
 ru=service.caller('/v1/description-category/attribute',{**base,'language':'RU'})['result'];names={field_key(f):f for f in ru}
 return [{**f,'name_ru':names.get(field_key(f),{}).get('name',f.get('name',''))} for f in zh]

def load(service,bundles,force=False):
 if not bundles:raise ValueError('请先选择用于读取官方颜色的商品类目')
 catalogs=[];contexts=set();total=0;limits=[]
 for bundle in bundles:
  context=category_key(bundle)
  if context in contexts:continue
  contexts.add(context)
  field=next((f for f in fields(service,bundle,force) if is_color_field(f,False) and f.get('dictionary_id')),None)
  if not field:raise ValueError('该类目没有可读取的官方颜色字典；请沿用真实颜色并在参数页核对')
  zh=pages(service,bundle,field,'ZH_HANS',force);ru=pages(service,bundle,field,'RU',force)
  if set(zh)!=set(ru):raise ValueError('中俄颜色字典记录不一致，未确认完整，请重新读取')
  category,type_id=context
  with getattr(service,'io_lock',nullcontext()):
   write(service.root/f'{category}-{type_id}-{field["id"]}.json',{str(k):v for k,v in ru.items()})
   write(service.root/f'{category}-{type_id}-{field["id"]}-fullcolors-{field["dictionary_id"]}.json',{'fetched_at':time.time(),'rows':list(ru.values())})
  records={}
  for identifier,row in ru.items():
   label=str(row.get('value') or '').strip()
   if not label:continue
   if _key(label) in records and records[_key(label)]['id']!=identifier:raise ValueError('官方颜色出现重名选项，无法唯一确认，请在参数页核对')
   records[_key(label)]={'value':label,'label':str(zh[identifier].get('value') or label),'id':identifier,'official':True}
  catalogs.append(records);total+=len(records);limits.append(int(field.get('max_value_count') or 100) if field.get('is_collection') else 1)
 common=set(catalogs[0]).intersection(*(set(r) for r in catalogs[1:]))
 rows=[catalogs[0][key] for key in catalogs[0] if key in common]
 if not rows:raise ValueError('所选类目没有共同可选颜色，请逐变体核对')
 return {'rows':rows,'total_read':total,'contexts':len(contexts),'maximum':min(limits),'complete':True}

def preload(service,category,force=False):
 """Read and cache the official palette immediately after category choice.

 The creation grid has no listing bundle yet.  A minimal confirmed category is
 enough because colors are a category dictionary, not a product attribute.
 """
 return load(service,[{'sku':'creation-color-catalog','category':{**dict(category or {}),'confirmed':True}}],force)
