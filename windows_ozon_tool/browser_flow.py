"""Conservative ChatGPT image task: never auto-resubmit an uncertain send."""
import time
class InterventionRequired(RuntimeError):pass
def send_once(page,content):
 editor=page.locator('#prompt-textarea')
 if not editor.is_visible():raise InterventionRequired('请人工完成登录或验证，再继续。')
 stop=page.get_by_test_id('stop-button')
 if stop.count() and stop.is_visible():raise InterventionRequired('上一任务仍在生成。')
 before=page.locator('[data-message-author-role="assistant"]').count()
 editor.fill(content)
 button=page.get_by_test_id('send-button')
 if not button.count() or not button.is_enabled():raise InterventionRequired('发送按钮不可用；请检查附件上传、额度或验证。')
 button.click(timeout=10000)
 return before

def wait_and_download(page,before,cancel,emit,timeout=600):
 deadline=time.monotonic()+timeout
 emit('已发送，等待新回复的图片下载按钮；不会重复发送。')
 while time.monotonic()<deadline:
  if cancel.is_set():raise InterventionRequired('任务已暂停；已发送的生成仍可能继续，请检查网页。')
  if page.is_closed():raise InterventionRequired('浏览器已关闭。')
  replies=page.locator('[data-message-author-role="assistant"]')
  if replies.count()>before:
   latest=replies.last
   buttons=latest.locator('button[aria-label*="Download"], button[aria-label*="下载"], button[aria-label*="Скачать"], button[data-testid*="download"]')
   for i in range(buttons.count()):
    button=buttons.nth(i)
    if button.is_visible() and button.is_enabled():
     with page.expect_download(timeout=20000) as pending:button.click(timeout=10000)
     return pending.value
  page.wait_for_timeout(1000)
 raise InterventionRequired('等待超时。请在网页检查限额、验证或生成结果；未自动重发。')
