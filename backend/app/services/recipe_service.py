from app.models.schemas import RecipeItem


class RecipeService:
    def __init__(self) -> None:
        self.recipe_pool = [
            {
                "name": "番茄炒蛋",
                "ingredients": ["番茄", "鸡蛋", "葱"],
                "difficulty": "easy",
                "nutrition_score": 8.0,
                "reason": "酸甜开胃，蛋白质和维生素搭配均衡。",
            },
            {
                "name": "蒜蓉西兰花",
                "ingredients": ["西兰花", "大蒜", "盐"],
                "difficulty": "easy",
                "nutrition_score": 9.0,
                "reason": "高纤维、低脂，适合日常健康饮食。",
            },
            {
                "name": "土豆炖牛肉",
                "ingredients": ["土豆", "牛肉", "洋葱"],
                "difficulty": "medium",
                "nutrition_score": 8.5,
                "reason": "能量充足，适合一餐主菜。",
            },
            {
                "name": "香煎三文鱼",
                "ingredients": ["三文鱼", "黑胡椒", "柠檬"],
                "difficulty": "medium",
                "nutrition_score": 9.5,
                "reason": "富含优质脂肪酸，口味清爽。",
            },
            {
                "name": "青椒肉丝",
                "ingredients": ["青椒", "猪里脊", "生抽"],
                "difficulty": "hard",
                "nutrition_score": 7.5,
                "reason": "家常下饭菜，但火候要求较高。",
            },
        ]

    def recommend(self, ingredients: list[str], top_k: int = 5) -> list[RecipeItem]:
        normalized = {item.strip().lower() for item in ingredients if item.strip()}
        ranked: list[RecipeItem] = []

        for recipe in self.recipe_pool:
            recipe_ings = recipe["ingredients"]
            overlap = sum(1 for ing in recipe_ings if ing.lower() in normalized)
            match_ratio = overlap / max(len(recipe_ings), 1)
            difficulty_score = {"easy": 1.0, "medium": 0.7, "hard": 0.4}.get(
                recipe["difficulty"], 0.5
            )
            nutrition_norm = float(recipe["nutrition_score"]) / 10
            recommendation = 0.6 * match_ratio + 0.25 * nutrition_norm + 0.15 * difficulty_score

            if overlap > 0:
                ranked.append(
                    RecipeItem(
                        name=recipe["name"],
                        ingredients=recipe_ings,
                        difficulty=recipe["difficulty"],
                        nutrition_score=recipe["nutrition_score"],
                        recommendation_score=round(recommendation, 3),
                        reason=recipe["reason"],
                    )
                )

        ranked.sort(key=lambda x: x.recommendation_score, reverse=True)

        if not ranked:
            return [
                RecipeItem(
                    name="创意拼盘",
                    ingredients=ingredients or ["任意蔬菜", "任意蛋白质"],
                    difficulty="easy",
                    nutrition_score=7.0,
                    recommendation_score=0.6,
                    reason="未匹配到标准菜谱，建议做清炒或沙拉类自由搭配。",
                )
            ]
        return ranked[:top_k]
