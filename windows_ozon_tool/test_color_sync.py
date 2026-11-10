import copy,tempfile,unittest
from pathlib import Path
from attribute_service import AttributeService,field_key,AUTOFILL_VERSION
from group_service import GroupService
from pricing_service import read,write
from prefill_rules import color_values
from unittest.mock import Mock
COLOR={'id':100,'name':'颜色','name_ru':'Цвет товара','type':'String','dictionary_id':9,'is_collection':True,'max_value_count':5}
NAME={'id':101,'name':'颜色名称','name_ru':'Название цвета','type':'String'}
class ColorSyncTests(unittest.TestCase):
 def setup(self,tmp):
  def api(path,body):
   if path.endswith('/attribute'):
    fields=copy.deepcopy([COLOR,NAME])
    if body.get('language')=='RU':
     for f in fields:f['name']=f['name_ru']
    return {'result':fields}
   return {'result':[{'id':1,'value':'серый'},{'id':2,'value':'черный'},{'id':3,'value':'белый'}],'has_next':False}
  svc=AttributeService(tmp,caller=api);path=Path(tmp)/'products'/'A'/'listing_bundle.json';path.parent.mkdir(parents=True)
  write(path,{'sku':'A','variant_parameters':{'name':'椅子','color':'灰色；黑色','stock':'1000'},'category':{'description_category_id':10,'type_id':20,'confirmed':True},'images':[]})
  svc.refresh(path);return svc,path
 def test_created_multicolors_fill_all_and_empty_cache_repairs(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,path=self.setup(tmp);b=read(path);self.assertEqual([v['dictionary_value_id'] for v in b['attribute_draft']['values']['0:100']],[1,2])
   b['attribute_draft']['values']['0:100']=[];write(path,b);svc.refresh(path,force=False)
   self.assertEqual([v['dictionary_value_id'] for v in read(path)['attribute_draft']['values']['0:100']],[1,2])
 def test_basic_edit_replaces_all_old_colors_and_official_edit_syncs_back(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,path=self.setup(tmp);group=GroupService([path],svc,Mock())
   group.set_parameters([0],'color',['白色；黑色'])
   b=read(path);self.assertEqual(color_values(b['variant_parameters']['color']),['белый','черный']);self.assertEqual([v['dictionary_value_id'] for v in b['attribute_draft']['values']['0:100']],[3,2])
   group.set_attributes([0],'0:100',[[{'dictionary_value_id':1,'value':'серый'},{'dictionary_value_id':2,'value':'черный'}]])
   b=read(path);self.assertEqual(color_values(b['variant_parameters']['color']),['серый','черный']);self.assertIn('серый',b['attribute_draft']['values']['0:101'][0]['value'])
 def test_single_editor_save_and_clear_sync_basic_color(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,path=self.setup(tmp);svc.save_values(path,'0:100',[{'dictionary_value_id':3,'value':'белый'}]);self.assertEqual(read(path)['variant_parameters']['color'],'белый')
   svc.save_values(path,'0:100',[]);svc.refresh(path,force=False);b=read(path);self.assertEqual(b['variant_parameters']['color'],'');self.assertFalse(b['attribute_draft']['values'].get('0:100'))
if __name__=='__main__':unittest.main()
