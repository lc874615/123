"""Check Edge dependencies using the same interpreter that runs the tool."""
import importlib
import runpy
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEPENDENCIES=(('PIL','Pillow'),('imageio_ffmpeg','imageio-ffmpeg'),('openpyxl','openpyxl'))

def missing_dependencies():
 missing=[]
 for module,package in DEPENDENCIES:
  try:importlib.import_module(module)
  except ImportError:missing.append(package)
 return missing

def ensure_dependencies():
 missing=missing_dependencies()
 if not missing:return
 if sys.prefix==sys.base_prefix:
  raise RuntimeError('请使用本目录 start_edge.bat 启动，或运行 安装Edge版.bat；未向系统Python安装依赖。')
 print('Missing dependencies: '+', '.join(missing)+'. Installing into the tool virtual environment...',flush=True)
 try:
  subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--prefer-binary','-r',str(ROOT/'requirements.txt')],check=True,timeout=300,cwd=ROOT)
 except (OSError,subprocess.SubprocessError) as exc:
  raise RuntimeError('依赖安装未完成。请检查网络后重新运行 start_edge.bat，或双击 修复依赖.bat；已有素材与任务保留。') from exc
 importlib.invalidate_caches()
 missing=missing_dependencies()
 if missing:raise RuntimeError('当前Python仍缺少 '+', '.join(missing)+'。请运行 修复依赖.bat，并保留窗口中的错误信息。')

def main():
 try:ensure_dependencies()
 except RuntimeError as exc:
  print(str(exc),file=sys.stderr);return 1
 if '--check-only' not in sys.argv:
  runpy.run_path(str(ROOT/'local_bridge.py'),run_name='__main__')
 return 0

if __name__=='__main__':sys.exit(main())
