import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ get:vi.fn(),post:vi.fn(),push:vi.fn() }))
vi.mock('@/api/client',()=>({api:mocks}))
const route=reactive({path:'/'})
vi.mock('vue-router',()=>({useRoute:()=>route,useRouter:()=>({push:mocks.push})}))
import AnnouncementNotice from './AnnouncementNotice.vue'
const item={id:8,revision:3,title:'新增系统绑定',version_label:'2026.11',release_date:'2026-11-05',content:'<p>说明文字</p>',published_at:'2026-11-05T00:00:00Z',read_at:null,important:true}
const wrappers:ReturnType<typeof mount>[]=[]
function render(blocked=false){const w=mount(AnnouncementNotice,{props:{blocked},global:{stubs:{'el-dialog':{props:['modelValue'],template:'<section v-if="modelValue" role="dialog"><slot/><slot name="footer"/></section>'},'el-button':{props:['loading','disabled'],template:'<button :disabled="loading || disabled"><slot/></button>'}}}});wrappers.push(w);return w}
beforeEach(()=>{vi.resetAllMocks();setActivePinia(createPinia());route.path='/';useAuthStore().$patch({accessToken:'test',user:{id:1,permission_codes:[]} as any});mocks.get.mockResolvedValue({data:{unread_count:1,latest:item,important:item}})})
afterEach(()=>wrappers.splice(0).forEach(w=>w.unmount()))
it('uses a banner for ordinary updates and avoids mail dialog overlap',async()=>{mocks.get.mockResolvedValueOnce({data:{unread_count:1,latest:item,important:null}});const w=render();await flushPromises();expect(w.text()).toContain('未读更新公告');expect(w.find('[role=dialog]').exists()).toBe(false);await w.setProps({blocked:true});expect(w.text()).toBe('')})
it('marks the exact announcement read then obeys account-wide server state',async()=>{const w=render();await flushPromises();expect(w.find('[role=dialog]').exists()).toBe(true);mocks.post.mockResolvedValue({data:item});mocks.get.mockResolvedValue({data:{unread_count:0,latest:null,important:null}});await w.findAll('button').find(b=>b.text()==='我已知晓')!.trigger('click');await flushPromises();expect(mocks.post).toHaveBeenCalledWith('/announcements/8/read',{revision:3});expect(w.text()).toBe('');const another=render();await flushPromises();expect(another.text()).toBe('')})
it('retains important notice on failed acknowledgement and refreshes on window focus',async()=>{const w=render();await flushPromises();mocks.post.mockRejectedValue(new Error('offline'));await w.findAll('button').find(b=>b.text()==='我已知晓')!.trigger('click');await flushPromises();expect(w.text()).toContain('未能保存');mocks.get.mockResolvedValue({data:{unread_count:0,latest:null,important:null}});window.dispatchEvent(new Event('focus'));await flushPromises();expect(w.text()).toBe('')})
it('ignores late replies from an account after logout',async()=>{let resolve!:(v:any)=>void;mocks.get.mockImplementationOnce(()=>new Promise(r=>resolve=r));const w=render();await flushPromises();useAuthStore().user=null;await flushPromises();resolve({data:{unread_count:1,latest:item,important:item}});await flushPromises();expect(w.text()).toBe('')})
it('opens detail without marking other announcements read',async()=>{const w=render();await flushPromises();await w.findAll('button').find(b=>b.text()==='查看详情')!.trigger('click');expect(mocks.push).toHaveBeenCalledWith('/announcements/8');expect(mocks.post).not.toHaveBeenCalled();route.path='/announcements/8';await flushPromises();expect(w.text()).toBe('')})
