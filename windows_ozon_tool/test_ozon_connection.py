import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import ozon_connection
class ConnectionTests(unittest.TestCase):
 def test_ozon_api_credentials_persist_only_through_protection(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
   with patch.object(ozon_connection,'protect',return_value=b'ciphertext'):
    ozon_connection.save(tmp,'test-client','test-key',True)
   path=Path(tmp)/'ozon_api.dpapi';self.assertEqual(path.read_bytes(),b'ciphertext')
   os.environ.clear()
   with patch.object(ozon_connection,'protect',return_value=json.dumps({'client_id':'test-client','api_key':'test-key'}).encode()):self.assertTrue(ozon_connection.restore(tmp))
   self.assertEqual(os.environ['OZON_API_KEY'],'test-key')
 def test_protection_failure_never_saves_plaintext_or_changes_connection(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),patch.object(ozon_connection,'protect',side_effect=ValueError('failed')):
   with self.assertRaises(ValueError):ozon_connection.save(tmp,'test-client','test-key',True)
   self.assertFalse((Path(tmp)/'ozon_api.dpapi').exists());self.assertNotIn('OZON_API_KEY',os.environ)
if __name__=='__main__':unittest.main()
