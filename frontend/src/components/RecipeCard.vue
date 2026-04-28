<template>
  <div class="recipe-card">
    <h3>{{ recipe.name }}</h3>
    <p><strong>推荐分：</strong>{{ formatRecommendationScore(recipe.recommendation_score) }}</p>
    <p><strong>难度：</strong>{{ recipe.difficulty }}</p>
    <p><strong>营养分：</strong>{{ recipe.nutrition_score }}</p>
    <p><strong>食材：</strong>{{ recipe.ingredients.join("、") }}</p>
    <p class="reason">{{ recipe.reason }}</p>
  </div>
</template>

<script setup>
/**
 * 功能:
 * 菜谱卡片展示组件，负责渲染单条推荐菜谱信息。
 * 参数:
 * - recipe: Object，后端返回的菜谱实体。
 * 返回:
 * - Vue 组件渲染结果。
 * 关键流程:
 * 1) 展示基础字段；
 * 2) 统一格式化推荐分；
 * 3) 呈现推荐理由。
 * 异常处理:
 * 无显式异常，依赖上游保证数据结构。
 */
defineProps({
  recipe: {
    type: Object,
    required: true,
  },
});

/**
 * 功能:
 * 将 0~1 范围推荐分格式化为百分制字符串。
 * 参数:
 * - score: number，推荐分。
 * 返回:
 * - string，例如 87.5
 * 关键流程:
 * 1) 乘以 100；
 * 2) 保留 1 位小数；
 * 3) 转为文本返回。
 * 异常处理:
 * 非数值输入时返回 "0.0"。
 */
function formatRecommendationScore(score) {
  if (typeof score !== "number") return "0.0";
  return (score * 100).toFixed(1);
}
</script>
