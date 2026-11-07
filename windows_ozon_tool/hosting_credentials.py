"""Windows DPAPI storage. Never fall back to plaintext secrets."""
import ctypes
import os
from ctypes import wintypes

def protect(raw,decrypt=False):
 if os.name!='nt':raise ValueError('仅Windows可加密记住托管密钥；当前环境请使用仅本次运行或环境变量')
 class Blob(ctypes.Structure):
  _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
 buffer=ctypes.create_string_buffer(raw);source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
 crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 method=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
 method.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
 method.restype=wintypes.BOOL;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
 if not method(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):raise ValueError('Windows密钥保护失败；请取消记住密钥后重试')
 try:return ctypes.string_at(target.pbData,target.cbData)
 finally:kernel.LocalFree(ctypes.cast(target.pbData,ctypes.c_void_p))
