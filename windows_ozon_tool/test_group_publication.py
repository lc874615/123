import copy,shutil,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import test_attributes as fixtures
import test_pricing as pricing_fixtures
from attribute_service import AttributeService,field_key
from group_service import GroupService,revision
from publication_service import PublicationService,Rejected
from pricing_service import PricingService,read,write

class FakeApi:
 def __init__(self):
  self.calls=[];self.items={};self.stocks={};self.import_error=None;self.stock_error=None;self.import_pending=False;self.warehouse_active=True;self.moderate='approved'
 def __call__(self,path,body):
  self.calls.append((path,copy.deepcopy(body)))
  if path.endswith('/attribute'):
   fields=copy.deepcopy(fixtures.FIELDS)
   fields.append({'id':600,'name':'包装长(mm)','name_ru':'Длина упаковки, мм','type':'Decimal'})
   if body['type_id']==20:fields.append({'id':555,'name':'保养','name_ru':'Рекомендации по уходу','type':'string'})
   else:fields.append({'id':777,'name':'新类目参数','name_ru':'Новый параметр','type':'string','is_required':True})
   if body.get('language')=='RU':
    for f in fields:f['name']=f.get('name_ru',f['name'])
   return {'result':fields}
  if '/attribute/values' in path:
   value=body.get('value') or ('Нет бренда' if body['attribute_id']==85 else 'Картон')
   return {'result':[{'id':body['type_id']*100+body['attribute_id'],'value':value}],'has_next':False}
  if path=='/v2/warehouse/list':return {'warehouses':[{'warehouse_id':77,'name':'Synthetic RFBS','status':'created' if self.warehouse_active else 'disabled','is_rfbs':True},{'warehouse_id':88,'name':'FBS','status':'created','is_rfbs':False},{'warehouse_id':99,'name':'blocked','status':'blocked','is_rfbs':True}],'has_next':False}
  if path=='/v3/product/import':
   for i,item in enumerate(body['items']):self.items[item['offer_id']]={**copy.deepcopy(item),'id':100+i}
   if self.import_error:raise self.import_error
   return {'result':{'task_id':501}}
  if path=='/v1/barcode/generate':
   for item in self.items.values():
    if item['id'] in body['product_ids']:item['barcodes']=['OZN'+str(item['id'])]
   return {'errors':[]}
  if path=='/v1/product/import/prices':
   for row in body['prices']:self.items[row['offer_id']].update(copy.deepcopy(row))
   return {'result':[{'offer_id':r['offer_id'],'updated':True,'errors':[]} for r in body['prices']]}
  if path=='/v1/product/import/info':return {'result':{'items':[{'offer_id':o,'product_id':v['id'],'status':'pending' if self.import_pending else 'imported','errors':[]} for o,v in self.items.items()]}}
  if path=='/v3/product/info/list':
   rows=[]
   for offer in body['offer_id']:
    if offer not in self.items:continue
    item=copy.deepcopy(self.items[offer]);stock=self.stocks.get((offer,77),0);item.update(statuses={'is_created':True,'moderate_status':self.moderate},availabilities=[{'availability':'AVAILABLE' if stock>0 else 'HIDDEN'}],visibility_details={'has_price':True,'has_stock':stock>0});rows.append(item)
   return {'items':rows}
  if path=='/v2/products/stocks':
   if self.stock_error=='before':raise ValueError('response lost')
   for row in body['stocks']:self.stocks[(row['offer_id'],row['warehouse_id'])]=row['stock']
   if self.stock_error=='after':raise ValueError('response lost')
   return {'result':[{**r,'updated':True,'errors':[]} for r in body['stocks']]}
  if path=='/v2/product/info/stocks-by-warehouse/fbs':return {'products':[{'offer_id':o,'warehouse_id':w,'free_stock':v} for (o,w),v in self.stocks.items() if o in body['offer_id']],'has_next':False}
  raise AssertionError(path)

class GroupTests(unittest.TestCase):
 def setup_group(self,tmp,two=False):
  path,_=fixtures.AttributeTests().setup_draft(tmp);data=read(path);data['variant_parameters'].update(name='Synthetic item',quantity='1',stock='5',cost='20',margin='25');data['category'].update(name='Тестовый тип',path='Synthetic / Тестовый тип');data.update(base_article='GROUP',price_cny=None);write(path,data)
  paths=[path]
  if two:
   other=path.parent.parent/'SECOND';shutil.copytree(path.parent,other);p=other/'listing_bundle.json';b=read(p);b.update(sku='SECOND',offer_id='SECOND');write(p,b);paths.append(p)
  api=FakeApi();attributes=AttributeService(tmp,caller=api);pricing=PricingService(tmp,attributes.lock)
  config=pricing_fixtures.PricingTests().configs();config['commissions']['records'][0]['type_ru']='Тестовый тип';config['commissions']['records'].append({'type_ru':'Другой тип','brand':'All','rates':['.2','.2','.2'],'source_row':4})
  for name,value in config.items():write(pricing.root/(name+'.json'),value)
  for p in paths:attributes.refresh(p)
  pricing.calculate_all();group=GroupService(paths,attributes,pricing);publication=PublicationService(tmp,attributes.lock,caller=api,account_getter=lambda:'test-shop')
  for b,p in zip(group.load(),paths):
   b['export_settings']={'vat':'0','currency_code':'CNY','currency_confirmed':True};b['fulfillment']={'warehouse_id':77,'warehouse_name':'Synthetic RFBS','account_id':'test-shop'};write(p,b)
  return group,api,publication
 def test_bulk_cost_updates_all_prices_and_rejects_invalid_batch_atomically(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp,True);before=[b['price_cny'] for b in group.load()]
   group.set_parameters([0,1],'cost',['40','70'],group.token());after=group.load()
   self.assertTrue(float(after[0]['price_cny'])>float(before[0]));self.assertTrue(float(after[1]['price_cny'])>float(after[0]['price_cny']))
   frozen=group.load()
   with self.assertRaises(ValueError):group.set_parameters([0,1],'cost',['100','NaN'],group.token())
   self.assertEqual(group.load(),frozen)
 def test_official_packaging_mm_attribute_reprices_using_cm_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);group.set_attributes([0],'0:600',[[{'value':'300'}]],group.token());b=group.load()[0]
   self.assertEqual(float(b['variant_parameters']['pack_length']),30);self.assertIsNotNone(b['price_cny']);self.assertEqual(float(b['attribute_draft']['values']['0:600'][0]['value']),300)
 def test_category_refresh_preserves_values_revalidates_dictionary_and_restores_archive(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);group.attributes.save_values(group.paths[0],'0:555',[{'value':'Synthetic care'}]);old=group.load()[0];old_id=old['attribute_draft']['values']['0:85'][0]['dictionary_value_id'];old_price=old['price_cny']
   group.change_category([0],{'description_category_id':11,'type_id':30,'name':'Другой тип','path':'Other'},group.token());new=group.load()[0]
   self.assertEqual(new['attribute_draft']['values']['0:9048'],old['attribute_draft']['values']['0:9048']);self.assertNotEqual(new['attribute_draft']['values']['0:85'][0]['dictionary_value_id'],old_id);self.assertTrue(float(new['price_cny'])>float(old_price));self.assertIn('0:777',[field_key(f) for f in new['attribute_draft']['fields']])
   group.change_category([0],{'description_category_id':10,'type_id':20,'name':'Тестовый тип','path':'Back'},group.token());self.assertEqual(group.load()[0]['attribute_draft']['values']['0:555'][0]['value'],'Synthetic care')
 def test_warehouse_list_exposes_all_shop_types_and_statuses(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);self.assertEqual([r['warehouse_id'] for r in pub.warehouses()],[77,88,99])
 def test_repeated_submit_imports_once_sets_selected_warehouse_once_and_checks_live_sale(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp,True);job=pub.begin(group,group.token());again=pub.begin(group,group.token());self.assertEqual(job['id'],again['id'])
   first=pub.step(job['id']);self.assertNotEqual(first['state'],'on_sale');finished=pub.step(job['id']);self.assertEqual(finished['state'],'on_sale')
   self.assertEqual(sum(p=='/v3/product/import' for p,b in api.calls),1);stock_calls=[b for p,b in api.calls if p=='/v2/products/stocks'];self.assertEqual(len(stock_calls),1);self.assertEqual({r['warehouse_id'] for r in stock_calls[0]['stocks']},{77})
   pub.begin(group,group.token());self.assertEqual(sum(p=='/v3/product/import' for p,b in api.calls),1);self.assertEqual(sum(p=='/v2/products/stocks' for p,b in api.calls),1)
 def test_unreturned_warehouse_blocks_import_and_stock(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);original=pub.caller
   pub.caller=lambda path,body:{'warehouses':[],'has_next':False} if path=='/v2/warehouse/list' else original(path,body)
   with self.assertRaises(ValueError):pub.begin(group,group.token())
   self.assertFalse(any(p in ('/v3/product/import','/v2/products/stocks') for p,b in api.calls))
 def test_import_timeout_is_durable_and_never_automatically_reposted(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);api.import_error=ValueError('timeout');job=pub.begin(group,group.token());self.assertEqual(job['state'],'import_uncertain')
   restarted=PublicationService(tmp,group.lock,caller=api,account_getter=lambda:'test-shop');restarted.step(job['id']);restarted.begin(group,group.token())
   self.assertEqual(sum(p=='/v3/product/import' for p,b in api.calls),1);self.assertFalse(any(p=='/v2/products/stocks' for p,b in api.calls))
 def test_unknown_stock_write_is_reconciled_without_duplicate_reset(self):
  for mode in ('before','after'):
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
    group,api,pub=self.setup_group(tmp);api.stock_error=mode;job=pub.begin(group,group.token());pub.step(job['id']);pub.step(job['id'])
    self.assertEqual(sum(p=='/v2/products/stocks' for p,b in api.calls),1)
    current=read(pub.root/(job['id']+'.json'));self.assertEqual(current['items']['ITEM']['stock_state'],'done' if mode=='after' else 'uncertain')
 def test_existing_live_card_cannot_mask_pending_import(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);api.import_pending=True;job=pub.begin(group,group.token());api.stocks[('ITEM',77)]=5;current=pub.step(job['id'])
   self.assertFalse(current['items']['ITEM'].get('on_sale'));self.assertNotEqual(current['state'],'on_sale')
 def test_moderation_pending_is_not_reported_as_on_sale(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);api.moderate='pending';job=pub.begin(group,group.token());pub.step(job['id']);current=pub.step(job['id'])
   self.assertNotEqual(current['state'],'on_sale');self.assertTrue(current['writes_complete']);self.assertIsNone(pub.active(['ITEM']))
 def test_changing_price_does_not_replenish_stock_after_sales(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);job=pub.begin(group,group.token());pub.step(job['id']);pub.step(job['id']);api.stocks[('ITEM',77)]=3
   group.set_parameters([0],'cost',['60'],group.token());new=pub.begin(group,group.token());pub.step(new['id']);pub.step(new['id'])
   self.assertEqual(sum(p=='/v2/products/stocks' for p,b in api.calls),1);self.assertEqual(api.stocks[('ITEM',77)],3)
 def test_account_switch_never_continues_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);job=pub.begin(group,group.token());pub.account_getter=lambda:'different-shop'
   with self.assertRaises(ValueError):pub.step(job['id'])
   self.assertFalse(any(p=='/v2/products/stocks' for p,b in api.calls))
 def test_source_changed_after_import_stops_stock_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=self.setup_group(tmp);job=pub.begin(group,group.token());b=read(group.paths[0]);b['variant_parameters']['stock']='9';write(group.paths[0],b);current=pub.step(job['id'])
   self.assertEqual(current['state'],'local_changed');self.assertFalse(any(p=='/v2/products/stocks' for p,b in api.calls))

if __name__=='__main__':unittest.main()

class AutofillRegressionTests(unittest.TestCase):
 def test_requested_fields_use_variant_sources(self):
  from attribute_service import suggested_value
  b={'sku':'BASE(2)','variant_parameters':{'net_weight':'1100','quantity':'2','color':'浅灰色','name':'收纳篮'},'copy':{'title_ru':'Общий заголовок','tags_ru':['#дом','#хранение']}}
  expected={'Вес товара, г':'1100','Количество в упаковке, шт':'2','Количество товара в единице измерения':'2','Единиц в одном товаре':'2','Название цвета':'светло-серый','Количество заводских упаковок':'1','Название':'Общий заголовок','Код продавца':'BASE(2)','Гарантия':'Без гарантии','#Хештеги':'#дом #хранение','Целевая аудитория':'Для взрослых'}
  for name,value in expected.items():
   with self.subTest(name=name):self.assertEqual(suggested_value({'id':1,'name_ru':name},b),value)
  b['variant_parameters']['name']='儿童书包';self.assertEqual(suggested_value({'id':1,'name_ru':'Целевая аудитория'},b),'Для детей')
 def test_warehouse_string_ids_and_false_pagination(self):
  import threading
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def call(path,body):
    calls.append(body);return {'result':{'warehouses':[{'warehouse_id':'777','name':'Real shape','is_rfbs':True,'status':'created'}],'has_next':'false'}}
   pub=PublicationService(tmp,threading.Lock(),call,lambda:'shop')
   self.assertEqual(pub.warehouses()[0]['warehouse_id'],777);self.assertEqual(len(calls),1)

class CategoryInteractionTests(unittest.TestCase):
 def test_setup_guidance_points_to_confirmation_and_warehouse(self):
  from category_catalog import setup_errors
  errors=setup_errors([{'sku':'A','category':{'confirmed':False},'export_settings':{'vat':'0','currency_code':'CNY','currency_confirmed':True}}],'shop')
  self.assertEqual(len(errors),2);self.assertIn('确认沿用当前类目',errors[0]);self.assertIn('读取店铺全部仓库',errors[1])
 def test_catalog_cache_avoids_repeated_network_fetches(self):
  from category_catalog import load_catalog
  from types import SimpleNamespace
  calls=[]
  def call(endpoint,body):
   calls.append(body);return {'result':[{'description_category_id':10,'category_name':'Parent','children':[{'type_id':20,'type_name':'Child','children':[]}]}]}
  with tempfile.TemporaryDirectory() as tmp:
   service=SimpleNamespace(root=Path(tmp),caller=call)
   self.assertTrue(load_catalog(service,'shop'));self.assertTrue(load_catalog(service,'shop'));self.assertEqual(len(calls),2)
   load_catalog(service,'shop',True);self.assertEqual(len(calls),4)
 def test_warehouse_explicit_string_flags_and_diagnostic(self):
  import threading
  with tempfile.TemporaryDirectory() as tmp:
   def call(path,body):return {'warehouses':[{'warehouse_id':'12','name':'private name','address':'private address','is_rfbs':'true','status':'created','is_karantin':'false'}],'has_next':False}
   pub=PublicationService(tmp,threading.Lock(),call,lambda:'shop');self.assertEqual(pub.warehouses()[0]['warehouse_id'],12)
   text=pub.save_warehouse_diagnostic().read_text();self.assertNotIn('private name',text);self.assertNotIn('private address',text)
 def test_confirm_current_category_does_not_fetch_full_tree(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=GroupTests().setup_group(tmp);b=read(group.paths[0]);b['category']['confirmed']=False;write(group.paths[0],b)
   group.confirm_current_categories([0],group.token());self.assertTrue(group.load()[0]['category']['confirmed']);self.assertFalse(any(p.endswith('/tree') for p,body in api.calls))

class OGLWarehouseTests(unittest.TestCase):
 def test_created_ogl_warehouse_is_eligible_even_when_not_rfbs(self):
  import threading
  with tempfile.TemporaryDirectory() as tmp:
   def call(path,body):return {'warehouses':[{'warehouse_id':77,'name':'Synthetic OGL','warehouse_type':'ogl','is_rfbs':False,'status':'created'},{'warehouse_id':78,'warehouse_type':'ogl','is_rfbs':False,'status':'disabled'}],'has_next':False}
   pub=PublicationService(tmp,threading.Lock(),call,lambda:'shop');self.assertEqual([r['warehouse_id'] for r in pub.warehouses()],[77,78])
 def test_only_warehouse_is_applied_to_whole_group_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=GroupTests().setup_group(tmp,True)
   for path in group.paths:
    b=read(path);b.pop('fulfillment',None);write(path,b)
   rows=[{'warehouse_id':77,'name':'Synthetic OGL'}]
   self.assertTrue(group.use_only_warehouse(rows,'test-shop',group.token()))
   self.assertTrue(all(b['fulfillment']['warehouse_id']==77 for b in group.load()))
   token=group.token();self.assertFalse(group.use_only_warehouse(rows,'test-shop',token));self.assertEqual(group.token(),token)
   self.assertFalse(group.use_only_warehouse(rows+[{'warehouse_id':88,'name':'Second'}],'test-shop',token))
 def test_ogl_submission_rechecks_warehouse_and_sets_stock(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=GroupTests().setup_group(tmp)
   original=pub.caller
   def call(path,body):
    if path=='/v2/warehouse/list':return {'warehouses':[{'warehouse_id':77,'name':'OGL','warehouse_type':'ogl','is_rfbs':False,'status':'created'}],'has_next':False}
    return original(path,body)
   pub.caller=call;job=pub.begin(group,group.token());pub.step(job['id']);pub.step(job['id']);self.assertEqual(api.stocks[(group.load()[0]['sku'],77)],5)
