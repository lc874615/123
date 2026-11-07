import base64,io,unittest
from PIL import Image
from file_assets import decode,validate_images

def image(n):
 b=io.BytesIO();Image.new('RGB',(600,800),(n*20,80,90)).save(b,format='JPEG');return b.getvalue()
class Tests(unittest.TestCase):
 def test_eight_individual_images(self):
  self.assertEqual([base64.b64decode(x) for x in validate_images([image(i) for i in range(1,9)],8,[])],[image(i) for i in range(1,9)])
 def test_archive_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'不读取压缩包'):decode(b'PK','zip',8,[])
 def test_missing_image_rejected(self):
  with self.assertRaisesRegex(ValueError,'需要8张'):validate_images([image(1)],8,[])
 def test_html_instead_of_image_rejected(self):
  with self.assertRaises(Exception):decode(b'<html>Login</html>','jpg',1,[])
 def test_duplicate_image_content_rejected(self):
  with self.assertRaisesRegex(ValueError,'重复'):validate_images([image(1)]*8,8,[])
 def test_single_image_file(self):
  self.assertEqual(base64.b64decode(decode(image(2),'jpg',1,[])[0]),image(2))
if __name__=='__main__':unittest.main()
