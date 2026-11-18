import tempfile,unittest,copy
from pathlib import Path
from types import SimpleNamespace
from pricing_service import read,write
from category_prefill import declared,typed,schema,key,value_for
from attribute_service import suggested_value,AttributeService
from reference_prefill import build,save,needed

class Tests(unittest.TestCase):
 def field(self,ru='Мощность, Вт',zh='功率，瓦',**kw):return {'id':900001,'name_ru':ru,'name':zh,'type':'integer',**kw}
 def test_declared_cross_category_units(self):
  b={'variant_parameters':{'extra':'功率: 0.06 kW；容量: 2 L；直径: 8 cm；厚度: 3 mm'}}
  self.assertEqual(suggested_value(self.field(),b),'60')
  self.assertEqual(declared(self.field('Объем, мл','容量，毫升'),b),'2000')
  self.assertEqual(declared(self.field('Диаметр, мм','直径，毫米'),b),'80')
  self.assertEqual(declared(self.field('Толщина, см','厚度，厘米',type='decimal'),b),'0.3')
  self.assertEqual(declared(self.field('Объем, мл','容量，毫升',type='string'),b),'2000')
 def test_conflicts_bad_units_and_geometry_estimates_stay_unknown(self):
  f=self.field();self.assertIsNone(declared(f,{'variant_parameters':{'extra':'功率: 60 W；功率: 80 W'}}))
  self.assertIsNone(typed(f,'2 kg'));self.assertIsNone(typed(f,'60-80 W'))
  self.assertIsNone(suggested_value(self.field('Объем, л','容量，升',type='decimal'),{'variant_parameters':{'length':'40','width':'30','height':'20'}}))
 def test_declared_structured_parameter_has_priority(self):
  f=self.field('Ширина, см','商品宽(cm)',type='decimal')
  self.assertEqual(suggested_value(f,{'variant_parameters':{'width':'30','extra':'商品宽: 99 cm'}}),'30')
 def setup(self,tmp):
  folder=Path(tmp);sku='ITEM(1)';ref=folder/'products'/sku/'references'/'original.jpg';ref.parent.mkdir(parents=True);ref.write_bytes(b'original source')
  field=self.field();bundle={'sku':sku,'variant_parameters':{'name':'台灯'},'category':{'description_category_id':10,'type_id':20,'confirmed':True},'attribute_draft':{'fields':[field]}}
  write(ref.parent.parent/'listing_bundle.json',bundle)
  task={'id':'T','sku':sku,'state':'saved','set_mode':True,'copy_leader':sku,'variant_parameters':bundle['variant_parameters'],'main_references':[{'path':str(ref),'mime':'image/jpeg'}]}
  return SimpleNamespace(folder=folder,tasks=[task]),task,field,ref
 def test_schema_image_evidence_is_typed_scoped_and_invalidated(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);build(store,t['sku'])
   payload={'category_attributes':{t['sku']:[{'field_key':key(f),'value':'0.06 kW','source':'reference_image_text','evidence':'Power: 0.06 kW','reference_ids':['R1']}]}}
   self.assertEqual(save(store,t['sku'],payload),1);b=read(ref.parent.parent/'listing_bundle.json');self.assertEqual(suggested_value(f,b),'60')
   ref.write_bytes(b'changed original source');self.assertIsNone(value_for(f,b))
 def test_wrong_sku_field_reference_and_unseen_number_are_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);build(store,t['sku'])
   for change in ({'field_key':'0:999999'},{'reference_ids':['R9']},{'value':'500 W'},{'source':'reference_image'}):
    row={'field_key':key(f),'value':'60 W','source':'reference_image_text','evidence':'Power: 60 W','reference_ids':['R1']};row.update(change)
    self.assertEqual(save(store,t['sku'],{'category_attributes':{t['sku']:[row]}}),0)
 def test_category_change_rejects_old_evidence(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);build(store,t['sku']);path=ref.parent.parent/'listing_bundle.json';b=read(path);b['category']['type_id']=21;write(path,b)
   self.assertEqual(save(store,t['sku'],{'category_attributes':{t['sku']:[{'field_key':key(f),'value':'60 W','source':'reference_image_text','evidence':'60 W','reference_ids':['R1']}]}}),0)
 def test_more_than_eight_variants_are_read_in_batches_without_losing_coverage(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp)
   for n in range(2,11):
    sku=f'ITEM({n})';p=store.folder/'products'/sku/'references'/'source.jpg';p.parent.mkdir(parents=True);p.write_bytes(('original '+str(n)).encode());task=copy.deepcopy(t);task.update(id='T'+str(n),sku=sku,main_references=[{'path':str(p),'mime':'image/jpeg'}]);store.tasks.append(task)
   context,refs=build(store,t['sku']);self.assertEqual(len(context['variants']),8);self.assertTrue(needed(store,t))
   context2,refs2=build(store,t['sku']);self.assertIn('ITEM(10)',context2['variants']);self.assertFalse(needed(store,t))
 def test_schema_arriving_after_initial_copy_triggers_category_read(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);path=ref.parent.parent/'listing_bundle.json';b=read(path);b.pop('attribute_draft');write(path,b);build(store,t['sku']);self.assertFalse(needed(store,t));b['attribute_draft']={'fields':[f]};write(path,b);self.assertTrue(needed(store,t))
 def test_official_dictionary_mapping_and_manual_value_survive_new_prefill(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);f=self.field('Тип разъема','接口类型',type='string',dictionary_id=7)
   path=ref.parent.parent/'listing_bundle.json';b=read(path);b['attribute_draft']={'fields':[f]};write(path,b);build(store,t['sku'])
   save(store,t['sku'],{'category_attributes':{t['sku']:[{'field_key':key(f),'value':'USB-C','source':'reference_image_text','evidence':'Interface: USB-C','reference_ids':['R1']}]}})
   def caller(endpoint,body):
    if endpoint.endswith('/attribute'):return {'result':[{**f,'name':f['name_ru'] if body.get('language')=='RU' else f['name']}]}
    return {'result':[{'id':11,'value':'USB-C'},{'id':12,'value':'USB-A'}],'has_next':False}
   service=AttributeService(tmp,caller=caller);state=service.refresh(path);self.assertEqual(state['values'][key(f)][0]['dictionary_value_id'],11)
   b=read(path);b['attribute_draft']['manual_keys']=[key(f)];b['attribute_draft']['values'][key(f)]=[{'dictionary_value_id':12,'value':'USB-A'}];b['variant_parameters']['extra']='接口类型: USB-C';write(path,b)
   self.assertEqual(service.refresh(path)['values'][key(f)][0]['dictionary_value_id'],12)
 def test_conflicting_observations_do_not_choose_an_arbitrary_value(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);build(store,t['sku'])
   rows=[{'field_key':key(f),'value':v,'source':'reference_image_text','evidence':'Power: 60 W / 80 W','reference_ids':['R1']} for v in ('60 W','80 W')]
   self.assertEqual(save(store,t['sku'],{'category_attributes':{t['sku']:rows}}),0);self.assertIsNone(value_for(f,read(ref.parent.parent/'listing_bundle.json')))
 def test_identical_pictures_in_different_variant_files_do_not_lose_batch_coverage(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp)
   for n in range(2,11):
    sku=f'ITEM({n})';p=store.folder/'products'/sku/'references'/'source.jpg';p.parent.mkdir(parents=True);p.write_bytes(ref.read_bytes());task=copy.deepcopy(t);task.update(id='T'+str(n),sku=sku,main_references=[{'path':str(p),'mime':'image/jpeg'}]);store.tasks.append(task)
   build(store,t['sku']);self.assertTrue(needed(store,t));build(store,t['sku']);self.assertFalse(needed(store,t))
 def test_current_schema_evidence_note_matches_value_instead_of_legacy_default(self):
  with tempfile.TemporaryDirectory() as tmp:
   store,t,f,ref=self.setup(tmp);f=self.field('Макс. нагрузка, кг','最大承重')
   path=ref.parent.parent/'listing_bundle.json';b=read(path);b['variant_parameters']['name']='椅子';b['attribute_draft']={'fields':[f]};write(path,b);build(store,t['sku'])
   save(store,t['sku'],{'category_attributes':{t['sku']:[{'field_key':key(f),'value':'80 kg','source':'reference_image_text','evidence':'Max load: 80 kg','reference_ids':['R1']}]}})
   def caller(endpoint,body):return {'result':[{**f,'name':f['name_ru'] if body.get('language')=='RU' else f['name']}]}
   state=AttributeService(tmp,caller=caller).refresh(path)
   self.assertEqual(state['values'][key(f)][0]['value'],'80');self.assertEqual(state['auto_references'][key(f)]['kind'],'reference_image');self.assertEqual(state['auto_references'][key(f)]['suggested'],'80')
