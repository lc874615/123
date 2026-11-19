import tempfile,unittest
from pathlib import Path
from attribute_service import AttributeService
from color_catalog import load,preload
from color_swatches import swatch
FIELD={'id':100,'name':'颜色','name_ru':'Цвет товара','dictionary_id':9,'is_collection':True,'max_value_count':5,'type':'String'}
def bundle(type_id=20):return {'sku':'A','category':{'description_category_id':10,'type_id':type_id,'confirmed':True}}
class OfficialColorTests(unittest.TestCase):
 def service(self,tmp,broken=False):
  calls=[];names=['черный','белый','бежевый','серый','аквамариновый','лавандовый']
  def api(path,body):
   calls.append((path,dict(body)))
   if path.endswith('/attribute'):return {'result':[{**FIELD,'name':'Цвет товара' if body['language']=='RU' else '颜色'}]}
   if path.endswith('/search'):raise AssertionError('complete verified color cache should avoid search')
   cursor=body.get('last_value_id',0);start=cursor%1000 if cursor else 0;offset=1000 if body['type_id']==30 else 0
   rows=[{'id':offset+i+1,'value':names[i] if body.get('language')=='RU' else '官方颜色'+str(i+1)} for i in range(start,min(start+2,len(names)))]
   return {'result':rows if not broken or cursor==0 else [{'id':1,'value':'repeat'}],'has_next':True if broken else start+2<len(names)}
  return AttributeService(tmp,caller=api),calls
 def test_reads_all_pages_in_both_languages_and_resolves_late_option(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,calls=self.service(tmp);result=load(svc,[bundle()]);self.assertTrue(result['complete']);self.assertEqual(len(result['rows']),6)
   cursors=[body['last_value_id'] for path,body in calls if path.endswith('/values')];self.assertEqual(cursors,[0,2,4,0,2,4])
   values=svc.resolve_suggestion(bundle(),FIELD,['аквамариновый']);self.assertEqual(values,[{'dictionary_value_id':5,'value':'аквамариновый'}])
 def test_preload_uses_confirmed_creation_category_and_populates_cache(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,calls=self.service(tmp);result=preload(svc,{'description_category_id':10,'type_id':20,'name':'测试'})
   self.assertEqual(len(result['rows']),6);self.assertTrue(list(Path(tmp).glob('attributes/*fullcolors*')))
 def test_bulk_categories_keep_common_names_but_resolve_own_verified_ids(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,calls=self.service(tmp);result=load(svc,[bundle(),bundle(30)]);self.assertEqual(result['contexts'],2);self.assertEqual(result['total_read'],12)
   self.assertEqual(svc.resolve_suggestion(bundle(),FIELD,['лавандовый'])[0]['dictionary_value_id'],6)
   self.assertEqual(svc.resolve_suggestion(bundle(30),FIELD,['лавандовый'])[0]['dictionary_value_id'],1006)
 def test_single_value_category_resolves_multicolor_combination_beyond_first_page(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,calls=self.service(tmp);original=svc.caller
   def api(path,body):
    response=original(path,body)
    if path.endswith('/attribute'):
     for field in response['result']:field.update(is_collection=False,max_value_count=1)
    elif path.endswith('/values'):
     for row in response['result']:
      if row['id']==6:row['value']='серый, черный' if body['language']=='RU' else '灰色与黑色'
    return response
   svc.caller=api;load(svc,[bundle()]);values=svc.resolve_suggestion(bundle(),{**FIELD,'is_collection':False,'max_value_count':1},['серый','черный'])
   self.assertEqual(values,[{'dictionary_value_id':6,'value':'серый, черный'}])
 def test_stuck_pagination_never_claims_complete(self):
  with tempfile.TemporaryDirectory() as tmp:
   svc,calls=self.service(tmp,True)
   with self.assertRaisesRegex(ValueError,'分页未前进'):load(svc,[bundle()])
   self.assertFalse(list(Path(tmp).glob('attributes/*fullcolors*')))
 def test_swatch_colors_composites_transparency_and_unknown_are_distinct(self):
  red=swatch('红色');combo=swatch('серый, черный');unknown=swatch('unrecognized actual hue');transparent=swatch('прозрачный')
  self.assertEqual(red.size,(52,28));self.assertNotEqual(combo.getpixel((5,5)),combo.getpixel((45,5)))
  self.assertNotEqual(red.tobytes(),unknown.tobytes());self.assertNotEqual(unknown.tobytes(),transparent.tobytes())
if __name__=='__main__':unittest.main()
