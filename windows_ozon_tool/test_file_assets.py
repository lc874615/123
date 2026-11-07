import base64,io,unittest,zipfile
from PIL import Image
from file_assets import decode

def image(n):
 b=io.BytesIO();Image.new('RGB',(600,800),(n*20,80,90)).save(b,format='JPEG');return b.getvalue()
def archive(rows):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in rows:z.writestr(name,data)
 return b.getvalue()
class Tests(unittest.TestCase):
 def test_eight_numbered_images_sorted_main_first(self):
  result=decode(archive([(f'images/{i:02d}_role.jpg',image(i)) for i in range(8,0,-1)]),'zip',8,[])
  self.assertEqual([base64.b64decode(x) for x in result],[image(i) for i in range(1,9)])
 def test_archive_path_traversal_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'不安全'):decode(archive([('../01_main.jpg',image(1))]),'zip',1,[])
 def test_missing_or_duplicate_numbers_rejected(self):
  for rows in [[('01_main.jpg',image(1))],[('01_a.jpg',image(1)),('01_b.jpg',image(2))]]:
   with self.assertRaisesRegex(ValueError,'编号或数量'):decode(archive(rows),'zip',8,[])
 def test_html_instead_of_image_rejected(self):
  with self.assertRaises(Exception):decode(b'<html>Login</html>','jpg',1,[])
 def test_duplicate_image_content_rejected(self):
  with self.assertRaisesRegex(ValueError,'重复'):decode(archive([(f'{i:02d}.jpg',image(1)) for i in range(1,9)]),'zip',8,[])
 def test_single_image_file(self):
  self.assertEqual(base64.b64decode(decode(image(2),'jpg',1,[])[0]),image(2))
if __name__=='__main__':unittest.main()
