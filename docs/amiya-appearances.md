# 阿米娅形象切换

桌面端右键阿米娅，选择 **切换形象 → 插画阿米娅**。托盘图标菜单也提供相同选项；选择 **基建小人** 可随时回到原版。首次使用仍显示原形象，后续按角色记住选择。

两种形象共用同一个角色身份、模型设置、语音、热键和对话。切换外观只替换动画，不会重新创建 AI 会话。原有 WebM 素材和动作配置保留。

插画版以用户提供的参考图为基础，有微笑、眨眼、开心、挥手、困倦和惊讶六个表情，配合轻微呼吸、摇摆和互动弹跳。它是二维插画表情动画，不是骨骼模型。

## 素材

- 路径：`characters/amiya/appearances/illustrated/sprites.png`
- 格式：1536 × 1024 RGBA PNG，3 列 × 2 行，单格 512 × 512。
- 顺序：微笑、闭眼、开心、挥手、困倦、惊讶。
- 保留生成的透明通道；渲染时使用预乘透明度插值，避免透明像素中的背景颜色渗入发丝边缘。
- 生成方式：内置 imagegen 工具，参考用户提供的「ChatGPT 图像 2026年11月17日 23_18_24.png」，仅参考人物，不使用图中的 UI。

## 最终生成提示词

```text
Use case: stylized-concept. Asset type: production desktop pet sprite sheet, transparent PNG. Input image is a reference for the CHARACTER ONLY; ignore ALL UI, menus, panels and writing. Create a clean high resolution 3 columns by 2 rows sprite sheet of precisely six full-body illustrations of the SAME seated chibi Amiya seen at the bottom of this reference, delicate polished 2D anime digital line art, not pixel art and not 3D. Brown layered long hair, two long upright rabbit ears with pink interiors, big cyan blue eyes, navy black hooded coat with blue trim and scarf, small dark boots, tiny hands resting on knees, soft pink cheek blush, large head tiny body. Preserve reference character identity and costume. Each of six cells has identical canvas dimensions and character scale, same centered seated body and consistent ground baseline, generous transparent padding including above ear tips. No floor, NO cast shadow, NO UI, no text, no labels, no gridlines, no decorative marks around her, absolutely transparent background. Frame order row-major: (1) neutral warm smile eyes open hands on knees, (2) exact same seated pose with eyes fully closed relaxed for blink, (3) cheerful laughing open mouth closed smiling eyes and rosy cheeks, (4) seated pose with right hand raised waving hello and blue eyes open, (5) seated sleepy pose eyes closed head gently tilted to one side hands on knees, (6) seated delighted surprised face with bright open blue eyes and small rounded mouth hands slightly lifted. Keep every full rabbit ear, all hair, arms and boots inside its own cell, evenly spaced isolated characters. Each pose must be recognizable and very consistent, never add extra limbs. Flat alpha transparency around each separate sprite.
```
