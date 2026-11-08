import copy,tempfile,time,unittest
from pathlib import Path
from attribute_service import AttributeService,field_key,source_fingerprint,review_hash
from listing_preview import attribute_errors,build_item,export_preview
from pricing_service import read,write
import test_hosting as image_fixtures
import test_video_hosting as video_fixtures
from video_hosting import VideoHostingService

FIELDS=[{'id':85,'name':'品牌','name_ru':'Бренд','type':'string','dictionary_id':1,'is_required':True},{'id':9048,'name':'型号','name_ru':'Название модели','type':'string','is_required':True},{'id':4191,'name':'简介','name_ru':'Аннотация','type':'string','is_required':True},{'id':23171,'name':'标签','name_ru':'Хештеги','type':'string','is_collection':True},{'id':12345,'name':'内衬材质','name_ru':'Материал подкладки','type':'string','dictionary_id':2,'is_required':True}]
class AttributeTests(unittest.TestCase):
 def setup_draft(self,tmp):
  source,path,host,video=video_fixtures.VideoTests().setup_media(tmp);VideoHostingService(source).scan_once();data=read(path)
  data.update(category={'description_category_id':10,'type_id':20,'confirmed':True},model='RANDOM-MODEL',brand='Нет бренда',variant_parameters={'cost':'20','material':'金属','accessory_material':'纸板','pack_length':'21.5','pack_width':'12','pack_height':'7','pack_weight':'900'},copy={'title_ru':'Тестовое изделие','description_ru':'Основной материал — металл; вкладыш — картон.','tags_ru':['#корзина'],'missing_facts':[]},pricing_fingerprint='price-inputs',pricing_confirmed_fingerprint='price-inputs',pricing_confirmed_price='123');write(path,data)
  def caller(endpoint,body):
   if endpoint.endswith('/attribute'):return {'result':copy.deepcopy(FIELDS)}
   return {'result':[{'id':100 if body.get('value')=='Нет бренда' else 200,'value':body.get('value','Картон')}],'has_next':False}
  return path,AttributeService(tmp,caller=caller)
 def test_live_schema_auto_fill_keeps_body_and_lining_separate(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);state=service.refresh(path)
   self.assertEqual(state['values']['0:12345'][0]['value'],'Картон');self.assertEqual(state['values']['0:85'][0]['value'],'Нет бренда')
   self.assertEqual(attribute_errors(read(path)),[]);self.assertFalse(state['confirmed'])
 def test_unknown_dictionary_id_and_empty_vat_are_blocked(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path)
   with self.assertRaises(ValueError):service.save_values(path,'0:85',[{'dictionary_value_id':999,'value':'fake'}])
   with self.assertRaises(ValueError):service.confirm(path,'',True)
   with self.assertRaises(ValueError):service.confirm(path,'0',False)
 def test_preview_has_packaging_mm_common_copy_fixed_main_and_video_complex_group(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True)
   item,errors=build_item(path.parent,read(path));self.assertEqual(errors,[]);self.assertEqual(item['depth'],215);self.assertEqual(item['width'],120);self.assertEqual(item['height'],70);self.assertEqual(item['weight'],900)
   self.assertEqual(item['images'][0],read(path)['images'][0]['https_url']);self.assertEqual(len(item['images']),8);self.assertEqual(item['currency_code'],'CNY')
   video=next(g for g in item['complex_attributes'] if g['attributes'][0]['complex_id']==100001);self.assertEqual({a['id'] for a in video['attributes']},{21841,21837})
 def test_changed_category_and_changed_fact_require_review(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True);data=read(path);data['variant_parameters']['accessory_material']='聚丙烯';write(path,data)
   self.assertTrue(attribute_errors(data));state=service.refresh(path);self.assertFalse(state['confirmed']);self.assertEqual(state['values']['0:12345'][0]['value'],'Полипропилен')
   data=read(path);data['category']['type_id']=21;self.assertTrue(attribute_errors(data))
 def test_failed_export_removes_stale_payload_and_never_submits(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True);output=Path(tmp)/'preview'
   report=export_preview([path.parent],output);self.assertTrue(report['ready']);self.assertFalse(report['submitted']);self.assertTrue((output/'ozon_import_preview.json').exists())
   data=read(path);data['images'][0]['https_url']=None;write(path,data);report=export_preview([path.parent],output);self.assertFalse(report['ready']);self.assertFalse((output/'ozon_import_preview.json').exists())
 def test_live_category_change_during_fetch_is_not_committed(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);original=service.caller;changed=[False]
   def caller(endpoint,body):
    if not changed[0]:
     data=read(path);data['category']['type_id']=21;write(path,data);changed[0]=True
    return original(endpoint,body)
   service.caller=caller
   with self.assertRaisesRegex(ValueError,'类目已变化'):service.refresh(path)
   self.assertNotIn('attribute_draft',read(path))
 def test_payload_validation_supports_live_schema_without_obsolete_type_attribute(self):
  from publish import validate
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True);item,errors=build_item(path.parent,read(path));self.assertFalse(errors)
   self.assertEqual(validate({'items':[item]})['type_id'],20)
   second=copy.deepcopy(item);second['offer_id']='OTHER';self.assertEqual(len(validate({'items':[item,second]})),2)
   second['price']='NaN'
   with self.assertRaises(ValueError):validate({'items':[item,second]})
 def test_manual_attribute_change_requires_new_review(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True);data=read(path)
   data['attribute_draft']['values']['0:9048']=[{'value':'CHANGED'}];item,errors=build_item(path.parent,data)
   self.assertIsNone(item);self.assertTrue(any('属性内容' in e for e in errors))
 def test_group_confirmation_is_blocked_when_any_variant_is_incomplete(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);other=Path(tmp)/'products'/'OTHER'/'listing_bundle.json';data=read(path);data['sku']='OTHER';data['attribute_draft']['values'].pop('0:85');write(other,data)
   with self.assertRaises(ValueError):service.confirm_many([path,other],'0',True)
   self.assertFalse(read(path)['attribute_draft']['confirmed'])
 def test_group_confirmation_rejects_changed_review_snapshot(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);expected={str(path):review_hash(read(path)['attribute_draft'])};service.save_values(path,'0:9048',[{'value':'NEW-MODEL'}])
   with self.assertRaisesRegex(ValueError,'预览后属性发生变化'):service.confirm_many([path],'0',True,expected)
 def test_attribute_numeric_types_reject_nan_and_fractional_integer(self):
  from attribute_service import validate_values
  for value in ('NaN','Infinity','1.5'):
   with self.assertRaises(ValueError):validate_values({'type':'Integer'},[{'value':value}])
 def test_saved_preview_detects_draft_or_media_changes_before_submit(self):
  from listing_preview import validate_saved_preview
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True);output=Path(tmp)/'preview';export_preview([path.parent],output);payload_path=output/'ozon_import_preview.json';payload=read(payload_path)
   self.assertTrue(validate_saved_preview(payload_path,payload))
   (path.parent/'video'/'product_8s.mp4').write_bytes(b'changed')
   with self.assertRaises(ValueError):validate_saved_preview(payload_path,payload)
 def test_expired_schema_and_non_generic_brand_block_preview(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);data=read(path);data['attribute_draft']['fetched_at']=0
   self.assertTrue(any('24小时' in e for e in attribute_errors(data)))
   data['attribute_draft']['fetched_at']=time.time();data['attribute_draft']['values']['0:85']=[{'dictionary_value_id':100,'value':'Other brand'}]
   self.assertTrue(any('无品牌' in e for e in attribute_errors(data)))
 def test_cancelled_task_cannot_use_an_old_successful_preview(self):
  from listing_preview import validate_saved_preview
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);service.confirm(path,'0',True);write(Path(tmp)/'tasks.json',[{'sku':'ITEM','state':'saved'}]);output=Path(tmp)/'preview';export_preview([path.parent],output)
   payload_path=output/'ozon_import_preview.json';payload=read(payload_path);write(Path(tmp)/'tasks.json',[])
   with self.assertRaisesRegex(ValueError,'删除或取消'):validate_saved_preview(payload_path,payload)
 def test_required_unmapped_field_stays_missing(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=self.setup_draft(tmp);service.refresh(path);data=read(path);data['attribute_draft']['fields'].append({'id':98765,'name':'承重','is_required':True,'type':'decimal'});write(path,data)
   self.assertTrue(any('承重' in e for e in attribute_errors(data)))

if __name__=='__main__':unittest.main()
