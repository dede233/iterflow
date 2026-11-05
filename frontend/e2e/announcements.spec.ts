import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'
for(const width of [1440,375]) test(`announcement draft preview publish and account read at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:900})
 let item:any=null
 const writes:string[]=[]
 await page.addInitScript(()=>{localStorage.setItem('iterflow.access_token','announcement-local');localStorage.setItem('iterflow.refresh_token','announcement-local')})
 await page.route('**/api/v1/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname,method=route.request().method()
  const reply=(json:unknown,status=200)=>route.fulfill({json,status})
  if(path==='/api/v1/auth/me') return reply({id:1,username:'admin',display_name:'测试管理员',permission_codes:['*'],data_scope:'ALL',must_change_password:false})
  if(path==='/api/v1/notifications/unread-count') return reply({unread_count:0})
  if(path==='/api/v1/announcements/notice')return reply({unread_count:item?.published_at&&!item?.read_at?1:0,latest:item?.published_at&&!item?.read_at?item:null,important:null})
  if(path==='/api/v1/announcements'&&method==='GET')return reply({items:item&&(item.published_at||url.searchParams.get('manage')==='true')?[item]:[],total:item?1:0,page:1,page_size:20,unread_count:0,can_manage:true})
  if(path==='/api/v1/announcements'&&method==='POST'){item={...route.request().postDataJSON(),id:1,revision:1,published_at:null,read_at:null};writes.push('create');return reply(item)}
  if(path==='/api/v1/announcements/1'&&method==='GET')return reply(item)
  if(path==='/api/v1/announcements/1/publish'){expect(route.request().postDataJSON()).toEqual({revision:1});item.published_at='2026-11-05T00:00:00Z';item.revision++;writes.push('publish');return reply(item)}
  if(path==='/api/v1/announcements/1/read'){item.read_at='2026-11-05T00:01:00Z';writes.push('read');return reply(item)}
  if(await mockCollaboration(route))return
  return reply({message:'Unexpected '+method+' '+path},500)
 })
 await page.goto('/#/announcements')
 await page.getByRole('button',{name:'新增公告',exact:true}).click()
 const edit=page.getByRole('dialog',{name:'新增更新公告',exact:true})
 await edit.getByRole('textbox',{name:'公告标题',exact:true}).fill('业务系统绑定更新')
 await edit.getByRole('textbox',{name:'版本标识',exact:true}).fill('2026.11')
 await edit.locator('[contenteditable=true]').fill('新增业务系统选择，历史版本可按提示补齐归属。')
 await edit.getByRole('button',{name:'预览',exact:true}).click()
 const preview=page.getByRole('dialog',{name:'公告预览',exact:true})
 await expect(preview).toContainText('新增业务系统选择')
 expect(writes).toEqual([])
 await preview.getByRole('button',{name:'关闭此对话框',exact:true}).click()
 await edit.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(edit).toBeHidden()
 await expect(page.getByText('草稿 · 仅管理员可见')).toBeVisible()
 expect(writes).toEqual(['create'])
 await page.getByRole('button',{name:'发布公告',exact:true}).click()
 await page.getByRole('button',{name:'确认发布',exact:true}).click()
 await expect(page.getByRole('dialog',{name:'发布更新公告',exact:true})).toBeHidden()
 await expect(page.getByRole('button',{name:'发布公告',exact:true})).toBeHidden()
 await expect.poll(()=>writes).toEqual(['create','publish','read'])
 await expect(page.getByRole('heading',{name:'业务系统绑定更新',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
 await page.screenshot({path:`test-results/announcement-${width}.png`,fullPage:true})
})
