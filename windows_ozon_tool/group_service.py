"""Editable whole-product plans. Pure local writes; pricing follows each edit."""
import copy,hashlib,json,re,secrets,threading
from pathlib import Path
from decimal import Decimal
from attribute_service import field_key,category_key,source_fingerprint
from variants import FIELDS,facts
from pricing_service import read,write

PARAM_KEYS={k for k,_,_ in FIELDS}
def revision(bundles,legacy=False):
 data=[]
 for b in bundles:
  state=b.get('attribute_draft') or {};category={k:v for k,v in (b.get('category') or {}).items() if k!='attributes_revalidation_required'}
  data.append({'sku':b.get('sku'),'offer_id':b.get('offer_id'),'category':category,'parameters':b.get('variant_parameters'),'copy':b.get('copy'),'model':b.get('model'),'brand':b.get('brand'),'attributes':{k:state.get(k) for k in ('schema_hash','values','migration_pending','source_fingerprint')},'price':b.get('price_cny'),'manual_price':b.get('manual_price'),'pricing_fingerprint':b.get('pricing_fingerprint'),'images':[{k:r.get(k) for k in ('order','role','sha256','https_url','hosting_target')} for r in b.get('images') or []],'video':{k:(b.get('video') or {}).get(k) for k in ('sha256','https_url','image_hashes')},'export_settings':b.get('export_settings'),'fulfillment':b.get('fulfillment'),'stock_revision':b.get('stock_revision'),'reference_decisions':b.get('reference_decisions'),'asset_review':b.get('asset_review'),'regeneration_pending':True if b.get('image_regeneration_jobs') else b.get('regeneration_pending')})
 if legacy:
  for row in data:row.pop('asset_review',None);row.pop('regeneration_pending',None)
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
  self.paths=[Path(p) for p in paths];self.attributes=attributes;self.pricing=pricing;self.store=store;self.lock=attributes.lock;self.mutex=getattr(attributes,'business_lock',None) or threading.RLock();attributes.business_lock=self.mutex;self.status="整组草稿已加载"
 def load(self):
  with self.lock:return [read(p) for p in self.paths]
 def token(self):return revision(self.load())
 def _check(self,bundles,expected):
  if expected is not None and revision(bundles)!=expected:raise ValueError('预览内容已更新，请先核对最新表格再操作')
 def _invalidate(self,bundle):
  bundle.pop('pricing_fingerprint',None);bundle.pop('pricing_confirmed_fingerprint',None)
  if not bundle.get('manual_price'):bundle['price_cny']=None
  state=bundle.get('attribute_draft')
  if state:state['confirmed']=False
 def _write(self,bundles):
  prepared={b['sku']:{'sku':b['sku'],'variant_parameters':b.get('variant_parameters',{}),'facts':b.get('facts','')} for b in bundles}
  existing=(bundles[0].get('group_variants') or []) if bundles else []
  variants=[copy.deepcopy(prepared.pop(r['sku'],r)) for r in existing if isinstance(r,dict) and r.get('sku')]
  variants.extend(prepared.values());all_facts='\n'.join(r['sku']+'：'+r.get('facts','') for r in variants)
  for path,b in zip(self.paths,bundles):
   b['group_facts']=all_facts;b['group_variants']=variants;write(path,b)
   if self.store:
    for task in self.store.tasks:
     if task['sku']==b['sku']:task.update(variant_parameters=copy.deepcopy(b.get('variant_parameters',{})),facts=b.get('facts',''),group_facts=all_facts,group_variants=copy.deepcopy(variants))
  if self.store:
   group_skus={r['sku'] for r in variants}
   for task in self.store.tasks:
    if task['sku'] in group_skus:task.update(group_facts=all_facts,group_variants=copy.deepcopy(variants))
   self.store.save()
 def after_edit(self,indices,refresh=True,force=False):
  errors=[]
  if refresh:
   forced=set()
   for n in indices:
    try:
     self.status=self.paths[n].parent.name+'：同步官方属性与已填内容'
     key=category_key(read(self.paths[n]));self.attributes.refresh(self.paths[n],force=force and key not in forced);forced.add(key)
    except ValueError as exc:errors.append(self.paths[n].parent.name+'：'+str(exc))
  self.status='正在重新计算售价';self.pricing.calculate_all();self.attributes.wake.set();self.status='部分属性未同步：'+'；'.join(errors) if errors else '参数和自动售价已同步'
 def refresh_preview(self):
  with self.mutex:
   self.after_edit(list(range(len(self.paths))),refresh=True,force=False)
   return self.status
 def set_parameters(self,indices,key,values,expected=None):
  if key not in PARAM_KEYS:raise ValueError('不是可编辑的基础参数')
  if len(indices)!=len(values) or len(set(indices))!=len(indices):raise ValueError('批量目标与输入数量不一致')
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected);before=copy.deepcopy(bundles)
    for n,value in zip(indices,values):
     b=bundles[n];p=dict(b.get('variant_parameters') or {});p[key]=str(value).strip();text=facts(p)
     b.update(variant_parameters=p,facts=text,stock=int(p.get('stock','0') or 0))
     if key=='stock':b['stock_revision']=secrets.token_hex(8)
     for field in (b.get('attribute_draft') or {}).get('fields',[]):
      if binding(field) and binding(field)[0]==key:
       state=b['attribute_draft'];state.get('values',{}).pop(field_key(field),None);state['manual_keys']=[k for k in state.get('manual_keys',[]) if k!=field_key(field)]
     self._invalidate(b)
    from asset_state import mark_changes
    mark_changes(before,bundles);self._write(bundles)
   self.after_edit(indices,refresh=key not in ('cost','margin','stock'))
 def set_attributes(self,indices,key,values,expected=None):
  if len(indices)!=len(values) or len(set(indices))!=len(indices):raise ValueError('批量目标与输入数量不一致')
  # Common text has one owner regardless of the editor used.
  from tag_rules import is_tag_field,is_series_field,normalize_tags
  source=self.load();field=next((f for f in (source[indices[0]].get('attribute_draft') or {}).get('fields',[]) if field_key(f)==key),None) if indices else None
  if field:
   name=(field.get('name_ru') or field.get('name','')).casefold().strip()
   copy_key='tags_ru' if is_tag_field(field) else 'description_ru' if field['id']==4191 or name in ('аннотация','описание товара','简介') else 'title_ru' if not is_series_field(field) and (field['id']==4180 or name in ('название','名称')) else None
   if copy_key:
    proposed=[' '.join(v.get('value','') for v in rows) for rows in values]
    if len(set(proposed))>1:raise ValueError('标题、简介和标签为全组共用，请填写同一个值')
    value=copy.deepcopy(source[0].get('copy') or {});value[copy_key]=normalize_tags(proposed[0]) if copy_key=='tags_ru' else proposed[0]
    return self.set_copy(value,expected)
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected);before=copy.deepcopy(bundles);prepared=[]
    for n,raw in zip(indices,values):
     b=bundles[n];canonical=self.attributes.prepare_values(b,key,raw);field=next(f for f in b['attribute_draft']['fields'] if field_key(f)==key)
     state=b['attribute_draft'];state.setdefault('values',{})[key]=canonical;state['manual_keys']=sorted(set(state.get('manual_keys') or [])|{key});state['confirmed']=False
     (state.get('migration_pending') or {}).pop(key,None)
     link=binding(field)
     if link and len(canonical)>1 and link[0] in ('color','material','accessory_material'):
      b.setdefault('variant_parameters',{})[link[0]]='；'.join(v.get('value','') for v in canonical);b['facts']=facts(b['variant_parameters'])
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
    from asset_state import mark_changes
    mark_changes(before,bundles);self._write(bundles)
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
 def ensure_initial_stock(self,target):
  changed=False
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths]
    for b in bundles:
     p=b.setdefault('variant_parameters',{})
     if str(p.get('stock',''))==str(target):continue
     p['stock']=str(target);b['stock']=target;b['facts']=facts(p);b['stock_revision']=secrets.token_hex(8);changed=True
    if changed:self._write(bundles)
  return changed
 def ensure_fixed_vat(self):
  from prefill_rules import fixed_settings
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];changed=False
    for bundle in bundles:changed=fixed_settings(bundle) or changed
    if changed:self._write(bundles)
  return changed
 def set_prices(self,indices,values,expected=None):
  if not indices or len(indices)!=len(values):raise ValueError('请选择变体并填写对应售价')
  prices=[]
  for value in values:
   try:price=Decimal(str(value))
   except Exception:raise ValueError('售价须为有效正数') from None
   if not price.is_finite() or price<=0 or price!=price.quantize(Decimal('.01')):raise ValueError('售价须为正数且最多两位小数')
   prices.append(format(price.quantize(Decimal('.01')),'f'))
  with self.mutex:
   with self.lock:
    bundles=[read(p) for p in self.paths];self._check(bundles,expected)
    for n,price in zip(indices,prices):
     b=bundles[n];b.update(price_cny=price,manual_price=True,pricing_confirmed_fingerprint=b.get('pricing_fingerprint'),pricing_confirmed_price=price,pricing_status='采用手动售价，自动估算供参考')
    self._write(bundles)
  self.pricing.calculate_all()
  return len(prices)
 def confirm_references(self,indices,key,expected=None,skip=False):
  from assisted_fields import inline_references
  with self.mutex:
   bundles=self.load();self._check(bundles,expected);changes=[]
   for n in indices:
    row=inline_references(bundles[n]).get(key)
    if row is None:continue
    if skip:
     if row['required']:raise ValueError('平台必填属性不能跳过，请填写已核实值')
     changes.append((n,row,None));continue
    if not row['suggested']:raise ValueError('该字段没有可靠参考值，请双击填写或选择已核实的官方选项')
    values=self.resolve_text(n,key,row['suggested']);canonical=self.attributes.prepare_values(bundles[n],key,values);changes.append((n,row,canonical))
   with self.lock:
    latest=[read(p) for p in self.paths];self._check(latest,expected)
    for n,row,values in changes:
     b=latest[n];b.setdefault('reference_decisions',{})[key]={'source':source_fingerprint(b),'action':'skip' if skip else 'accepted','evidence':row['evidence'],'confidence':row['confidence']}
     if not skip:
      state=b['attribute_draft'];state.setdefault('values',{})[key]=values;state['manual_keys']=sorted(set(state.get('manual_keys') or [])|{key});state['confirmed']=False
     # Attribute-only reference choices do not change pricing inputs.
    self._write(latest)
   self.attributes.wake.set()
  return len(changes)
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
      if value!='0':raise ValueError('实际增值税率已按你的规则固定为0')
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
    from tag_rules import normalize_tags,is_tag_field
    from asset_reconcile import copy_basis
    fingerprint=copy_basis(bundles)
    value={**value,'tags_ru':normalize_tags(value.get('tags_ru'))}
    for b in bundles:
     b['copy']={**copy.deepcopy(value),'sku':b['sku']};b['copy_basis']=fingerprint;self._invalidate(b)
     if b.get('asset_review'):b['asset_review']['copy']=False
     state=b.get('attribute_draft') or {}
     for field in state.get('fields',[]):
      name=(field.get('name_ru') or field.get('name','')).casefold().strip()
      if is_tag_field(field) or field['id'] in (4191,4180) or name in ('аннотация','название'):
       k=field_key(field);state.get('values',{}).pop(k,None);state['manual_keys']=[x for x in state.get('manual_keys',[]) if x!=k]
    self._write(bundles)
    if self.store:self.store.sync_shared_copies()
   self.after_edit(list(range(len(bundles))))

def preview_changes(before,after,allow_automatic=False):
 """Compare merchant-visible content, not refreshed cache timestamps/fingerprints."""
 def sections(b):
  state=b.get('attribute_draft') or {};category=b.get('category') or {}
  return {'类目':{k:category.get(k) for k in ('description_category_id','type_id','name','confirmed')},'基础参数':b.get('variant_parameters'),'共用文案':b.get('copy'),'型号与品牌':[b.get('model'),b.get('brand')],'官方属性':state.get('values'),'官方字段要求':sorted([{k:f.get(k) for k in ('id','attribute_complex_id','name','name_ru','type','dictionary_id','is_required','is_collection')} for f in state.get('fields',[])],key=lambda f:(f.get('attribute_complex_id') or 0,f['id'])),'售价':str(b.get('price_cny')),'手动售价设置':b.get('manual_price'),'图片':[{k:r.get(k) for k in ('order','role','sha256','https_url','hosting_target')} for r in b.get('images') or []],'视频':{k:(b.get('video') or {}).get(k) for k in ('sha256','https_url','image_hashes')},'税率与币种':b.get('export_settings'),'仓库与库存设置':[b.get('fulfillment'),b.get('stock_revision')],'参考值核对':b.get('reference_decisions')}
 if [b.get('sku') for b in before]!=[b.get('sku') for b in after]:return ['变体清单发生变化']
 result=[]
 for old,new in zip(before,after):
  left,right=sections(old),sections(new)
  if allow_automatic:
   if (new.get('export_settings') or {}).get('vat')=='0':left['税率与币种']={**(left['税率与币种'] or {}),'vat':'0'}
   from tag_rules import normalize_tags
   for side in (left,right):
    if isinstance(side['共用文案'],dict):side['共用文案']={**side['共用文案'],'tags_ru':normalize_tags(side['共用文案'].get('tags_ru'))}
   keys=set((old.get('attribute_draft') or {}).get('auto_reference_keys') or [])|set((new.get('attribute_draft') or {}).get('auto_reference_keys') or [])
   keys-=set((new.get('attribute_draft') or {}).get('manual_keys') or [])
   from tag_rules import is_tag_field,is_series_field
   for field in (new.get('attribute_draft') or {}).get('fields',[]):
    key=field_key(field);values=((new.get('attribute_draft') or {}).get('values') or {}).get(key) or []
    if is_series_field(field) and values==[{'value':'1'}]:keys.add(key)
    if is_tag_field(field) and ' '.join(v.get('value','') for v in values)==' '.join(normalize_tags((new.get('copy') or {}).get('tags_ru'))):keys.add(key)
   for side in (left,right):side['官方属性']={k:v for k,v in (side['官方属性'] or {}).items() if k not in keys}
   estimate=(new.get('auto_pricing') or {}).get('price_cny')
   if not new.get('manual_price') and estimate is not None and str(estimate)==str(new.get('price_cny')):left['售价']=right['售价']
  for name in left:
   if left[name]==right[name]:continue
   text=str(new.get('sku',''))+'：'+name+'变化'
   if name=='售价':text+='（'+left[name]+' → '+right[name]+'）'
   elif name in ('基础参数','官方属性'):
    l=left[name] or {};r=right[name] or {};keys=[k for k in set(l)|set(r) if l.get(k)!=r.get(k)]
    labels={field_key(f):f.get('name') or f.get('name_ru') or field_key(f) for f in (new.get('attribute_draft') or {}).get('fields',[])}
    text+='：'+'、'.join(labels.get(k,k) for k in sorted(keys))
   result.append(text)
 return result
