<template>
  <nav class="bottom mobile-only">
    <router-link to="/">首页</router-link><router-link to="/feedbacks">反馈</router-link><router-link to="/requirements">需求</router-link><router-link to="/versions">版本</router-link><router-link to="/notifications">消息</router-link>
  </nav>
</template>
<style scoped>
.bottom {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  height: 62px;
  align-items: center;
  justify-content: space-around;
  background: #fff;
  border-top: 1px solid #e5e7eb;
  font-size: 12px;
  z-index: 20;
}

.router-link-active {
  color: #409eff;
  font-weight: 700;
}

@media (max-width: 767px) {
  .bottom {
    display: flex;
  }
}
</style>
