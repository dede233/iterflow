import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
export const router=createRouter({history:createWebHistory(),routes:[
 {path:'/login',component:()=>import('@/views/auth/LoginView.vue')},
 {path:'/',component:AppLayout,children:[
  {path:'',component:()=>import('@/views/dashboard/DashboardView.vue')},
  {path:'feedbacks',component:()=>import('@/views/feedback/FeedbackListView.vue')},{path:'feedbacks/new',component:()=>import('@/views/feedback/FeedbackCreateView.vue')},{path:'feedbacks/:id',component:()=>import('@/views/feedback/FeedbackDetailView.vue')},
  {path:'requirements',component:()=>import('@/views/requirement/RequirementListView.vue')},{path:'requirements/:id',component:()=>import('@/views/requirement/RequirementDetailView.vue')},
  {path:'versions',component:()=>import('@/views/version/VersionListView.vue')},{path:'versions/:id',component:()=>import('@/views/version/VersionDetailView.vue')},
  {path:'releases',component:()=>import('@/views/release/ReleaseListView.vue')},{path:'notifications',component:()=>import('@/views/notification/NotificationCenterView.vue')},
  {path:'system/users',component:()=>import('@/views/system/UserListView.vue')},{path:'system/roles',component:()=>import('@/views/system/RoleListView.vue')}
 ]}
}]})
router.beforeEach((to)=>{if(to.path!='/login'&&!localStorage.getItem('access_token')) return '/login'})
