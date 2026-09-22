from pathlib import Path
import json,time,hashlib
from playwright.sync_api import sync_playwright
r=Path(__file__).parent
# Adapted from owner's tt-capture/capture_tos_pages.py: same settle/dismiss flow,
# sidebar navigation prevents direct-route initial Page Not Found.
def settle(pg):
 try:pg.wait_for_selector('[data-testid="stStatusWidget"]',state='detached',timeout=45000)
 except Exception:pass
 pg.wait_for_timeout(2500)
with sync_playwright() as p:
 br=p.chromium.launch(headless=True);pg=br.new_page(viewport={'width':1440,'height':3000},device_scale_factor=2)
 errors=[];pg.on('pageerror',lambda e:errors.append(str(e)))
 pg.goto('http://127.0.0.1:8765/?embed=true',wait_until='domcontentloaded');settle(pg)
 print(pg.locator('body').inner_text()[:10000],flush=True)
 for route,key in [('tos-import','a'),('tos-results','b'),('experimental-results','c')]:
  link=pg.locator(f'a[href$="/{route}"],a[href*="/{route}?"]')
  print(route,'links',link.count(),flush=True)
  if link.count():link.first.click()
  else:pg.goto(f'http://127.0.0.1:8765/{route}?embed=true',wait_until='domcontentloaded')
  settle(pg)
  if key=='a':pg.get_by_role('button',name='Inspect Package',exact=True).click();settle(pg)
  pg.screenshot(path=str(r/'shots'/f'{key}_tall.png'))
  text=pg.locator('body').inner_text();(r/'shots'/f'{key}_text.txt').write_text(text)
  print(key,text[:3500],flush=True)
  items=pg.locator('[data-testid="stMainBlockContainer"] > div').evaluate_all('(els)=>els.map(e=>({tag:e.tagName,text:e.innerText.slice(0,100),rect:{x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}}))')
  (r/'shots'/f'{key}_bounds.json').write_text(json.dumps(items,indent=2))
 (r/'browser_errors.json').write_text(json.dumps(errors));br.close()
