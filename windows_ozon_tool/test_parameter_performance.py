import threading,unittest
from unittest.mock import Mock,patch
from cell_references import ReferenceBadges
from pricing_service import PricingService

class ParameterPerformanceTests(unittest.TestCase):
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
