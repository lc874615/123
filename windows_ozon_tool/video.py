"""Eight images, 30 frames each: an exact 240-frame / 8-second H.264 slideshow."""
from pathlib import Path
import subprocess,tempfile
from PIL import Image,ImageOps

def make_video(files,output,ffmpeg=None):
 if len(files)!=8:raise ValueError('需要恰好8张图片')
 if ffmpeg is None:
  import imageio_ffmpeg
  ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as tmp:
  folder=Path(tmp)
  for i,p in enumerate(files):
   with Image.open(p) as im:
    im=ImageOps.exif_transpose(im).convert('RGB');canvas=Image.new('RGB',(1080,1440),'white');fit=ImageOps.contain(im,(1080,1440));canvas.paste(fit,((1080-fit.width)//2,(1440-fit.height)//2));canvas.save(folder/f'{i:02d}.png')
  target=output.with_suffix('.partial.mp4')
  command=[str(ffmpeg),'-y','-framerate','1','-start_number','0','-i',str(folder/'%02d.png'),'-vf','fps=30','-frames:v','240','-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
  subprocess.run(command,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
  target.replace(output)
 return str(output)
