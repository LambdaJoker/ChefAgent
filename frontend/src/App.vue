<template>
  <div class="container">
    <header>
      <h1>AI 私厨</h1>
      <p>上传菜品照片，自动识别食材并推荐菜谱。</p>
    </header>

    <section class="upload-panel">
      <input type="file" accept="image/*" @change="handleFileSelect" />
      <input v-model="hint" placeholder="可选：补充食材信息" />
      <button :disabled="isAnalyzing || !selectedFile" @click="handleAnalyzeImage">
        {{ isAnalyzing ? "分析中..." : "上传并识别" }}
      </button>
    </section>

    <section class="result-panel" v-if="recognitionText || ossImageUrl">
      <h2>识别结果</h2>
      <p>{{ recognitionText || "暂未识别" }}</p>
      <p><strong>OSS URL：</strong>{{ ossImageUrl || "暂无" }}</p>
      <p><strong>食材：</strong>{{ ingredientText }}</p>
    </section>

    <section v-if="recipes.length">
      <h2>推荐菜谱</h2>
      <div class="recipe-grid">
        <RecipeCard v-for="recipe in recipes" :key="recipe.name" :recipe="recipe" />
      </div>
    </section>

    <ChatPanel :ingredients="ingredients" />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import ChatPanel from "./components/ChatPanel.vue";
import RecipeCard from "./components/RecipeCard.vue";
import {
  fetchRecipeRecommendations,
  recognizeIngredientsByUrl,
  uploadImageToOss,
} from "./api/client";

const selectedFile = ref(null);
const hint = ref("");
const ingredients = ref([]);
const recognitionText = ref("");
const recipes = ref([]);
const ossImageUrl = ref("");
const isAnalyzing = ref(false);

const ingredientText = computed(() =>
  ingredients.value.length ? ingredients.value.join("、") : "暂无"
);

/**
 * 功能:
 * 处理文件选择事件，记录当前待上传图片。
 * 参数:
 * - event: Event，input change 事件对象。
 * 返回:
 * - void
 * 关键流程:
 * 1) 从 input.files 取首个文件；
 * 2) 写入 selectedFile 状态；
 * 3) 无文件时置空状态。
 * 异常处理:
 * 无显式异常。
 */
function handleFileSelect(event) {
  const fileList = event?.target?.files;
  selectedFile.value = fileList && fileList.length > 0 ? fileList[0] : null;
}

/**
 * 功能:
 * 执行“上传 OSS -> URL 识别 -> 菜谱推荐”的主流程。
 * 参数:
 * 无。
 * 返回:
 * - Promise<void>
 * 关键流程:
 * 1) 上传图片到 OSS 并保存 URL；
 * 2) 使用 URL 调用识别接口获取食材；
 * 3) 使用食材调用推荐接口刷新菜谱列表。
 * 异常处理:
 * 任一步失败时展示错误文案并清理菜谱列表。
 */
async function handleAnalyzeImage() {
  if (!selectedFile.value) return;
  isAnalyzing.value = true;
  try {
    const uploadResult = await uploadImageToOss(selectedFile.value);
    ossImageUrl.value = uploadResult.object_url;

    const recognitionResult = await recognizeIngredientsByUrl(
      uploadResult.object_url,
      hint.value
    );
    ingredients.value = recognitionResult.ingredients || [];
    recognitionText.value = recognitionResult.raw_description || "";

    const recommendResult = await fetchRecipeRecommendations(ingredients.value, 5);
    recipes.value = recommendResult.recipes || [];
  } catch (error) {
    recognitionText.value = "分析失败，请检查后端服务、OSS 配置或网络连接。";
    recipes.value = [];
  } finally {
    isAnalyzing.value = false;
  }
}
</script>
