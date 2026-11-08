import copy,json,tempfile,unittest
from pathlib import Path
from attribute_service import AttributeService,suggested_value,source_fingerprint
from rich_content import generate
from listing_preview import attribute_errors
from pricing_service import read,write
import test_attributes as fixtures

def bundle():
 return {'sku':'A(1)','images':[{'order':i,'role':'primary' if i==1 else 'gallery','https_url':f'https://example.com/A/{i:02d}.jpg','sha256':str(i)} for i in range(1,9)]}

class RichContentTests(unittest.TestCase):
 def test_eight_images_main_first_and_variant_specific(self):
  first=bundle();second=copy.deepcopy(first);second['images'][0]['https_url']='https://example.com/B/01.jpg'
  a=json.loads(generate(first));b=json.loads(generate(second));blocks=a['content'][0]['blocks']
  self.assertEqual(a['version'],0.3);self.assertEqual(len(blocks),8)
  self.assertEqual([r['img']['src'] for r in blocks],[r['https_url'] for r in first['images']]);self.assertEqual(blocks[0]['img']['src'],blocks[0]['img']['srcMobile']);self.assertNotEqual(blocks[0],b['content'][0]['blocks'][0]);self.assertEqual(blocks[1:],b['content'][0]['blocks'][1:])
 def test_partial_wrong_order_or_unhosted_images_do_not_generate(self):
  for key,value in [('https_url',''),('https_url','https://example.com/1.webp'),('https_url','https://example.com/1.jpg?token=secret'),('order',8),('role','gallery')]:
   b=bundle();b['images'][0][key]=value;self.assertIsNone(generate(b))
  b=bundle();b['images'].pop();self.assertIsNone(generate(b))
 def test_image_changes_invalidate_attribute_source(self):
  b=bundle();before=source_fingerprint(b);b['images'][0]['https_url']='https://example.com/new.jpg';self.assertNotEqual(source_fingerprint(b),before)
 def test_quantity_and_contents_from_declared_facts(self):
  b={'category':{'name':'Корзина для хранения'},'variant_parameters':{'quantity':'2'}}
  self.assertEqual(suggested_value({'id':1,'name_ru':'Количество товара в единице измерения, шт'},b),'2')
  self.assertEqual(suggested_value({'id':1,'name_ru':'Комплектация'},b),'Корзина для хранения — 2 шт.')
  self.assertIsNone(suggested_value({'id':1,'name_ru':'Объем главного отделения, л'},b))
 def test_refresh_generates_rich_and_replaces_old_variant_links(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=fixtures.AttributeTests().setup_draft(tmp);old=service.caller
   def call(endpoint,body):
    r=old(endpoint,body)
    if endpoint.endswith('/attribute'):r['result'].append({'id':11254,'name':'Rich-контент JSON','type':'string'})
    return r
   service.caller=call;state=service.refresh(path);b=read(path);self.assertEqual(state['values']['0:11254'],[{'value':generate(b)}])
   b['images'][0]['https_url']='https://example.com/replaced.jpg';b['attribute_draft']['manual_keys'].append('0:11254');write(path,b)
   state=service.refresh(path);self.assertIn('replaced.jpg',state['values']['0:11254'][0]['value']);self.assertNotIn('0:11254',state['manual_keys'])
   b=read(path);b['attribute_draft']['values']['0:11254']=[{'value':'{}'}];self.assertTrue(any('富内容' in e for e in attribute_errors(b)))
