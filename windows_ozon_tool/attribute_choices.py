"""Official dictionary selection state shared by single and bulk preview editors."""
from attribute_service import field_key,category_key,validate_values

def value_limit(field):
 return int(field.get('max_value_count') or 100) if field.get('is_collection') else 1

class OfficialChoices:
 def __init__(self,service,bundles,key):
  if not bundles:raise ValueError('请先选择变体')
  self.service=service;self.bundles=bundles;self.key=key;self.fields=[];self.contexts={};self.records={};self.selected={};self.query=None;self.visible=[]
  prior=[]
  for b in bundles:
   field=next((f for f in (b.get('attribute_draft') or {}).get('fields',[]) if field_key(f)==key),None)
   if not field or not field.get('dictionary_id'):raise ValueError(b.get('sku','')+'：此参数不属于当前类目的官方字典，不能统一选择')
   self.fields.append(field);ctx=(*category_key(b),field['id'],field['dictionary_id']);self.contexts.setdefault(ctx,{'bundle':b,'field':field,'rows':{},'cursor':0,'more':True})
   values=(b.get('attribute_draft') or {}).get('values',{}).get(key,[]);prior.append({v['dictionary_value_id']:v for v in values if v.get('dictionary_value_id')})
  self.maximum=min(value_limit(f) for f in self.fields);self.multiple=self.maximum>1
  common=set(prior[0]).intersection(*[set(r) for r in prior[1:]])
  self.selected={i:dict(prior[0][i]) for i in prior[0] if i in common};self.records={i:{'id':i,'value':v.get('value','')} for i,v in self.selected.items()}
 def load(self,query='',next_page=False,force=False):
  query=query.strip()
  if query!=self.query or not next_page:
   self.query=query
   for ctx in self.contexts.values():ctx.update(rows={},cursor=0,more=True)
  for ctx in self.contexts.values():
   if not ctx['more']:continue
   response=self.service.dictionary(ctx['bundle'],ctx['field'],query,ctx['cursor'],force=force);rows=response.get('result') or []
   for row in rows:
    if type(row.get('id')) is int and row['id']>0:ctx['rows'][row['id']]=dict(row)
   more=response.get('has_next',False)
   if more is True or str(more).lower()=='true':
    cursor=rows[-1]['id'] if rows else ctx['cursor']
    if not rows or cursor==ctx['cursor']:raise ValueError('官方字典分页未前进，请刷新后重试')
    ctx.update(cursor=cursor,more=True)
   else:ctx['more']=False
  contexts=list(self.contexts.values());common=set(contexts[0]['rows']).intersection(*[set(c['rows']) for c in contexts[1:]])
  self.visible=[r for i,r in contexts[0]['rows'].items() if i in common];self.records.update({r['id']:r for r in self.visible});return list(self.visible)
 @property
 def has_more(self):return any(c['more'] for c in self.contexts.values())
 def toggle(self,identifier):
  if identifier in self.selected:self.selected.pop(identifier);return
  if identifier not in self.records:raise ValueError('此选项未从官方接口读取')
  row=self.records[identifier]
  if not self.multiple:self.selected={}
  if len(self.selected)>=self.maximum:raise ValueError('该参数最多允许选择'+str(self.maximum)+'项')
  self.selected[identifier]={'dictionary_value_id':identifier,'value':row['value']}
 def clear(self):self.selected={}
 def values(self):
  values=[dict(v) for v in self.selected.values()]
  if values:
   for f in self.fields:validate_values(f,values)
  # Validate IDs independently against every selected variant's category cache.
  return [self.service.prepare_values(b,self.key,values) for b in self.bundles]
