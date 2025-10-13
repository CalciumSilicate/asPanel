<!-- src/App.vue -->
<template>
  <!-- 全局路由过渡（登录/注册 与 主布局切换时也有过渡） -->
  <router-view v-slot="{ Component, route }">
    <!-- 仅在顶层布局变化时（如 Login <-> MainLayout）执行过渡；
         子视图切换保持侧边栏/头部静止，不参与淡入淡出 -->
    <transition name="page-fade" mode="out-in">
      <component :is="Component" :key="route.matched[0]?.path || route.path" />
    </transition>
  </router-view>
 </template>

<script setup lang="ts">
// 目前不需要逻辑，但 setup 语法是推荐的
</script>

<style>
/* 全局字体与背景已在 styles/theme.css 中统一处理 */
</style>
