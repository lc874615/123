"""Reuse a live logical window without discarding its unsaved UI state."""
def _windows(parent):
 root=parent._root() if hasattr(parent,'_root') else parent
 windows=getattr(root,'_ozon_windows',None)
 if not isinstance(windows,dict):windows={};root._ozon_windows=windows
 return windows

def lookup(parent,key):
 windows=_windows(parent);window=windows.get(key)
 if window is None:return None
 try:
  alive=window.winfo_exists()
 except Exception:alive=False
 if not alive:windows.pop(key,None);return None
 for action in (window.deiconify,window.lift,window.focus_set):
  try:action()
  except Exception:pass
 return window

def remember(parent,key,window):
 windows=_windows(parent);windows[key]=window
 def remove(event):
  if event.widget is window and windows.get(key) is window:windows.pop(key,None)
 window.bind('<Destroy>',remove,add='+')
 return window
