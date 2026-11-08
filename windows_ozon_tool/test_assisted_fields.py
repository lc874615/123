import tempfile,unittest,hashlib
from pathlib import Path
from assisted_fields import proposals,create_manual
from cos_host import CosHost,HostingError

def bundle():
 return {'sku':'TEST(1)','copy':{'title_ru':'Корзина для хранения'},'variant_parameters':{'quantity':'2','length':'44','width':'35','height':'25'},'attribute_draft':{'fields':[{'id':1,'name_ru':'Объем главного отделения, л'},{'id':2,'name_ru':'Число секций, шт'},{'id':3,'name_ru':'Нужен код маркировки','is_required':True},{'id':4,'name_ru':'Документ PDF'},{'id':5,'name_ru':'Название файла PDF'}]}}
class AssistedFieldTests(unittest.TestCase):
 def test_external_dimensions_not_used_as_internal_capacity(self):
  rows=proposals(bundle());self.assertEqual(len(rows),4);self.assertEqual(rows[0]['suggested'],'');self.assertIn('38.5',rows[0]['evidence']);self.assertEqual(rows[1]['suggested'],'');self.assertEqual(rows[2]['suggested'],'');self.assertTrue(rows[2]['required'])
 def test_declared_internal_dimensions_and_sections(self):
  b=bundle();b['variant_parameters'].update(inner_length='40',inner_width='30',inner_height='20',extra='隔层数：3');rows=proposals(b);self.assertEqual(float(rows[0]['suggested']),24);self.assertEqual(rows[1]['suggested'],'3')
 def test_manual_is_real_pdf_not_certificate(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=create_manual(bundle(),Path(tmp)/'manual.pdf');self.assertTrue(p.read_bytes().startswith(b'%PDF-'));self.assertTrue(p.stat().st_size>1000)
 def test_pdf_upload_uses_pdf_mime_and_digest(self):
  host=CosHost({'bucket':'test-1234567890','region':'ap-hongkong','prefix':'ozon-images'},{'secret_id':'fake','secret_key':'fake'});calls=[];host._put=lambda *args:calls.append(args) or {'https_url':'https://example.com/test.pdf'}
  raw=b'%PDF-1.4\nsynthetic';digest=hashlib.sha256(raw).hexdigest();host.upload_document(raw,digest);self.assertEqual(calls[0][3],'application/pdf');self.assertIn('/documents/',calls[0][2])
  with self.assertRaises(HostingError):host.upload_document(b'fake',digest)
  with self.assertRaises(HostingError):host.upload_document(raw,'wrong')
