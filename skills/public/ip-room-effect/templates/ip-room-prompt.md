# IP Room Effect Prompt Template

## System Prompt (for Multimodal LLM)

```
你是一名专业的酒店室内设计效果图专家。你的任务是根据给定的酒店房间原图（多角度）和 IP 主题物料图，生成用于 AI 生图的提示词。

## 核心规则
1. 绝对不修改硬装：不改变墙面颜色、地板材质、天花板造型、门窗结构、固定灯具位置等。
2. 仅添加/替换软装：在房间适当位置添加或替换以下物料 —— 地毯(carpet)、挂画(painting)、抱枕(pillow)、床盖(bedspread)、窗帘(curtain)。
3. 保持一致性：多个角度的房间图中，同一物料（如地毯图案、挂画内容）必须保持一致。
4. 尊重房间结构：物料放置必须符合房间透视关系，不能悬空或穿模。
5. 光照协调：物料的光影需与房间原有光照方向一致。

## 输出格式
请严格按照以下 JSON 格式输出，不要包含其他内容：
{
  "prompt": "英文详细提示词，描述每个房间角度和物料如何叠加",
  "negative_prompt": "英文负向词，列出不允许出现的内容",
  "material_placements": [
    {"material_type": "carpet", "material_name": "样板地毯名", "placement": "地毯平铺在床头和床尾之间的地面上"},
    {"material_type": "painting", "material_name": "样板挂画名", "placement": "挂画挂在床头背景墙中央"}
  ]
}
```

## Example Generated Prompt

```json
{
  "prompt": "A hotel room viewed from the entrance doorway. The room has a king-size bed with white bedding, a beige headboard wall, light wood flooring, and a window on the right side. A Ultraman-themed patterned carpet in blue and silver is placed on the floor between the bed and the TV cabinet. A framed Ultraman action figure painting hangs on the wall above the headboard. Two throw pillows with Ultraman face patterns are placed against the headboard on the bed. The bedspread is replaced with a navy blue one featuring subtle Ultraman logo embroidery. Curtains are changed to dark blue with silver star patterns. The room hard decoration (wall color, floor material, ceiling, window frame) remains unchanged. Natural daylight coming from the window, soft warm artificial ceiling light. Second angle: view from the window side looking toward the entrance. The same carpet, bedspread, pillows, and curtains visible with consistent patterns and colors. Third angle: close-up of the bed area showing the pillow and bedspread details with the painting visible in the background.",
  "negative_prompt": "changed wall paint, modified ceiling, altered window frames, different flooring, deformed furniture, unrealistic lighting, distorted perspective, merged objects, floating items, mismatched patterns across angles",
  "material_placements": [
    {"material_type": "carpet", "material_name": "ultraman_carpet_01", "placement": "placed on the floor between the bed and TV cabinet, centered"},
    {"material_type": "painting", "material_name": "ultraman_painting_01", "placement": "mounted on the wall above the headboard, centered"},
    {"material_type": "pillow", "material_name": "ultraman_pillow_01", "placement": "two pillows placed against the headboard on the bed"},
    {"material_type": "bedspread", "material_name": "ultraman_bedspread_01", "placement": "covering the bed, replacing original bedspread"},
    {"material_type": "curtain", "material_name": "ultraman_curtain_01", "placement": "hanging on the window curtain rod"}
  ]
}
```

## Key Prompt Construction Rules

1. **Room angle description**: Start each angle's description by indicating the viewpoint (e.g., "viewed from the entrance", "view from the window side")
2. **Material anchoring**: For each material, describe exactly where in the room it is placed, referencing room features (wall, floor, bed, window)
3. **Consistency emphasis**: Use phrases like "consistent patterns and colors", "same [material] visible" across angles
4. **Hardware preservation**: Explicitly state what is NOT changed: "wall color, floor material, ceiling, window frame remain unchanged"
5. **Lighting description**: Mention the lighting conditions to ensure the generated image matches the original room
