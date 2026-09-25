<script setup lang="ts">
const steps = ['反馈', '需求', '版本', '发布']
</script>

<template>
  <main class="auth-shell">
    <aside class="auth-story" aria-label="迭程产品介绍">
      <div class="auth-brand"><span class="auth-mark">迭</span><span>迭程 <strong>IterFlow</strong></span></div>
      <div class="auth-copy">
        <span class="auth-kicker">需求与版本协作管理系统</span>
        <h2>让每一次反馈<br>都有清晰的去向。</h2>
        <p>从原始反馈到正式需求，再到版本与发布，团队在同一条协作链路上工作。</p>
        <ol class="auth-flow">
          <li v-for="(step, index) in steps" :key="step"><span>{{ String(index + 1).padStart(2, '0') }}</span>{{ step }}</li>
        </ol>
      </div>
      <div class="auth-foot">ITERFLOW / V1.5</div>
    </aside>
    <div class="auth-form-pane"><div class="auth-form-inner"><slot /></div></div>
  </main>
</template>

<style scoped>
.auth-shell { display: grid; grid-template-columns: minmax(360px, 45%) minmax(0, 1fr); min-height: 100dvh; background: var(--if-bg-page); }
.auth-story { position: relative; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; min-height: 100dvh; padding: clamp(28px, 4vw, 60px); background: radial-gradient(circle at 110% 0%, #334c83 0, transparent 34%), linear-gradient(150deg, #17243d, #0c1527 78%); color: #fff; }
.auth-story::before { position: absolute; width: 460px; height: 460px; right: -240px; bottom: -180px; border: 1px solid rgba(173, 195, 255, .16); border-radius: 50%; box-shadow: 0 0 0 80px rgba(173, 195, 255, .035), 0 0 0 160px rgba(173, 195, 255, .025); content: ''; pointer-events: none; }
.auth-brand { display: flex; align-items: center; gap: 10px; position: relative; z-index: 1; font-size: 17px; font-weight: 700; }
.auth-brand strong { font-weight: 500; }
.auth-mark { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 9px; background: var(--if-brand-500); font-weight: 800; }
.auth-copy { position: relative; z-index: 1; max-width: 470px; }
.auth-kicker { color: #9bb6ef; font-size: 12px; font-weight: 650; letter-spacing: .12em; }
.auth-copy h2 { margin: 16px 0; font-size: clamp(30px, 3vw, 46px); line-height: 1.23; letter-spacing: -.025em; }
.auth-copy p { max-width: 380px; margin: 0; color: #b7c4db; font-size: 14px; line-height: 1.9; }
.auth-flow { display: flex; flex-wrap: wrap; gap: 8px; margin: 36px 0 0; padding: 0; list-style: none; }
.auth-flow li { display: inline-flex; align-items: center; gap: 8px; padding: 8px 11px; border: 1px solid rgba(173, 195, 255, .18); border-radius: 8px; color: #d9e4fa; font-size: 12px; }
.auth-flow li span { color: #7f9bd1; font-family: var(--if-font-mono); font-size: 11px; }
.auth-foot { position: relative; z-index: 1; color: #6f82a4; font-family: var(--if-font-mono); font-size: 11px; letter-spacing: .1em; }
.auth-form-pane { display: grid; place-items: center; min-width: 0; padding: 40px 24px; }
.auth-form-inner { width: min(440px, 100%); }
@media (max-width: 767px) {
  .auth-shell { display: block; }
  .auth-story { min-height: auto; padding: 16px 20px; background: transparent; color: var(--if-text-1); }
  .auth-story::before, .auth-copy, .auth-foot { display: none; }
  .auth-brand { font-size: 15px; }
  .auth-form-pane { min-height: calc(100dvh - 66px); padding: 12px 16px 48px; align-items: center; }
}
</style>
