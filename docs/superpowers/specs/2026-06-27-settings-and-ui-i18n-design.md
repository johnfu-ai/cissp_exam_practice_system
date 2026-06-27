# Settings 页面与界面国际化设计 (v1.2)

日期：2026-06-27
状态：Approved
关联 PRD 版本：v1.2（§6.12 FR-SET / FR-I18N）
前置：FR-LANG（v1.1，题目内容双语，已实现并合并 master）

## 1. 目标与范围

新增「设置 / Settings」页面作为个人偏好的唯一入口，并在其中提供新的「界面语言」（UI chrome 国际化）选择；把原侧边栏账户区的题目内容语言 `language_mode` 选择器迁入 Settings。界面语言切换后整个系统的 UI 界面字符串（导航、按钮、页面标题、表单标签、提示、Settings 页本身）即时切换为英文或中文。

### 1.1 范围内

- 新增 `/settings` 页面（App Router `(app)` 分组下）。
- 新增界面语言偏好 `User.interface_language`（`en` | `zh`，默认 `en`），经既有 `GET/PUT /api/users/me/preferences` 读写。
- 前端 UI chrome 国际化（Approach A：客户端 `I18nProvider` + `t()`，cookie 种子避免首屏闪烁）。
- 侧边栏账户区：移除 `language_mode` `<Select>`，新增「Settings」入口。

### 1.2 范围外（明确）

- 不翻译分类数据（domain / 书本 / 章节 / 知识点 / 标签名称）——这些是 taxonomy 数据，保持入库原文。
- 不改动题目内容双语（FR-LANG 已完成）；`language_mode`（en/zh/bilingual）仍是题目内容语言，独立保留。
- 不引入暗色模式、不引入 `[locale]` 路由、不引入 `next-intl` 依赖。
- 解决 PRD §16-#3：UI chrome 国际化此前被推迟，本次纳入范围（仅 chrome；taxonomy 数据有意不译）。

## 2. 数据模型

`User` 新增列：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `interface_language` | `String(5)` | `NOT NULL DEFAULT 'en'` | 界面语言，取值 `en`/`zh` |

Alembic 迁移为纯加列（additive），无需数据回填。`User.language_mode`（既有）保持不变。

迁移必须通过 `tests/test_migrations.py` 的零 autogenerate 漂移检查（新增列被 autogenerate 识别为待添加，无意外差异）。

## 3. API

复用既有偏好接口，不新增端点。

- `GET /api/users/me/preferences` → `{ language_mode, interface_language }`
- `PUT /api/users/me/preferences` → 请求体可选 `language_mode`（既有）与 `interface_language`（新增，`en`/`zh`）。枚举非法值返回 422。
- `UserOut`、`/auth/me`、`/auth/login`、`/auth/register` 响应新增 `interface_language` 字段。

实现位置：`app/api/users.py`（偏好路由）、`app/schemas/*.py`（UserOut / preferences schema）、`app/services/`（偏好更新逻辑）。校验沿用既有 `ValidationError → 422` 约定。

## 4. 前端架构

### 4.1 翻译资源

`frontend/src/locales/{en,zh}.json` —— 按 stable key 组织的字符串字典。key 命名：`nav.dashboard`、`settings.interfaceLanguage`、`common.save` 等。缺失 key 回退到英文（再缺失回退到 key 本身）。

### 4.2 I18nProvider（Approach A）

- 客户端 context：`src/lib/i18n/provider.tsx` 暴露 `useI18n()` → `{ locale, t }`，`t(key)` 查字典。
- 初始 locale 来自 `usePreferences()`（既有 React Query，读 `/api/users/me/preferences` 的 `interface_language`）。
- **首屏正确性**：根布局（server component）读 `ui_lang` cookie → 设 `<html lang>` 并把初始 locale 序列化注入 `I18nProvider`，使其 hydrate 时已在正确语言，**无英文闪烁、无 hydration mismatch**。
- 偏好变更时：(1) `PUT /api/users/me/preferences` `interface_language`；(2) 写 `ui_lang` cookie（`path=/`, `max-age=1y`, `sameSite=lax`），下次 SSR 即正确。
- cookie 读写小工具：`src/lib/i18n/cookie.ts`。

### 4.3 /settings 页面

`src/app/(app)/settings/page.tsx`（薄包装）→ `src/features/settings/settings-page.tsx`。两张卡片：

1. **界面语言 / Interface language**：`<Select>` English / 中文 → 写 `interface_language` + cookie。切换即时生效（context 更新触发整树重渲染 chrome 字符串）。
2. **题目内容语言 / Question content language**：既有 en/zh/bilingual `<Select>`（从侧边栏迁入）→ 写 `language_mode`。

页面本身字符串经 `t()`。

### 4.4 侧边栏

`src/components/app-sidebar.tsx` 账户区：

- 删除 `language_mode` 的 `<Label>` + `<Select>` 整块。
- 在用户信息块与 Log out 之间新增「Settings」链接（`lucide-react` `Settings` 图标，pill 风格，`href="/settings"`）。
- 保留用户名/邮箱展示与 Log out。

### 4.5 chrome 字符串接入

所有手写 UI chrome 字符串经 `t()`：导航标签、按钮文案、`PageHeader`/`Eyebrow` 文案、表单 `<Label>`、toast、空状态、Settings 页。**保持已测契约**：feature-module 测试（`cat-runner.test.tsx`、`editor.test.tsx` 等）断言的可访问名 / 按钮文本若依赖字面英文，改为断言稳定 `data-testid` 或稳定 label，并在计划中记录改动点。

## 5. PRD 改动（v1.2）

- 修订记录新增 v1.2 (2026-06-27) 行。
- §6 新增 §6.12「设置与界面国际化」含 FR-SET-01..03、FR-I18N-01..06。
- §6.11 注明 `language_mode` 选择器从侧边栏迁至 Settings（交叉引用 FR-SET）。
- §8.1 页面清单新增「设置 / Settings」行。
- §9.4 `User` 行补 `interface_language`。
- §9.5 标注 `GET/PUT /api/users/me/preferences` 同时承载 `interface_language`。
- §12.1 MVP 新增「设置页 + UI chrome 国际化（en/zh）」。
- §14 新增验收：Settings 页存在、侧边栏 Settings 入口、界面语言持久化 + 全 chrome 切换、无首屏闪烁。
- §16-#3 标记已决议（2026-06-27, v1.2）：UI chrome 国际化纳入范围；taxonomy 数据有意不译。

## 6. 测试

### 后端

- 偏好接口：`GET` 返回 `interface_language`；`PUT` 设置 `interface_language`；非法枚举 → 422；`/me`、`/login`、`/register` 含 `interface_language`。
- 迁移测试：加列默认 `en`；零 autogenerate 漂移。
- 既有 `language_mode` 测试保持绿。

### 前端

- `I18nProvider`/`t()` 单测：key 命中、缺失 key 回退英文、locale 切换。
- cookie 工具单测：读/写 `ui_lang`。
- Settings 页测试：两张卡片两个选择器；切换分别调用偏好 PUT；界面语言切换写 cookie。
- 侧边栏测试：无 language `<Select>`；存在 Settings 链接。
- 既有 feature-module 测试：迁移到稳定 label/testid 后保持绿。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 首屏英文闪烁 / hydration mismatch | cookie 种子 + server 注入初始 locale |
| 既有测试依赖字面英文文本断言 | 改为稳定 `data-testid` / label，逐个迁移 |
| 字典 key 漏译 | 缺失 key 回退英文 + 英文字典为权威源；lint 可后续加 key 完整性检查 |
| taxonomy 数据未译造成「半中文」观感 | 明确范围外，文档说明；domain 名称等可在后续版本单独处理 |

## 8. 验收

1. 登录后侧边栏账户区有「Settings」入口，无语言下拉。
2. `/settings` 有两张卡片：界面语言（English/中文）、题目内容语言（en/zh/bilingual）。
3. 选「中文」后整个 UI chrome 即时变中文，刷新后仍为中文；选「English」反之。
4. 题目内容语言选择器在 Settings 页工作如旧（影响题目渲染，不影响 chrome）。
5. 后端偏好接口往返 `interface_language` 正确，非法值 422。
6. 全部后端测试、前端测试、lint、build 通过；docker compose 健康检查通过。
