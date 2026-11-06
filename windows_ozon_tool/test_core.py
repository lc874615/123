import unittest
from publish import validate
from app import accept_image,slug,prompt
class Tests(unittest.TestCase):
 def test_no_html_as_image(self):self.assertFalse(accept_image(b'<html>'+b'a'*20000,''))
 def test_image_header(self):self.assertTrue(accept_image(b'\x89PNG\r\n\x1a\n'+b'a'*20000,''))
 def test_local_images_rejected(self):
  x={'items':[{'offer_id':'x','name':'x','description_category_id':1,'type_id':1,'price':'1','currency_code':'CNY','attributes':[{'id':85},{'id':8229},{'id':9048}],'weight':1,'height':1,'width':1,'depth':1,'images':['C:/a.png']*8}]}
  with self.assertRaises(ValueError):validate(x)
 def test_no_path_escape(self):self.assertNotIn('/',slug('../../bad'))
 def test_prompt_avoids_packaging_confusion(self):self.assertIn('包装尺寸必须区分',prompt('事实','主图'))
if __name__=='__main__':unittest.main()
