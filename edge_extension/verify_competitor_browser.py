"""Actual Chromium public-characteristic fixtures. All network requests intercepted."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await browser.new_page();await page.route('**/*',lambda r:r.fulfill(status=200,content_type='text/html',body='<main></main>'));await page.goto('https://www.ozon.ru/product/synthetic-12345/')
  await page.set_content('<div data-widget="webCharacteristics"><dl><dt>Тип разъема</dt><dd>USB-C</dd></dl><dl><dt>Длина, см</dt><dd>32</dd></dl><dl hidden><dt>Private hidden</dt><dd>ignored</dd></dl></div><dl><dt>Account</dt><dd>ignored</dd></dl>')
  await page.add_script_tag(path=str(ROOT/'competitor_page.js'));result=await page.evaluate('globalThis.__ozonCompetitorRead()');assert result['rows']==[{'name':'Тип разъема','value':'USB-C'},{'name':'Длина, см','value':'32'}],result
  product={'@context':'https://schema.org','@type':'Product','additionalProperty':[{'name':'Цвет','value':'Белый'},{'name':'Длина, см','value':'32','unitText':'см'}]}
  await page.set_content('<script type="application/ld+json">'+json.dumps(product)+'</script>');await page.add_script_tag(path=str(ROOT/'competitor_page.js'));result=await page.evaluate('globalThis.__ozonCompetitorRead()');assert len(result['rows'])==2 and result['rows'][1]['value']=='32 см'
  await page.set_content('<div data-widget="webCharacteristics"><dl><dt>Особенности</dt><dd><a>A</a><a>B</a></dd></dl></div>');await page.add_script_tag(path=str(ROOT/'competitor_page.js'));multi=await page.evaluate('globalThis.__ozonCompetitorRead()');assert multi['rows'][0]['values']==['A','B'],multi
  product['url']='https://www.ozon.ru/product/synthetic-12345/'
  related={'@type':'Product','url':'https://www.ozon.ru/product/unrelated-999/','additionalProperty':[{'name':'Related private mismatch','value':'ignored'}]}
  await page.set_content('<script type="application/ld+json">'+json.dumps({'@graph':[product,related]})+'</script>');await page.add_script_tag(path=str(ROOT/'competitor_page.js'));result=await page.evaluate('globalThis.__ozonCompetitorRead()');assert len(result['rows'])==2 and not any(r['name']=='Related private mismatch' for r in result['rows'])
  await page.goto('https://www.ozon.ru/my/order');await page.add_script_tag(path=str(ROOT/'competitor_page.js'))
  try:await page.evaluate('globalThis.__ozonCompetitorRead()')
  except Exception as e:assert '停止采集' in str(e)
  else:raise AssertionError('non-product page accepted')
  await browser.close();print('PASS: public characteristics/JSON-LD, hidden/account data excluded, non-product page rejected; all traffic mocked')
asyncio.run(main())
