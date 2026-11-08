import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from prefill_rules import value_for,annotation,fixed_settings,basis
from attribute_service import AttributeService
from reference_prefill import build,save,needed
from pricing_service import read,write
class PrefillRulesTests(unittest.TestCase):
 def chair(self):return {'sku':'1688-1(1)','variant_parameters':{'name':'椅子','color':'灰色, 黑色','material':'金属','accessory_material':'绒面','assembly':'拆卸','quantity':'1','length':'40'},'category':{'name':'Стул'}}
 def field(self,name,**kw):return {'id':1,'name_ru':name,**kw}
 def test_chair_defaults_and_explicit_override(self):
  b=self.chair();f=self.field('Макс. нагрузка, кг')
  self.assertEqual(value_for(f,b),'150');self.assertEqual(annotation(f,b)['kind'],'seller_default')
  b['variant_parameters']['extra']='最大承重: 180kg；座高: 45cm'
  self.assertEqual(value_for(f,b),'180');self.assertEqual(value_for(self.field('Высота сиденья, см'),b),'45')
  self.assertIsNone(value_for(self.field('Ширина сиденья, см'),b))
  self.assertEqual(value_for(self.field('Материал наполнителя'),b),'Высокоэластичная пена')
  b['variant_parameters']['name']='篮子';b['category']['name']='Корзина';self.assertIsNone(value_for(self.field('Материал наполнителя'),b))
 def test_facts_and_all_colors(self):
  b=self.chair()
  for name,value in [('Материал корпуса','Металл'),('Материал обивки','Велюр'),('Форма поставки','В разобранном виде'),('Название цвета','серый, черный'),('Глубина, см','40')]:self.assertEqual(value_for(self.field(name),b),value)
  self.assertEqual(value_for(self.field('Цвет товара',dictionary_id=3,is_collection=True),b),['серый','черный'])
  b['variant_parameters']['accessory_material']='纸板';self.assertIsNone(value_for(self.field('Материал обивки'),b))
 def test_dictionary_atomic_multiple_colors(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc=AttributeService(tmp,caller=lambda *a:None);svc.dictionary=lambda *a,**k:{'result':[{'id':10,'value':'серый'},{'id':20,'value':'черный'}]}
   f=self.field('Цвет товара',dictionary_id=3,is_collection=True,type='string')
   self.assertEqual([r['dictionary_value_id'] for r in svc.resolve_suggestion(self.chair(),f,['серый','черный'])],[10,20])
   f['is_collection']=False
   with self.assertRaises(ValueError):svc.resolve_suggestion(self.chair(),f,['серый','черный'])
   svc.dictionary=lambda *a,**k:{'result':[{'id':30,'value':'серый, черный'}]}
   self.assertEqual(svc.resolve_suggestion(self.chair(),f,['серый','черный'])[0]['dictionary_value_id'],30)
 def test_unknown_capacity_and_sections_remain_empty(self):
  from assisted_fields import inline_references
  b={'category':{'name':'Корзина'},'variant_parameters':{'length':'44','width':'35','height':'25','quantity':'2'},'attribute_draft':{'fields':[{'id':1,'name_ru':'Объем главного отделения, л'},{'id':2,'name_ru':'Число секций, шт'}]}}
  rows=inline_references(b);self.assertEqual(rows['0:1']['suggested'],'');self.assertEqual(rows['0:2']['suggested'],'')
 def test_vat_fixed(self):
  b={'export_settings':{'vat':'0.2','currency_code':'CNY'}};self.assertTrue(fixed_settings(b));self.assertEqual(b['export_settings']['vat'],'0');self.assertFalse(fixed_settings(b))
 def test_original_reference_evidence_and_stale_basis(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);sku='1688-1(1)';ref=folder/'products'/sku/'references'/'chair.jpg';ref.parent.mkdir(parents=True);ref.write_bytes(b'fixture')
   task={'sku':sku,'set_mode':True,'state':'saved','variant_parameters':self.chair()['variant_parameters'],'references':[{'path':str(ref),'mime':'image/jpeg'}]};store=SimpleNamespace(folder=folder,tasks=[task])
   self.assertTrue(needed(store,task));context,refs=build(store,sku);self.assertEqual(len(refs),1);self.assertFalse(needed(store,task))
   bundle=self.chair();write(ref.parent.parent/'listing_bundle.json',bundle)
   rows=[{'key':'seat_height','value':'45','source':'reference_image_text','evidence':'座高45cm','reference_ids':['R1']},{'key':'max_load','value':'999','source':'reference_image','evidence':'看起来很结实','reference_ids':['R1']},{'key':'coating','value':'Лак','source':'reference_image_text','evidence':'涂层','reference_ids':[{}]}]
   self.assertEqual(save(store,sku,{'variant_attributes':{sku:rows}}),1)
   b=read(ref.parent.parent/'listing_bundle.json');self.assertEqual(value_for(self.field('Высота сиденья, см'),b),'45');self.assertEqual(value_for(self.field('Макс. нагрузка, кг'),b),'150')
   b['variant_parameters']['height']='80';self.assertIsNone(value_for(self.field('Высота сиденья, см'),b))

class ReferenceBridgeTests(unittest.TestCase):
 def test_existing_common_copy_is_preserved_during_attributes_only_roundtrip(self):
  import json,socket,threading,urllib.request
  from unittest.mock import patch
  from local_bridge import Store,server
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);sku='CHAIR(1)';folder=Path(tmp)/'products'/sku;ref=folder/'references'/'chair.jpg';ref.parent.mkdir(parents=True);ref.write_bytes(b'fixture')
   original={'sku':sku,'title_ru':'Стул','description_ru':'Металлический стул','tags_ru':['#стул'],'missing_facts':[]}
   bundle={'sku':sku,'copy':original,'copy_source':sku,'variant_parameters':{'name':'椅子','color':'灰色, 黑色'}};write(folder/'listing_bundle.json',bundle)
   task={'id':'test-task','sku':sku,'name':'fixture','set_mode':True,'copy_leader':sku,'copy_state':'done','state':'saved','facts':'椅子','references':[{'path':str(ref),'mime':'image/jpeg'}],'variant_parameters':bundle['variant_parameters']};store.tasks=[task]
   with patch.object(store,'sync_shared_copies'):
    self.assertEqual(store.next_copy()['copy_mode'],'attributes')
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   http=server(store,'fixture-token',port);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   def post(route,body):
    req=urllib.request.Request('http://127.0.0.1:'+str(port)+route,json.dumps(body).encode(),headers={'Origin':'chrome-extension://fixture','Authorization':'Bearer fixture-token','Content-Type':'application/json'})
    with urllib.request.urlopen(req) as response:return json.load(response)
   try:
    data=post('/copy-task',{'sku':sku});self.assertEqual(len(data['references']),1);self.assertIn('不改写已有文案',data['prompt']);self.assertEqual(task['copy_state'],'running')
    snapshot=task['attribute_context'].copy();recovery=post('/copy-task',{'sku':sku,'inspect_only':True});self.assertEqual(recovery['references'],[]);self.assertEqual(task['attribute_context'],snapshot)
    with patch.object(store,'sync_shared_copies'),patch('category_match.suggest'):
     post('/copy-result',{'sku':sku,'copy':{'sku':sku,'variant_attributes':{sku:[{'key':'seat_height','value':'45','source':'reference_image_text','evidence':'座高45cm','reference_ids':['R1']}]}}})
    result=read(folder/'listing_bundle.json');self.assertEqual(result['copy'],original);self.assertEqual(result['reference_attributes']['records']['seat_height']['value'],'45');self.assertEqual(task['copy_state'],'done');self.assertFalse(needed(store,task))
   finally:http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main()
