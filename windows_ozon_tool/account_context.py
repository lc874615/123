"""Atomic authentication snapshots; never persist API keys in business receipts."""
import os,threading
LOCK=threading.RLock()
def credentials():
 with LOCK:return os.environ.get('OZON_CLIENT_ID',''),os.environ.get('OZON_API_KEY','')
