---
name: ip-room-effect
description: 当用户需要生成 IP 主题酒店房间效果图时使用此技能。在不改动房间硬装的前提下，将 IP 物料元素（地毯、挂画、抱枕、床盖、窗帘）叠加到酒店房间原图上，支持多角度一致的效果图生成。
---

# IP 房效果图生成技能

## 概述

此技能用于生成 IP 主题酒店房间效果图。输入酒店房间多角度原图，选择 IP 物料，即可生成带有主题软装的多角度一致效果图。

## 核心能力

- 从数据库查询指定 IP 的可选物料清单
- 调用多模态大模型分析房间结构和物料特征，生成精准的生图提示词
- 通过火山引擎组图模式一次生成多张角度一致的效果图
- 严格保持硬装不变，只叠加软装物料

## 工作流

### 步骤 1：理解需求

用户发起 IP 房效果图请求时，识别：

- **房间原图**：用户上传的多张不同角度的酒店房间原图
- **IP 主题**：要使用的 IP（如 奥特曼、芭比、哆啦A梦 等）
- **房间区域**：目标房间区域（套房客厅、套房卧室、标间卧室、单人间卧室、卫生间）
- **物料类型**：要添加的软装类型（地毯、挂画、抱枕、床盖、窗帘，默认全部）
- **风格偏好**：可选的风格说明（如"温馨亲子风格"）
- 无需检查 `/mnt/user-data` 下的文件夹

### 步骤 2：确认物料

调用后端接口查询指定 IP 和房间区域的可用物料：

```bash
curl "${STOCK_API_BASE_URL}/api/ip-room/materials?ip_name=ultraman&room_region=suite_bedroom"
```

**区域参数说明：**
| 区域值 | 说明 |
|--------|------|
| `suite_living_room` | 套房客厅 —— 沙发、茶几、电视柜、落地窗 |
| `suite_bedroom` | 套房卧室 —— 大床、床头柜、衣柜 |
| `standard_bedroom` | 标间卧室 —— 两张单人床、床头柜 |
| `single_bedroom` | 单人间卧室 —— 单人床、床头柜 |
| `bathroom` | 卫生间 —— 洗手台、马桶、淋浴区、镜子 |

将返回的物料列表（区域、类型、名称、描述）展示给用户确认。用户可以增减物料类型或指定具体物料名称。

### 步骤 3：生成提示词

调用多模态大模型，将房间原图和确认的物料图一同传入，分析房间结构和物料特征后生成生图提示词。

调用 Python 脚本：

```bash
python /mnt/skills/public/ip-room-effect/scripts/generate.py \
  --room-images /path/to/room1.jpg /path/to/room2.jpg /path/to/room3.jpg \
  --ip-name ultraman \
  --room-region suite_bedroom \
  --material-types carpet painting pillow bedspread curtain \
  --style-note "温馨亲子风格" \
  --output-dir /mnt/user-data/outputs/ip-room/ \
  --prompt-only
```

`--prompt-only` 模式下，脚本只完成提示词生成并保存 `prompt.json`，不执行生图。可将提示词展示给用户确认，必要时手动编辑 `prompt.json` 调整。

### 步骤 4：生成效果图

使用确认后的提示词调用火山引擎组图接口生成多角度效果图。

调用 Python 脚本：

```bash
python /mnt/skills/public/ip-room-effect/scripts/generate.py \
  --room-images /path/to/room1.jpg /path/to/room2.jpg /path/to/room3.jpg \
  --ip-name ultraman \
  --room-region suite_bedroom \
  --output-dir /mnt/user-data/outputs/ip-room/ \
  --prompt-file /mnt/user-data/outputs/ip-room/prompt.json
```

当同时传入 `--prompt-file` 和 `--room-images` 时，脚本跳过物料查询和提示词生成，直接使用已有提示词生图。

如果不需要分步确认，也可以去掉 `--prompt-only`，让脚本一步完成全部流程：

```bash
python /mnt/skills/public/ip-room-effect/scripts/generate.py \
  --room-images /path/to/room1.jpg /path/to/room2.jpg /path/to/room3.jpg \
  --ip-name ultraman \
  --room-region suite_bedroom \
  --material-types carpet painting pillow bedspread curtain \
  --output-dir /mnt/user-data/outputs/ip-room/
```

[!NOTE]
不要读取 Python 脚本内容，直接传入参数调用。

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--room-images` | 是 | 房间原图文件路径，多张空格分隔 |
| `--ip-name` | 是 | IP 名称，如 `ultraman`、`barbie` |
| `--room-region` | 是 | 房间区域：`suite_living_room`、`suite_bedroom`、`standard_bedroom`、`single_bedroom`、`bathroom` |
| `--material-types` | 否 | 要添加的物料类型，默认全部 |
| `--style-note` | 否 | 风格说明文字 |
| `--output-dir` | 是 | 效果图输出目录 |
| `--max-images` | 否 | 最多生成图片数，默认 4 |
| `--prompt-only` | 否 | 只生成提示词，不生图 |
| `--prompt-file` | 否 | 使用已有提示词文件 JSON 直接生图 |

## 常见场景

**IP 主题亲子房**：奥特曼、芭比、哆啦A梦等主题，地毯换图案、床盖换主题色、挂画换 IP 形象。
**商务主题房**：特定品牌 IP，抱枕和窗帘配合品牌色系。
**节庆主题房**：节假日限定 IP，地毯和床盖加入节庆元素。

## 输出处理

生成完成后：

- 效果图保存在 `output_dir` 目录下，文件名为 `ip_room_01.jpg`, `ip_room_02.jpg` 等
- 同时保存 `prompt.json` 提示词文件，供后续复用或调整
- 向用户展示生成的效果图并提供简要说明
- 如效果不满意，可修改 `prompt.json` 后使用 `--prompt-file` 重新生图

## 注意事项

- 房间原图应清晰、光线充足，同一房间需提供多张不同角度的照片
- 最多支持 14 张参考图
- 组图模式保证多角度之间物料颜色、图案的一致性
- 生成的图片 URL 有效期为 24 小时，脚本会自动下载到本地保存
- 脚本使用环境变量 `STOCK_API_BASE_URL` 连接后端，默认 `http://localhost:8000`
