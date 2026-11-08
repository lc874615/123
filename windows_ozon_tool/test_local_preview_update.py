import tempfile,unittest
from unittest.mock import patch
from pricing_service import read,write
import test_group_publication as fixtures

class LocalPreviewUpdateTests(unittest.TestCase):
 def test_updates_entire_group_prices_and_attributes_without_publication(self):
  with tempfile.TemporaryDirectory() as tmp:
   group,api,pub=fixtures.GroupTests().setup_group(tmp,True);before=[b['price_cny'] for b in group.load()]
   for n,path in enumerate(group.paths):
    b=read(path);b['variant_parameters']['cost']=str(50+n*30);write(path,b)
   api.calls.clear()
   with patch.object(pub,'begin',side_effect=AssertionError('local update must not submit')) as submit:
    result=group.refresh_preview();submit.assert_not_called()
   after=group.load();self.assertNotEqual([b['price_cny'] for b in after],before);self.assertTrue(all(b['attribute_draft']['values'] for b in after));self.assertEqual(result,'参数和自动售价已同步');self.assertEqual(pub.jobs(),[])
   forbidden=('/v3/product/import','/v1/product/import/prices','/v2/products/stocks')
   self.assertFalse(any(endpoint in forbidden for endpoint,body in api.calls))
if __name__=='__main__':unittest.main()
