# 搜索与标签 Wiki

> 这里是 PotatoGallery 的检索与标签说明。默认搜索覆盖 **标题 / 描述 / 标签**，同时兼容多种写法。以下内容以「推荐用法」为主，后续列出兼容语法与完整示例。

## 快速开始

- 直接输入关键词即可搜索标题、描述、标签。
- 使用 `#标签` 可以强制把关键词当成标签。
- 使用 `-标签` 可以排除某个标签。
- 多个条件使用空格拼接。

## 标签体系

### 注册与别名

- 标签需由管理员注册，并指定唯一的英文 URL 名称（slug，允许小写英文、数字、- 与 _）。
- 别名用于同义与形态统一，例如：`longhair`、`long hair`、`long_hair` 可以映射到同一主标签。
- 别名不会独立计数，统计归并到主标签。

### 父子与多父

- 标签支持多父结构，一个子标签可属于多个父标签。
- 父标签统计与搜索会自动包含子标签作品。
- 例：`fox_ears` 可属于 `animal_ears` 与 `kemonomimi`。

### 发布规则

- **仅在发布作品时需要使用 `#`**；管理编辑无需 `#`。
- 选择子标签后会提示补全父标签，多父会一次提示多个可选项。

## 搜索语法（推荐）

### 组合规则与优先级

- 默认是 **AND（交集）**：写多个条件时必须全部满足。
- 同类条件重复时会叠加更严格的限制（例如多个 `width>=`）。
- 标签会先做别名归一化，再计算父子关系。

### 基础标签

- `#tag`：强制按标签搜索。
- `tag`：自动识别为标签或关键词。
- `-tag`：排除标签。

### 分区 / 方向 / 尺寸

- `collection:portraits`
- `orientation:portrait`（portrait/landscape/square）
- `size:ultra`（ultra/large/medium/compact）

说明：`collection` 需要填写分区 slug（后台管理里维护），`orientation` 与 `size` 只接受上面的枚举。

### 数值范围

- `width>=1920` `height>=1080`
- `bytes>=2000000`

### 时间

- `date>=2024-01-01`
- `date:2024-01-01..2024-12-31`
- `age<=30d`（30 天内，支持 d/w/m）

### 排序

- `sort:new`（最新）
- `sort:old`（最早）
- `sort:bytes`（大文件优先）
- `sort:random`（随机）

### 文本检索

- `text:"soft light"`：精确短语。
- 直接输入词语也会被当作文本匹配。

### 不支持与注意事项

- 当前不支持 `OR`（或）语法，可拆分为多次搜索。
- 日期格式推荐 `YYYY-MM-DD`，范围使用 `..`。
- 数值条件仅接受整数。

## 搜索语法（兼容）

以下写法等价于推荐语法：

- `tag:long_hair`、`tags:long_hair`
- `c=portraits`、`col:portraits`、`album:portraits`
- `ori:vertical`、`o:landscape`
- `q:hd`、`quality:large`
- `w>=1920` `h<=3000` `b>=2000000`
- `after:2024-01-01` `before:2024-12-31`
- `order:old`

## 完整示例集

```
#animal_ears fox_ears
#long_hair -duplicate
collection:portraits size:large
orientation:portrait width>=2000
bytes>=2000000 sort:new
text:"soft light" blue_eyes
age<=30d
```

## 猜你想找（搜索提示）

- 搜索框会提示可能的标签与别名，点击即可补全。
- 发布时若缺少父标签，会提示补全父标签。

## 常见问题

### 为什么有些标签需要管理员注册？

为了保证标签结构稳定、URL 一致并避免重复。

### 为什么发布时必须带 #？

发布表单需要明确区分标签与普通文本，`#` 是最直观且易纠错的方式。

### 为什么搜索时不强制 #？

搜索场景更偏「自然输入」，系统会自动识别标签或文本。
