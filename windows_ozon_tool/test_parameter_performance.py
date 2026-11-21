import threading,unittest
from unittest.mock import Mock,patch
from cell_references import ReferenceBadges
from pricing_service import PricingService

class ParameterPerformanceTests(unittest.TestCase):
 def test_native_reference_markers_add_no_overlay_or_scroll_handlers(self):
  tree=Mock();tree.get_children.side_effect=lambda parent=None:['section'] if parent is None else ['row'];tree.item.return_value=('missing',)
  with patch('tkinter.Label') as label:
   badges=ReferenceBadges(tree,lambda:[('row','v0','value',0)],Mock(),Mock(),native=True);badges.redraw()
  label.assert_not_called();tree.bind.assert_not_called();tree.bbox.assert_not_called()
  tree.item.assert_any_call('row',tags=['missing','reference'])
 def test_image_cache_is_bounded_and_invalidates_replaced_file(self):
  import tempfile
  from pathlib import Path
  from PIL import Image
  from preview_images import PreviewImages
  with tempfile.TemporaryDirectory() as temp:
   loader=PreviewImages(limit=2)
   try:
    path=Path(temp)/'image.png';Image.new('RGB',(100,150),'red').save(path)
    first=loader.load(path,(40,60));self.assertIs(first,loader.load(path,(40,60)))
    Image.new('RGB',(110,150),'blue').save(path)
    second=loader.load(path,(40,60));self.assertIsNot(first,second);self.assertEqual(second.getpixel((0,0)),(0,0,255))
    loader.load(path,(20,30));self.assertEqual(len(loader.cache),2)
   finally:loader.close()
 def test_scroll_redraw_keeps_click_target_and_updates_position(self):
  tree=Mock();tree.winfo_width.return_value=800;tree.bbox.side_effect=lambda iid,col:(0,20,250,30) if col=='#0' else (250,20,240,30)
  cells=[('row','v0','reference',0)];single=Mock();double=Mock()
  with patch('tkinter.Label') as label_type:
   label=label_type.return_value;label.cget.return_value='reference'
   badges=ReferenceBadges(tree,lambda:cells,single,double)
   badges.redraw();badges.redraw()
   label_type.assert_called_once();label.destroy.assert_not_called()
   bindings={args[0]:args[1] for args,kwargs in label.bind.call_args_list}
   bindings['<Double-1>'](Mock());double.assert_called_once_with('row',0)
   cells.clear();badges.redraw();label.destroy.assert_called_once()

 def test_targeted_pricing_does_not_expand_to_all_products(self):
  service=PricingService.__new__(PricingService);service.calculation_lock=threading.Lock();service._calculate_all=Mock()
  paths=['selected/listing_bundle.json'];service.calculate_paths(paths)
  service._calculate_all.assert_called_once_with(paths)

if __name__=='__main__':unittest.main()
