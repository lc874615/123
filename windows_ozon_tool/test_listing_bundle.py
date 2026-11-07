import tempfile,json,hashlib,unittest
from pathlib import Path
from listing_bundle import prepare
class Tests(unittest.TestCase):
 def test_bundle_order_hash_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'images').mkdir();rows=[]
   for i in range(1,9):
    f=p/'images'/f'{i}.png';f.write_bytes(str(i).encode());rows.append({'order':i,'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
   (p/'image_manifest.json').write_text(json.dumps(rows[::-1]));result=prepare(p,{'sku':'TEST','facts':'generic'})
   d=json.loads(result.read_text(encoding='utf-8'));self.assertEqual(d['images'][0]['role'],'primary');self.assertIsNone(d['images'][0]['https_url'])
   with self.assertRaises(ValueError):prepare(p,{'sku':'TEST'})
 def test_missing_manifest(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):prepare(t,{'sku':'TEST'})
if __name__=='__main__':unittest.main()
