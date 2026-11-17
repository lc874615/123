import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PIL import Image
from variants import VariantGrid,FIELDS
class ReferenceUiTests(unittest.TestCase):
 def test_column_identity_is_used_after_frozen_columns_are_hidden(self):
  grid=VariantGrid.__new__(VariantGrid);grid.tree=Mock();grid.tree.identify_row.return_value='7';grid.tree.identify_column.return_value='#2';grid.tree.column.return_value='color';grid.track(SimpleNamespace(x=10,y=10));self.assertEqual(grid.focus,(7,next(i for i,f in enumerate(FIELDS) if f[0]=='color')))
 def test_replacing_reference_changes_only_target_path_without_overwriting_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/'old.png';b=Path(tmp)/'new.png';Image.new('RGB',(20,30),'red').save(a);Image.new('RGB',(20,30),'blue').save(b);original=a.read_bytes();row={'refs':[str(a),'another.png']};grid=VariantGrid.__new__(VariantGrid);grid.thumbnail=Mock()
   with patch('tkinter.filedialog.askopenfilename',return_value=str(b)):self.assertEqual(grid.replace_reference(row,0),str(b))
   self.assertEqual(row['refs'],[str(b),'another.png']);self.assertEqual(a.read_bytes(),original);grid.thumbnail.assert_called_once_with(row)
 def test_invalid_or_cancelled_replacement_preserves_original_reference(self):
  grid=VariantGrid.__new__(VariantGrid);grid.thumbnail=Mock();row={'refs':['original.png']}
  with patch('tkinter.filedialog.askopenfilename',return_value=''):self.assertIsNone(grid.replace_reference(row))
  with patch('tkinter.filedialog.askopenfilename',return_value='/does-not-exist.png'),patch('tkinter.messagebox.showerror'):self.assertIsNone(grid.replace_reference(row))
  self.assertEqual(row['refs'],['original.png']);grid.thumbnail.assert_not_called()
if __name__=='__main__':unittest.main()
