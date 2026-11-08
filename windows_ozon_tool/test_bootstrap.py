import contextlib,io,subprocess,tempfile,unittest
from pathlib import Path
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
   self.assertIn('https://mirrors.aliyun.com/pypi/simple/',args);self.assertEqual(run.call_args.kwargs['timeout'],1800)
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
 def test_failed_mirror_falls_back_without_changing_interpreter(self):
  attempts=[]
  def run(command,**kwargs):
   attempts.append(command)
   if len(attempts)==1:raise subprocess.CalledProcessError(1,command)
  with patch.object(bootstrap,'missing_dependencies',side_effect=[['imageio-ffmpeg'],[]]),patch.object(bootstrap.sys,'prefix','/tool/.venv'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap,'supports_resume',return_value=True),patch.object(bootstrap.subprocess,'run',side_effect=run),contextlib.redirect_stdout(io.StringIO()):
   bootstrap.ensure_dependencies()
  self.assertEqual(len(attempts),2)
  self.assertIn(bootstrap.PACKAGE_SOURCES[0][1],attempts[0]);self.assertIn(bootstrap.PACKAGE_SOURCES[1][1],attempts[1])
  self.assertTrue(all(command[0]==bootstrap.sys.executable and '--resume-retries' in command and '--only-binary=:all:' in command for command in attempts))
 def test_timeout_switches_source_instead_of_aborting_the_whole_install(self):
  with patch.object(bootstrap,'missing_dependencies',side_effect=[['Pillow'],[]]),patch.object(bootstrap.sys,'prefix','/tool/.venv'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap,'supports_resume',return_value=False),patch.object(bootstrap.subprocess,'run',side_effect=[subprocess.TimeoutExpired('pip',1800),None]) as run,contextlib.redirect_stdout(io.StringIO()):
   bootstrap.ensure_dependencies()
   self.assertEqual(run.call_count,2);self.assertNotIn('--resume-retries',run.call_args.args[0])
 def test_old_and_new_pip_help_select_compatible_options(self):
  for help_text,expected in [('Usage: install',False),('Options: --resume-retries <n>',True)]:
   with patch.object(bootstrap.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=help_text)):
    self.assertEqual(bootstrap.supports_resume(),expected)
  self.assertNotIn('--resume-retries',bootstrap.install_command(bootstrap.PACKAGE_SOURCES[0][1],False))
 def test_all_failed_sources_leave_existing_files_intact(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir();saved=root/'data'/'keep.json';saved.write_text('preserved')
   with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'missing_dependencies',return_value=['Pillow']),patch.object(bootstrap.sys,'prefix','/tool/.venv'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap,'supports_resume',return_value=False),patch.object(bootstrap.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'pip')) as run,contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaisesRegex(RuntimeError,'已有素材与任务保留'):bootstrap.ensure_dependencies()
    self.assertEqual(run.call_count,3);self.assertEqual(saved.read_text(),'preserved')
 def test_complete_local_wheels_do_not_contact_a_package_index(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'wheelhouse').mkdir();(root/'wheelhouse'/'fixture.whl').write_bytes(b'fixture')
   with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'missing_dependencies',side_effect=[['Pillow'],[]]),patch.object(bootstrap.sys,'prefix','/tool/.venv'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap,'supports_resume',return_value=False),patch.object(bootstrap.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()):
    bootstrap.ensure_dependencies();self.assertEqual(run.call_count,1)
    command=run.call_args.args[0];self.assertIn('--no-index',command);self.assertNotIn('--index-url',command);self.assertIn(str(root/'wheelhouse'),command)
 def test_incomplete_offline_wheels_fall_back_to_mirror(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'wheelhouse').mkdir();(root/'wheelhouse'/'fixture.whl').write_bytes(b'fixture')
   with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'missing_dependencies',side_effect=[['Pillow'],[]]),patch.object(bootstrap.sys,'prefix','/tool/.venv'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap,'supports_resume',return_value=False),patch.object(bootstrap.subprocess,'run',side_effect=[subprocess.CalledProcessError(1,'pip'),None]) as run,contextlib.redirect_stdout(io.StringIO()):
    bootstrap.ensure_dependencies();self.assertEqual(run.call_count,2);self.assertIn('--index-url',run.call_args.args[0])
 def test_windows_install_and_repair_use_the_same_accelerated_bootstrap(self):
  for name in ('安装.bat','安装Edge版.bat','修复依赖.bat'):
   command=(bootstrap.ROOT/name).read_text(encoding='utf-8')
   self.assertIn('bootstrap.py --check-only',command);self.assertNotIn('-m pip install',command)

if __name__=='__main__':unittest.main()
