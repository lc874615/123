import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from window_registry import lookup,remember
class WindowReuseTests(unittest.TestCase):
 def test_repeated_open_returns_live_original_and_retains_draft(self):
  root=SimpleNamespace();window=Mock();window.winfo_exists.return_value=True;window.draft='unsaved';remember(root,('parameter','A','color'),window)
  self.assertIs(lookup(root,('parameter','A','color')),window);self.assertEqual(window.draft,'unsaved');window.deiconify.assert_called_once();window.lift.assert_called_once()
 def test_closed_windows_can_reopen_and_destroying_child_does_not_clear_entry(self):
  root=SimpleNamespace();window=Mock();window.winfo_exists.return_value=True;remember(root,'image',window);callback=window.bind.call_args.args[1];callback(SimpleNamespace(widget=object()));self.assertIs(lookup(root,'image'),window)
  callback(SimpleNamespace(widget=window));self.assertIsNone(lookup(root,'image'));remember(root,'image',window);window.winfo_exists.return_value=False;self.assertIsNone(lookup(root,'image'))
 def test_distinct_targets_are_independent_and_focus_denial_never_duplicates(self):
  root=SimpleNamespace();a=Mock();b=Mock();a.winfo_exists.return_value=b.winfo_exists.return_value=True;remember(root,('edit','A'),a);remember(root,('edit','B'),b);a.focus_set.side_effect=RuntimeError('focus denied')
  self.assertIs(lookup(root,('edit','A')),a);self.assertIs(lookup(root,('edit','B')),b)
 def test_reopening_image_and_group_preview_reuses_window_without_building_widgets(self):
  from unittest.mock import patch
  from pathlib import Path
  import tempfile,threading
  from image_viewer import open_viewer
  from group_editor import open_editor
  with tempfile.TemporaryDirectory() as tmp:
   root=SimpleNamespace();image=Mock();image.winfo_exists.return_value=True
   remember(root,('image_viewer',str(Path(tmp).resolve()),0,'preview'),image)
   with patch('tkinter.Toplevel') as factory:
    self.assertIs(open_viewer(root,tmp,[{'local_file':'main.jpg'}],title='preview'),image);factory.assert_not_called()
   group=Mock();group.winfo_exists.return_value=True;path=Path(tmp)/'listing_bundle.json'
   remember(root,('group_preview',(str(path.resolve()),)),group)
   service=SimpleNamespace(lock=threading.Lock(),business_lock=threading.RLock())
   with patch('tkinter.Toplevel') as factory:
    self.assertIs(open_editor(root,tmp,service,[tmp],pricing=None,store=None,publication=None),group);factory.assert_not_called()
if __name__=='__main__':unittest.main()
