"""Read-only compatibility for collecting previously dispatched image requests."""

def configure(task):
 task.pop('sheet_layout',None)
 task.update(delivery_policy='independent_images',auto_image_retry=False)

def plan(task):
 attempt=(task.get('image_retry_attempts') or [{}])[-1]
 return {'sheet_layout':None,'expected_images':task.get('expected_images',8),'delivery_policy':'independent_images','auto_image_retry':False,'collection_expected':attempt.get('count',task.get('expected_images',8)),'collection_offset':attempt.get('offset',0),'recovery_marker':('【OZON_TASK:'+attempt['request_id']+'】') if attempt.get('request_id') else None}

def reserve(store,identifier,body):
 raise ValueError('自动补图功能已移除；请采集已有图片，或在任务中心手动点击“重启本条队列”重新制作')
