"""Bounded ISO-BMFF duration checks for the tool's H.264 eight-second MP4."""
import struct

def boxes(raw):
 offset=0
 while offset+8<=len(raw):
  size,kind=struct.unpack_from('>I4s',raw,offset);header=8
  if size==1:
   if offset+16>len(raw):raise ValueError('MP4扩展头不完整')
   size=struct.unpack_from('>Q',raw,offset+8)[0];header=16
  elif size==0:size=len(raw)-offset
  if size<header or offset+size>len(raw):raise ValueError('MP4数据不完整')
  yield kind,raw[offset+header:offset+size];offset+=size
 if offset!=len(raw):raise ValueError('MP4结尾不完整')

def inspect_mp4(raw):
 if not 32<=len(raw)<=100*1024*1024:raise ValueError('视频为空或超过100MB')
 top=dict(boxes(raw))
 if b'ftyp' not in top or b'moov' not in top:raise ValueError('未找到完整MP4头')
 movie=top[b'moov'];header=next((data for kind,data in boxes(movie) if kind==b'mvhd'),None)
 if not header:raise ValueError('MP4缺少时长信息')
 if header[0]==0 and len(header)>=20:scale,duration=struct.unpack_from('>II',header,12)
 elif header[0]==1 and len(header)>=32:scale,duration=struct.unpack_from('>IQ',header,20)
 else:raise ValueError('MP4时长头无效')
 if not scale:raise ValueError('MP4时间单位无效')
 seconds=duration/scale
 if not 8<=seconds<=8.05:raise ValueError('视频时长不是8秒，请重新合成')
 if b'avc1' not in movie and b'avc3' not in movie:raise ValueError('视频未检测到H.264编码，请重新合成')
 return {'duration_seconds':seconds,'codec':'h264','size':len(raw)}
