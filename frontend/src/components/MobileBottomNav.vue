<template>
  <nav class="bottom mobile-only">
    <router-link to="/">首页</router-link><router-link to="/feedbacks">反馈</router-link><router-link to="/requirements">需求</router-link><router-link to="/versions">版本</router-link><router-link to="/notifications">消息</router-link>
  </nav>
</template>
<style scoped>.bottom{position:fixed;left:0;right:0;bottom:0;height:62px;background:#fff;border-top:1px solid #e5e7eb;display:flex!important;justify-content:space-around;align-items:center;z-index:20;font-size:12px}.router-link-active{color:#409eff;font-weight:700}</style>
