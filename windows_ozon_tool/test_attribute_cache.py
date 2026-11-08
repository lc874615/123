import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from attribute_service import AttributeService
from pricing_service import read,write
import test_attributes as fixtures

class AttributeCacheTests(unittest.TestCase):
 def test_local_parameter_edit_reuses_actual_schema_after_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,first=fixtures.AttributeTests().setup_draft(tmp);first.refresh(path);original=read(path)['attribute_draft']['fetched_at'];b=read(path);b['variant_parameters']['length']='44';write(path,b);calls=[]
   def call(endpoint,body):calls.append(endpoint);return first.caller(endpoint,body)
   second=AttributeService(first.data,caller=call);state=second.refresh(path,force=False)
   self.assertFalse(any(p.endswith('/attribute') for p in calls));self.assertEqual(state['fetched_at'],original)
 def test_identical_dictionary_query_is_reused_after_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def call(endpoint,body):calls.append(endpoint);return {'result':[{'id':123,'value':'Синий'}]}
   b={'category':{'description_category_id':10,'type_id':20}};f={'id':5}
   one=AttributeService(tmp,caller=call);one.dictionary(b,f,'Синий');two=AttributeService(tmp,caller=call);self.assertEqual(two.dictionary(b,f,'Синий')['result'][0]['id'],123);self.assertEqual(len(calls),1)
   two.dictionary(b,f,'Синий',force=True);self.assertEqual(len(calls),2)
 def test_empty_results_cached_and_pagination_keys_independent(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def call(endpoint,body):calls.append(body);return {'result':[]}
   service=AttributeService(tmp,caller=call);b={'category':{'description_category_id':10,'type_id':20}};f={'id':5}
   service.dictionary(b,f,'unknown');service.dictionary(b,f,'unknown');self.assertEqual(len(calls),1)
   service.dictionary(b,f,'',1);service.dictionary(b,f,'',2);self.assertEqual(len(calls),3)
 def test_expired_schema_is_fetched_and_local_changes_do_not_extend_ttl(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,service=fixtures.AttributeTests().setup_draft(tmp);service.refresh(path);b=read(path);b['attribute_draft']['fetched_at']=time.time()-90000;write(path,b);calls=[];original=service.caller;service.schema_cache={}
   def call(endpoint,body):calls.append(endpoint);return original(endpoint,body)
   service.caller=call;state=service.refresh(path,force=False);self.assertEqual(sum(p.endswith('/attribute') for p in calls),2);self.assertLess(time.time()-state['fetched_at'],10)
