import contextlib,io,subprocess,unittest
from unittest.mock import patch
import bootstrap

class DependencyTests(unittest.TestCase):
 def test_ready_environment_never_installs(self):
  with patch.object(bootstrap,'missing_dependencies',return_value=[]),patch.object(bootstrap.subprocess,'run') as run:
   bootstrap.ensure_dependencies();run.assert_not_called()
 def test_install_uses_running_venv_python(self):
  with patch.object(bootstrap,'missing_dependencies',side_effect=[['openpyxl'],[]]),patch.object(bootstrap.sys,'prefix','/tool/.venv'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap.sys,'executable','/tool/.venv/python'),patch.object(bootstrap.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()):
   bootstrap.ensure_dependencies()
   args=run.call_args.args[0];self.assertEqual(args[:3],['/tool/.venv/python','-m','pip']);self.assertIn(str(bootstrap.ROOT/'requirements.txt'),args)
 def test_global_python_not_modified(self):
  with patch.object(bootstrap,'missing_dependencies',return_value=['openpyxl']),patch.object(bootstrap.sys,'prefix','/system'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap.subprocess,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'start_edge.bat'):bootstrap.ensure_dependencies()
   run.assert_not_called()
 def test_failed_install_does_not_start_tool(self):
  with patch.object(bootstrap,'ensure_dependencies',side_effect=RuntimeError('repair needed')),patch.object(bootstrap.runpy,'run_path') as launch,contextlib.redirect_stderr(io.StringIO()):
   self.assertEqual(bootstrap.main(),1);launch.assert_not_called()
 def test_missing_excel_has_actionable_message(self):
  from pricing_sources import excel_loader
  with patch.dict('sys.modules',{'openpyxl':None}):
   with self.assertRaisesRegex(ValueError,'修复依赖.bat'):excel_loader()

if __name__=='__main__':unittest.main()
