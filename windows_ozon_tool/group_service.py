"""Editable whole-product plans. Pure local writes; pricing follows each edit."""
import copy,hashlib,json,re,secrets,threading
from pathlib import Path
from decimal import Decimal
from attribute_service import field_key,category_key,source_fingerprint
from variants import FIELDS,facts
from pricing_service import read,write

PARAM_KEYS={k for k,_,_ in FIELDS}
def revision(bundles):
 data=[]
 for b in bundles:
  state=b.get('attribute_draft') or {};category={k:v for k,v in (b.get('category') or {}).items() if k!='attributes_revalidation_required'}
  data.append({'sku':b.get('sku'),'offer_id':b.get('offer_id'),'category':category,'parameters':b.get('variant_parameters'),'copy':b.get('copy'),'model':b.get('model'),'brand':b.get('brand'),'attributes':{k:state.get(k) for k in ('schema_hash','values','migration_pending','source_fingerprint')},'price':b.get('price_cny'),'pricing_fingerprint':b.get('pricing_fingerprint'),'images':[{k:r.get(k) for k in ('order','role','sha256','https_url','hosting_target')} for r in b.get('images') or []],'video':{k:(b.get('video') or {}).get(k) for k in ('sha256','https_url','image_hashes')},'export_settings':b.get('export_settings'),'fulfillment':b.get('fulfillment'),'stock_revision':b.get('stock_revision')})
 return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def binding(field):
 name=(field.get('name_ru') or field.get('name','')).strip().casefold()
 for key,names in [('color',('цвет','цвет товара','颜色','商品颜色')),('material',('материал','основной материал','主体材质','主要材质')),('accessory_material',('материал подкладки','内衬材质')),('quantity',('количество предметов в комплекте','количество в упаковке','количество в упаковке, шт','количество товара в единице измерения','количество товара','единиц в одном товаре','套装件数','包装件数'))]:
  if name in names:return key,Decimal(1)
 for key,ru,zh in [('pack_length','длина упаковки','包装长'),('pack_width','ширина упаковки','包装宽'),('pack_height','высота упаковки','包装高'),('length','длина','商品长'),('width','ширина','商品宽'),('height','высота','商品高')]:
  if name in (ru+', см',ru+' (см)',zh+'(cm)'):return key,Decimal(1)
  if name in (ru+', мм',ru+' (мм)',zh+'(mm)'):return key,Decimal('.1')
 if name in ('вес товара, г','商品净重(g)'):return 'net_weight',Decimal(1)
 if name in ('вес с упаковкой, г','вес товара с упаковкой, г','包装总重(g)'):return 'pack_weight',Decimal(1)
 return None

class GroupService:
 def __init__(self,paths,attributes,pricing,store=None):
  self.paths=[Path(p) for p in paths];self.attributes=attributes;self.pricing=pricing;self.store=store;self.lock=attributes.lock;self.mutex=threading.RLock();self.status="整组草稿已加载"
 def load(self):
  with self.lock:return [read(p) for p in self.paths]
 def token(self):return revision(self.load())
 def _check(self,bundles,expected):
  if expected is not None and revision(bundles)!=expected:raise ValueError('预览内容已更新，请先核对最新表格再操作')
 def _invalidate(self,bundle):
  bundle.pop('pricing_fingerprint',None);bundle.pop('pricing_confirmed_fingerprint',None)
  bundle['price_cny']=None
  state=bundle.get('attribute_draft')
  if state:state['confirmed']=False
 def _write(self,bundles):
  all_facts='\n'.join(b['sku']+'：'+b.get('facts','') for b in bundles)
  variants=[{'sku':b['sku'],'variant_parameters':b.get('variant_parameters',{}),'facts':b.get('facts','')} for b in bundles]
  for path,b in zip(self.paths,bundles):
   b['group_facts']=all_facts;b['group_variants']=variants;write(path,b)
   if self.store:
    for task in self.store.tasks:
     if task['sku']==b['sku']:task.update(variant_parameters=copy.deepcopy(b.get('variant_parameters',{})),facts=b.get('facts',''),group_facts=all_facts,group_variants=copy.deepcopy(variants))
  if self.store:self.store.save()
 def after_edit(self,indices,refresh=True):
  if refresh:
   for n in indices:
    try:
     self.status=self.paths[n].parent.name+'：同步官方属性与已填内容'
     self.attributes.refresh(self.paths[n],force=False)
    except ValueError:pass # Draft retains the explicit missing/connection state.
  self.status='正在重新计算售价';self.pricing.calculate_all();self.attributes.wake.set();self.status='参数和自动售价已同步'
 def set_parameters(self,indices,key,values,expected=None):
  if key not in PARAM_KEYS:raise ValueError('不是可编辑的基础参数')
  if len(indices)!=len(values) or len(set(indices))!=len(indices):raise ValueError('批量目标与输入数量不一致')
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected)
    for n,value in zip(indices,values):
     b=bundles[n];p=dict(b.get('variant_parameters') or {});p[key]=str(value).strip();text=facts(p)
     b.update(variant_parameters=p,facts=text,stock=int(p.get('stock','0') or 0))
     if key=='stock':b['stock_revision']=secrets.token_hex(8)
     for field in (b.get('attribute_draft') or {}).get('fields',[]):
      if binding(field) and binding(field)[0]==key:
       state=b['attribute_draft'];state.get('values',{}).pop(field_key(field),None);state['manual_keys']=[k for k in state.get('manual_keys',[]) if k!=field_key(field)]
     self._invalidate(b)
    self._write(bundles)
   self.after_edit(indices,refresh=key not in ('cost','margin','stock'))
 def set_attributes(self,indices,key,values,expected=None):
  if len(indices)!=len(values) or len(set(indices))!=len(indices):raise ValueError('批量目标与输入数量不一致')
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected);prepared=[]
    for n,raw in zip(indices,values):
     b=bundles[n];canonical=self.attributes.prepare_values(b,key,raw);field=next(f for f in b['attribute_draft']['fields'] if field_key(f)==key)
     state=b['attribute_draft'];state.setdefault('values',{})[key]=canonical;state['manual_keys']=sorted(set(state.get('manual_keys') or [])|{key});state['confirmed']=False
     (state.get('migration_pending') or {}).pop(key,None)
     link=binding(field)
     if link and len(canonical)==1:
      param,multiplier=link;text=canonical[0].get('value','')
      if param not in ('color','material','accessory_material'):
       if param=='quantity':
        found=re.fullmatch(r'(\d+)\s*(?:шт\.?|件|pcs)?',text.strip(),re.I)
        if not found:raise ValueError('官方件数值无法对应基础数量，请选择明确的整数件数')
        text=found[1]
       else:
        try:text=str(Decimal(text)*multiplier)
        except Exception:raise ValueError('此官方属性无法自动换算基础尺寸/重量，请核对单位') from None
      b.setdefault('variant_parameters',{})[param]=text;b['facts']=facts(b['variant_parameters'])
     self._invalidate(b);prepared.append(n)
    self._write(bundles)
   self.after_edit(prepared)
 def resolve_text(self,index,key,text):
  b=self.load()[index];field=next(f for f in b['attribute_draft']['fields'] if field_key(f)==key)
  if not text.strip():return []
  labels=[v.strip() for v in text.split('；') if v.strip()] if field.get('is_collection') else [text.strip()]
  if not field.get('dictionary_id'):return [{'value':label} for label in labels]
  values=[]
  for label in labels:
   matches={}
   if len(label)>=2:
    for row in self.attributes.dictionary(b,field,label)['result']:
     if str(row.get('value','')).strip().casefold()==label.casefold():matches[row['id']]=row
   if len(matches)!=1:
    for row in self.attributes.dictionary(b,field)['result']:
     if str(row.get('value','')).strip().casefold()==label.casefold():matches[row['id']]=row
   if len(matches)!=1:raise ValueError(b['sku']+'：官方字典未唯一匹配“'+label+'”，请逐格选择官方选项')
   row=next(iter(matches.values()));values.append({'dictionary_value_id':row['id'],'value':row['value']})
  return values
 def use_only_warehouse(self,warehouses,merchant,expected=None):
  if len(warehouses)!=1:return False
  record=warehouses[0];bundles=self.load()
  indices=[n for n,b in enumerate(bundles) if (b.get('fulfillment') or {}).get('warehouse_id')!=record['warehouse_id'] or (b.get('fulfillment') or {}).get('account_id')!=merchant]
  if not indices:return False
  self.set_settings(indices,'warehouse',{'warehouse_id':record['warehouse_id'],'warehouse_name':record['name'],'account_id':merchant},expected)
  return True
 def confirm_current_categories(self,indices,expected=None):
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected)
    for n in indices:
     category=bundles[n].get('category') or {}
     if not all(type(category.get(k)) is int and category[k]>0 for k in ('description_category_id','type_id')):raise ValueError('当前没有有效类目，请搜索并选择官方类目')
    for n in indices:
     bundles[n]['category']['confirmed']=True;bundles[n]['category_match_status']='预览页已确认当前类目'
    self._write(bundles)
   self.after_edit(indices)
 def change_category(self,indices,category,expected=None):
  if not all(type(category.get(k)) is int and category[k]>0 for k in ('description_category_id','type_id')):raise ValueError('请选择官方类目与类型')
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected)
    for n in indices:
     b=bundles[n];old=b.get('attribute_draft') or {}
     if old:b['attribute_history']=old
     b.pop('attribute_draft',None);b['category']={**category,'confirmed':True,'attributes_revalidation_required':True};b['category_match_status']='预览页已选择类目';self._invalidate(b)
    self._write(bundles)
   self.after_edit(indices)
 def set_settings(self,indices,key,value,expected=None):return self.set_settings_many(indices,key,[value]*len(indices),expected)
 def set_settings_many(self,indices,key,values,expected=None):
  if not indices or len(indices)!=len(values):raise ValueError('请选择变体并填写对应的值')
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected)
    for n,value in zip(indices,values):
     b=bundles[n]
     if key=='vat':
      if value not in ('0','0.05','0.07','0.1','0.2','0.22'):raise ValueError('税率无效')
      b.setdefault('export_settings',{}).update(vat=value,currency_code='CNY')
     elif key=='currency':
      if value!='CNY':raise ValueError('当前自动售价单位为人民币，仅支持已确认店铺CNY币种')
      b.setdefault('export_settings',{}).update(currency_code='CNY',currency_confirmed=True)
     elif key=='warehouse':b['fulfillment']=copy.deepcopy(value);b['stock_revision']=secrets.token_hex(8)
     else:raise ValueError('不支持的设置')
     self._invalidate(b)
    self._write(bundles)
   self.after_edit(indices,refresh=False)
 def set_copy(self,value,expected=None):
  from listing_bundle import copy_complete
  if not copy_complete(value):raise ValueError('标题、简介、标签和缺失信息列表不完整')
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected)
    for b in bundles:b['copy']={**copy.deepcopy(value),'sku':b['sku']};self._invalidate(b)
    self._write(bundles)
   self.after_edit(list(range(len(bundles))))
