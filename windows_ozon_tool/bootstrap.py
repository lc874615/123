"""Check Edge dependencies using the same interpreter that runs the tool."""
import importlib
import runpy
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEPENDENCIES=(('PIL','Pillow'),('imageio_ffmpeg','imageio-ffmpeg'),('openpyxl','openpyxl'))
PACKAGE_SOURCES=(
 ('阿里云镜像','https://mirrors.aliyun.com/pypi/simple/'),
 ('清华镜像','https://pypi.tuna.tsinghua.edu.cn/simple/'),
 ('PyPI官方源','https://pypi.org/simple/'),
)
INSTALL_TIMEOUT=1800

def supports_resume():
 """Older pip bundled with Python must not receive an unsupported option."""
 try:
  result=subprocess.run([sys.executable,'-m','pip','install','--help'],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',timeout=15,cwd=ROOT)
  return '--resume-retries' in result.stdout
 except (OSError,subprocess.SubprocessError):return False

def install_command(index=None,resume=False):
 command=[sys.executable,'-m','pip','install','--disable-pip-version-check','--prefer-binary','--only-binary=:all:','--timeout','60','--retries','4']
 if resume:command+=['--resume-retries','5']
 if index:command+=['--index-url',index]
 else:command+=['--no-index']
 wheels=ROOT/'wheelhouse'
 if wheels.is_dir():command+=['--find-links',str(wheels)]
 return command+['-r',str(ROOT/'requirements.txt')]

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
 print('缺少依赖：'+', '.join(missing)+'。仅安装到本工具 .venv。',flush=True)
 print('视频依赖含FFmpeg，约40MB；优先国内镜像，失败自动切换源。已安装的包和pip缓存会复用。',flush=True)
 resume=supports_resume()
 wheels=ROOT/'wheelhouse'
 if wheels.is_dir() and any(wheels.glob('*.whl')):
  print('检测到本地wheelhouse安装包，先尝试离线安装。',flush=True)
  try:
   subprocess.run(install_command(resume=resume),check=True,timeout=INSTALL_TIMEOUT,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   importlib.invalidate_caches()
   if not missing_dependencies():return
  except (OSError,subprocess.SubprocessError):
   print('本地安装包不完整或不适用，继续镜像安装。',flush=True)
 failures=[]
 for label,index in PACKAGE_SOURCES:
  print('正在使用'+label+'安装；单次最长30分钟，Ctrl+C可中止。',flush=True)
  try:
   subprocess.run(install_command(index,resume),check=True,timeout=INSTALL_TIMEOUT,cwd=ROOT)
   importlib.invalidate_caches()
   missing=missing_dependencies()
   if not missing:
    print('依赖安装完成，继续启动。',flush=True);return
   failures.append(label+'：仍缺少 '+', '.join(missing))
  except subprocess.TimeoutExpired:failures.append(label+'：下载过慢/安装超时')
  except subprocess.CalledProcessError as exc:failures.append(label+'：pip退出码 '+str(exc.returncode))
  except OSError as exc:failures.append(label+'：无法运行安装进程（'+type(exc).__name__+'）')
  print(failures[-1]+'；检查下一下载源。',flush=True)
 raise RuntimeError('依赖安装未完成：'+'；'.join(failures)+'。请运行 修复依赖.bat 重试；保持 data 和 .venv，已有素材与任务保留。')

def main():
 try:ensure_dependencies()
 except RuntimeError as exc:
  print(str(exc),file=sys.stderr);return 1
 except KeyboardInterrupt:
  print('\n安装已中止，已有素材、任务及下载缓存保留。下次运行继续检查依赖。',file=sys.stderr);return 130
 if '--check-only' not in sys.argv:
  runpy.run_path(str(ROOT/'local_bridge.py'),run_name='__main__')
 return 0

if __name__=='__main__':sys.exit(main())
