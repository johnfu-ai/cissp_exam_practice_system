# CISSP考试练习系统 PRD

版本：1.2
日期：2026-06-27
状态：Draft
技术方向：前端 Next.js，后端 FastAPI
目标文件：`docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`

> 修订记录
> - v1.2 (2026-06-27)：新增「设置页」与「界面国际化」需求（FR-SET-01..03、FR-I18N-01..06，见 §6.12）。新增 `User.interface_language`（§9.4）；偏好接口 `/api/users/me/preferences` 同时承载 `interface_language`（§9.5）；§8.1 页面清单新增设置页；§12.1 MVP 与 §14 验收标准补充；解决原开放问题 §16-#3（UI chrome 国际化纳入范围，仅界面字符串，taxonomy 数据有意不译）。原侧边栏题目内容语言选择器迁入设置页（FR-SET-02）。
> - v1.1 (2026-06-26)：新增题目语言选择与中英文双语展示需求（FR-LANG-01..10），覆盖数据模型（§9.4）、API（§9.5）、导入模板与校验（§10）、MVP 范围（§12）与验收标准（§14）；解决原开放问题 §16-#3（题目内容双语）与 §16-#9（双语存储模型）。ETL 管道代码沿用并适配新模型，§6.3/§9.6/§10.3/§10.4 描述不变。
> - v1.0 (2026-06-21)：初版。

## 1. 产品概述

### 1.1 产品愿景

建设一个专业、可扩展、可量化的 CISSP 备考练习系统，帮助考生把题库导入、分范围练习、答案详解、错题复盘、学习分析和模拟 Computerized Adaptive Testing (CAT) 考试整合到一个连续学习闭环中。

系统既要适合个人考生自学，也要为培训讲师、内容编辑和机构管理员预留能力。产品不提供或复制官方考试真题；题库内容由用户、管理员或机构在合法授权范围内导入、维护和使用。

### 1.2 核心价值

- 比通用刷题工具更懂 CISSP：内置 8 个 domain、考试版本、权重、书本章节和知识点映射。
- 比简单题库更可复盘：每道题支持详细解析、错误选项解释、个人笔记、收藏和错题状态。
- 比普通模拟考更贴近真实体验：支持 3 小时、100-150 题、前进式答题、动态选题的 CAT 模拟。
- 比个人 Excel 题库更可持续：支持导入校验、去重、版本、审核、权限和长期学习分析。

### 1.3 产品边界

- 本系统是学习与练习平台，不是 ISC2 官方考试平台。
- 模拟 CAT 算法用于学习评估，不代表 ISC2 官方评分算法。
- 系统不得暗示拥有 ISC2 官方背书，除非未来获得明确授权。
- 题库内容必须记录来源、授权状态和导入批次，降低版权与合规风险。

## 2. 官方考试基线

截至 2026-06-21，应以 ISC2 当前公开页面为基线。CISSP 考试使用 Computerized Adaptive Testing (CAT)，考试时间为 3 小时，题量为 100-150 题，通过分数为 700/1000。当前 CISSP Exam Outline 生效日期为 2024-04-15。

| Domain | 名称 | 权重 |
|---|---|---:|
| 1 | Security and Risk Management | 16% |
| 2 | Asset Security | 10% |
| 3 | Security Architecture and Engineering | 13% |
| 4 | Communication and Network Security | 13% |
| 5 | Identity and Access Management (IAM) | 13% |
| 6 | Security Assessment and Testing | 12% |
| 7 | Security Operations | 13% |
| 8 | Software Development Security | 10% |

系统必须把考试配置设计为可维护数据，而不是硬编码。管理员应能维护考试版本、domain 权重、题量范围、考试时长、题型、语言和生效日期。

参考来源：

- ISC2 CISSP Exam Outline: https://www.isc2.org/certifications/cissp/cissp-certification-exam-outline
- ISC2 CAT format update: https://www.isc2.org/Insights/2025/05/computerized-adaptive-testing-examination-format-updates
- ISC2 Before Your Exam: https://www.isc2.org/exams/before-your-exam

## 3. 产品目标与成功指标

### 3.1 产品目标

1. 支持用户快速导入、校验、清洗、标注和维护 CISSP 练习题。
2. 支持按书本、章节、domain、知识点、难度、错题、收藏和掌握程度进行专项练习。
3. 提供结构化答案详解，帮助用户理解正确答案、错误选项和背后的考点。
4. 提供固定模拟考试和 CAT 模拟考试，帮助用户训练考试节奏和知识覆盖。
5. 提供可行动的学习分析，定位薄弱 domain、薄弱知识点和复习优先级。
6. 支持后续扩展为多用户、多机构、多题库、多语言和商业化订阅系统。

### 3.2 成功指标

| 指标 | 目标 |
|---|---:|
| 新用户完成首次导入或首次练习比例 | >= 70% |
| 用户首次练习完成率 | >= 80% |
| 周活跃练习用户占比 | >= 45% |
| 用户查看解析比例 | >= 75% |
| 导入任务成功率 | >= 90% |
| 固定模拟考试完成率 | >= 60% |
| CAT 模拟考试完成率 | >= 50% |
| 用户能识别至少 2 个薄弱 domain 的比例 | >= 80% |
| 练习提交接口错误率 | < 0.5% |

### 3.3 优先级定义

| 优先级 | 含义 |
|---|---|
| P0 | MVP 必须具备，没有该能力核心流程无法成立 |
| P1 | 核心体验增强，建议在正式发布前完成 |
| P2 | 高级能力或商业化增强，可在后续版本实现 |

## 4. 用户角色

| 角色 | 描述 | 核心需求 |
|---|---|---|
| 个人考生 | 自学备考 CISSP 的用户 | 导入题库、刷题、错题复盘、模拟考试、掌握度分析 |
| 培训讲师 | 给学员授课或辅导的专家 | 管理题库、布置练习、查看学员薄弱项 |
| 内容编辑 | 负责题目整理和质量控制 | 导入、标注、去重、审核、版本管理 |
| 机构管理员 | 培训机构或企业管理员 | 管理用户、班级、题库权限、报表和审计 |
| 系统管理员 | 平台运维与权限管理人员 | 配置系统、管理租户、审计日志、备份恢复 |

## 5. 核心用户旅程

### 5.1 首次导入并开始练习

1. 用户注册并登录。
2. 用户下载导入模板或上传已有 CSV/XLSX/JSON 文件。
3. 系统识别字段，提示用户完成字段映射。
4. 系统校验题干、选项、答案、解析、domain、书本和章节。
5. 用户查看导入预览和错误报告。
6. 用户确认导入，题目进入草稿或已发布状态。
7. 用户选择书本、章节、domain 和题量，开始练习。
8. 用户提交答案后查看解析、收藏题目或添加笔记。

### 5.2 错题复盘

1. 用户进入错题本。
2. 用户筛选最近 14 天答错、答错 2 次以上或标记为需复习的题。
3. 系统按知识点和 domain 聚合错题。
4. 用户重新练习错题，并查看历史答题记录和个人笔记。
5. 用户将题目标记为已掌握或继续复习。

### 5.3 CAT 模拟考试

1. 用户选择 CAT 模拟考试。
2. 系统展示规则：3 小时、100-150 题、提交后不能回退、不能跳题。
3. 用户开始考试，系统从中等难度题目开始。
4. 系统根据用户答题表现、domain 覆盖和题目难度动态选择下一题。
5. 达到结束条件后，系统自动结束或用户完成最大题量。
6. 用户查看考试报告：结果评估、domain 表现、能力趋势、耗时分析和复习建议。

### 5.4 讲师或机构使用

1. 管理员创建班级或学习组。
2. 内容编辑导入并审核题库。
3. 讲师按章节或 domain 布置练习。
4. 学员完成练习或模拟考试。
5. 讲师查看班级整体薄弱点和个人学习报告。

## 6. 功能需求

### 6.1 用户与权限

| ID | 需求 | 优先级 |
|---|---|---|
| FR-USER-01 | 支持邮箱密码注册、登录和退出 | P0 |
| FR-USER-02 | 支持 JWT 或 session token 认证，并提供刷新机制 | P0 |
| FR-USER-03 | 支持密码重置 | P1 |
| FR-USER-04 | 支持角色权限：个人考生、讲师、内容编辑、机构管理员、系统管理员 | P0 |
| FR-USER-05 | 支持个人空间和机构空间隔离 | P1 |
| FR-USER-06 | 支持用户资料、头像、考试目标日期和每日练习目标 | P2 |

### 6.2 分类与参考数据

| ID | 需求 | 优先级 |
|---|---|---|
| FR-TAX-01 | 内置 CISSP 8 个 domain、权重和考试版本 | P0 |
| FR-TAX-02 | 支持管理员维护考试版本、domain 权重和生效日期 | P0 |
| FR-TAX-03 | 支持维护书本、版本、作者、章节结构 | P0 |
| FR-TAX-04 | 支持维护知识点树，可绑定到一个或多个 domain | P1 |
| FR-TAX-05 | 支持 domain、书本章节、知识点之间的交叉映射 | P1 |
| FR-TAX-06 | 支持标签管理，例如 cloud、risk、crypto、IAM、SDLC | P1 |

### 6.3 题库导入与 ETL

题库入库分为两条路径，共享同一套校验、去重和审计规则：

1. **交互式导入**（FR-IMP-*）：管理员通过页面上传 CSV/XLSX/JSON 或粘贴 Markdown，适合小批量、手工录入。
2. **ETL 管道**（FR-ETL-*）：面向批量数据集的 Extract-Transform-Load 管道，适合整本书/整批授权题库的清洗入库。`docs/questions/` 目录是其典型输入（见 §10.3），例如 OSG 第 10 版的 420 道双语题目。

两条路径都写入 `ImportJob` 批次记录并遵循相同的来源、授权状态、去重和历史快照规则（见 §9.4、NFR-DATA）。

#### 6.3.1 交互式导入

| ID | 需求 | 优先级 |
|---|---|---|
| FR-IMP-01 | 支持 CSV、XLSX、JSON 导入 | P0 |
| FR-IMP-02 | 支持 Markdown 粘贴导入 | P1 |
| FR-IMP-03 | 支持导入模板下载 | P0 |
| FR-IMP-04 | 支持字段映射和导入预览 | P0 |
| FR-IMP-05 | 校验必填字段、答案格式、选项数量、domain、章节和知识点 | P0 |
| FR-IMP-06 | 支持重复题检测，包括题干 hash、相似题干、选项顺序变化 | P1 |
| FR-IMP-07 | 支持批量导入进度、错误报告和部分成功导入 | P0 |
| FR-IMP-08 | 记录导入批次、来源、授权状态、导入人和导入时间 | P0 |
| FR-IMP-09 | 支持导出题库为 CSV、JSON 或 PDF | P2 |
| FR-IMP-10 | 后续支持 DOCX/PDF 半自动解析 | P2 |

#### 6.3.2 ETL 管道

ETL 管道将一个外部数据集（一个目录，含 `manifest.json` + 题目数据文件 + 可选的翻译覆盖/待译队列）清洗为可练习的题库。三阶段执行，全程可重入、可审计、可回滚到批次粒度。

**Extract（抽取）**：从数据集目录读取清单与题目记录，保留原始字段不动，按外部稳定 ID（如 `osg-v10-ch01-q01`）建立抽取索引；识别数据集来源、版本、语言覆盖度和题型分布。

**Transform（清洗转换）**：在不修改源文件的前提下，逐题做归一化、校验、映射、去重和富化，产出待加载的中间结构。清洗规则见 §10.4。

**Load（加载）**：在单个数据库事务内写入或更新 `Book`/`Chapter`/`Question`/`QuestionOption`/`Explanation`/`QuestionMapping`，并登记 `ImportJob` 批次与 `EtlRun` 运行记录；按外部 ID 幂等，重复运行只更新变化项。

| ID | 需求 | 优先级 |
|---|---|---|
| FR-ETL-01 | 支持以数据集目录为单位的 ETL 运行，读取 `manifest.json` 清单与题目数据文件 | P0 |
| FR-ETL-02 | 支持的源格式：JSONL（首选，见 §10.3）、JSON、CSV、XLSX；Markdown 粘贴走交互式导入 | P0 |
| FR-ETL-03 | 按外部稳定 ID 做抽取索引与幂等加载，重复运行不产生重复题，仅更新变化项 | P0 |
| FR-ETL-04 | 题型映射：`single_choice`/`multiple_choice`/`true_false` 直接入库；`matching` 归一化为 `single_choice`（每题恰好 1 个正确项），`prompt_items` 存入 `questions.prompt_items` JSONB，并标记 `needs_revision`（见 §16.7） | P0 |
| FR-ETL-05 | 双语处理：同时保留 en/zh 题干、选项、解析；优先以 `zh_overrides.json` 覆盖机翻译文，`translate_queue.json` 标记缺译 | P0 |
| FR-ETL-06 | 字段校验：必填字段、`correct_keys` 必须命中存在选项、单选恰好 1 个正确项、多选 ≥2 个正确项 | P0 |
| FR-ETL-07 | 来源映射：`source.book`/`edition`/`chapter`/`chapter_title` → 复用或新建 `Book`/`Chapter`；章节→domain 走映射表 `ChapterDomainMapping`（见 §9.4） | P0 |
| FR-ETL-08 | 去重：题干 hash、外部 ID、选项集合指纹三级去重；命中已存在题时按策略跳过/更新/标记冲突 | P0 |
| FR-ETL-09 | 富化与默认值：难度缺失默认 medium；授权状态缺失默认 `unconfirmed`；带 `issues`/`zh_issues` 的题入库为 `draft` 并标记待修订 | P0 |
| FR-ETL-10 | 预览（dry-run）：先全量 Transform 产出预览报告（新增/更新/跳过/冲突/错误计数与明细），确认后再 Load | P0 |
| FR-ETL-11 | 运行记录：每次 ETL 写入 `EtlRun`（数据集、阶段、计数、错误报告、耗时、操作人），并与 `ImportJob` 关联 | P0 |
| FR-ETL-12 | 部分成功：单题失败不中断整批，失败项写入错误报告，批次标记为 `partial`；已成功项保留 | P0 |
| FR-ETL-13 | 回滚：支持按 `EtlRun` 撤销本次新增/更新（题目软删除 + 恢复上一版本快照） | P1 |
| FR-ETL-14 | 调度：支持 CLI 触发（`python -m app.etl run <dataset>`）与后台任务异步执行大批次 | P1 |
| FR-ETL-15 | 映射维护：管理员可在后台维护章节→domain、章节→知识点映射，ETL 加载时自动套用 | P1 |
| FR-ETL-16 | 多数据集：支持多个数据集并存（OSG、AIO 等），按数据集筛选与统计 | P1 |

### 6.4 题目模型与生命周期

每道题至少支持以下字段：

- 题干：Markdown 或安全富文本。
- 题型：单选、多选、判断、场景题；高级题型预留排序、拖拽、热点题。
- 选项：2-8 个选项，支持富文本。
- 正确答案：单个或多个。
- 解析：正确答案说明、错误选项解释、考点总结、延伸阅读。
- 元数据：domain、子 domain、知识点、书本、章节、难度、标签、语言、来源。
- 质量字段：状态、版本、创建人、审核人、授权状态、更新时间。

| ID | 需求 | 优先级 |
|---|---|---|
| FR-Q-01 | 支持创建、编辑、软删除题目 | P0 |
| FR-Q-02 | 支持题目状态：草稿、待审核、已发布、需修订、已归档 | P0 |
| FR-Q-03 | 支持单选和多选题完整练习体验 | P0 |
| FR-Q-04 | 支持判断题和场景题 | P1 |
| FR-Q-05 | 支持排序题、拖拽题、热点题的数据结构预留 | P1 |
| FR-Q-06 | 支持题目修改历史，记录谁在何时修改了什么 | P1 |
| FR-Q-07 | 支持题目纠错反馈：解析不清、答案疑似错误、题干歧义、版权问题 | P1 |
| FR-Q-08 | 支持题目质量统计：错误率、争议率、曝光次数、平均耗时 | P1 |

### 6.5 练习模式

| ID | 需求 | 优先级 |
|---|---|---|
| FR-PRAC-01 | 支持快速练习，由系统推荐题目 | P0 |
| FR-PRAC-02 | 支持按 domain 选择练习范围 | P0 |
| FR-PRAC-03 | 支持按书本和章节选择练习范围 | P0 |
| FR-PRAC-04 | 支持按知识点、难度、题型、标签筛选 | P1 |
| FR-PRAC-05 | 支持自定义题量：10、25、50、100、自定义 | P0 |
| FR-PRAC-06 | 支持题目顺序：随机、顺序、由易到难、弱项优先 | P1 |
| FR-PRAC-07 | 支持只练未做题、错题、收藏题、需复习题 | P0 |
| FR-PRAC-08 | 支持练习中暂停、继续和保存进度 | P1 |
| FR-PRAC-09 | 支持练习计时和单题耗时记录 | P0 |
| FR-PRAC-10 | 支持练习结束摘要：正确率、耗时、domain 分布、错题列表 | P0 |

### 6.6 答题体验与答案详解

| ID | 需求 | 优先级 |
|---|---|---|
| FR-ANS-01 | 答题页一次展示一道题、选项、进度和计时 | P0 |
| FR-ANS-02 | 用户提交后展示正确答案、用户答案和判定结果 | P0 |
| FR-ANS-03 | 解析必须说明为什么正确答案正确 | P0 |
| FR-ANS-04 | 解析应逐项解释错误选项为什么不正确 | P0 |
| FR-ANS-05 | 展示关联 domain、知识点、书本章节和个人历史答题记录 | P0 |
| FR-ANS-06 | 支持收藏、标记需复习、标记已掌握、标记有疑问 | P0 |
| FR-ANS-07 | 支持用户为题目添加个人笔记 | P1 |
| FR-ANS-08 | 支持同知识点推荐题和复习建议 | P1 |
| FR-ANS-09 | 支持考试模式下提交后统一查看解析 | P0 |

### 6.7 固定模拟考试

| ID | 需求 | 优先级 |
|---|---|---|
| FR-EXAM-01 | 支持固定题量模拟考试 | P0 |
| FR-EXAM-02 | 支持按 CISSP domain 权重自动组卷 | P0 |
| FR-EXAM-03 | 支持考试计时和时间到自动提交 | P0 |
| FR-EXAM-04 | 支持考试结束后统一查看答案和解析 | P0 |
| FR-EXAM-05 | 支持考试报告：总分、正确率、domain 表现、耗时分析、错题清单 | P0 |
| FR-EXAM-06 | 支持保存考试历史和趋势对比 | P1 |

### 6.8 CAT 模拟考试

| ID | 需求 | 优先级 |
|---|---|---|
| FR-CAT-01 | 支持 3 小时、100-150 题的 CAT 模拟考试 | P0 |
| FR-CAT-02 | CAT 模拟考试中，已提交题目不可回退、不可修改 | P0 |
| FR-CAT-03 | CAT 模拟考试中，不允许跳题 | P0 |
| FR-CAT-04 | 初始题目从中等难度开始 | P0 |
| FR-CAT-05 | 根据答题结果、能力估计、domain 覆盖和题目难度选择下一题 | P0 |
| FR-CAT-06 | 达到 100 题后，如果通过或未通过判断达到阈值，可提前结束 | P1 |
| FR-CAT-07 | 达到 150 题或 3 小时时必须结束 | P0 |
| FR-CAT-08 | 考试期间不展示实时通过概率，避免干扰答题 | P1 |
| FR-CAT-09 | 结果报告展示能力估计、置信区间、domain 表现和复习建议 | P1 |
| FR-CAT-10 | 页面明确说明 CAT 模拟不等同 ISC2 官方评分算法 | P0 |

### 6.9 学习分析

| ID | 需求 | 优先级 |
|---|---|---|
| FR-ANA-01 | 首页仪表盘展示练习题量、正确率、学习时长、连续学习天数 | P0 |
| FR-ANA-02 | 展示 8 个 domain 的正确率、题量、平均耗时和掌握度 | P0 |
| FR-ANA-03 | 展示最近 30/90 天正确率趋势 | P1 |
| FR-ANA-04 | 识别薄弱 domain 和薄弱知识点 | P0 |
| FR-ANA-05 | 错题按错误类型分类：概念不清、审题错误、记忆错误、选项混淆、时间压力 | P1 |
| FR-ANA-06 | 给出本周复习建议和下一组推荐练习 | P1 |
| FR-ANA-07 | 支持导出个人学习报告 | P2 |
| FR-ANA-08 | 机构版支持班级和学员学习报告 | P2 |

### 6.10 管理后台

| ID | 需求 | 优先级 |
|---|---|---|
| FR-ADMIN-01 | 题库管理：导入、编辑、审核、发布、归档 | P0 |
| FR-ADMIN-02 | 分类管理：考试版本、domain、知识点、书本、章节、标签 | P0 |
| FR-ADMIN-03 | 用户管理：用户、角色、状态、机构、班级 | P1 |
| FR-ADMIN-04 | 考试配置：题量、时长、组卷策略、CAT 参数 | P1 |
| FR-ADMIN-05 | 内容质量：纠错反馈、争议题、低质量题、解析缺失题 | P1 |
| FR-ADMIN-06 | 审计日志：登录、导入、编辑、发布、删除、权限变更 | P1 |
| FR-ADMIN-07 | 报表：活跃用户、练习量、正确率、题库使用率、题目错误率 | P2 |

### 6.11 题目语言与双语展示（FR-LANG）

题目内容（题干、每个选项、解析）以中英文分别存储；用户可选择语言模式 `en` / `zh` / `bilingual`，作为个人偏好保存，并可在创建练习/考试会话时覆盖、在答题过程中即时切换。仅具备所选语言的题目进入 `en`/`zh` 会话；`bilingual` 模式按题并排展示两种语言、选项 1:1 配对。所选语言模式与双语内容冻结进答案快照，历史记录不受后续编辑影响。

| ID | 需求 | 优先级 |
|---|---|---|
| FR-LANG-01 | 题干、每个选项、解析均按语言分别维护（en/zh 两份） | P0 |
| FR-LANG-02 | 用户语言模式 `en` / `zh` / `bilingual` | P0 |
| FR-LANG-03 | 默认模式作为个人偏好保存；创建练习/考试会话时可覆盖 | P0 |
| FR-LANG-04 | `en`/`zh` 会话只投递具备该语言的题目 | P0 |
| FR-LANG-05 | `bilingual` 模式按题并排展示两种语言，选项 1:1 配对 | P0 |
| FR-LANG-06 | 答题中可即时切换语言模式，不丢失已选答案、计时、进度 | P0 |
| FR-LANG-07 | 答案快照记录所选模式与双语内容；后续编辑不改变历史 | P0 |
| FR-LANG-08 | 导入接受 `*_zh` 字段；单语题目可后续补充另一语言 | P1 |
| FR-LANG-09 | 编辑器分语言编辑/预览 en 与 zh；发布校验所需语言完整性 | P0 |
| FR-LANG-10 | 管理端语言覆盖率查询 + 按缺失语言过滤 | P2 |

支撑需求（在原有章节中并入语言模式）：FR-PRAC-11（练习会话携带 `language_mode`）、FR-ANS-10（答案详解按模式返回双语解析）、FR-EXAM-07（固定考试会话携带 `language_mode`）、FR-CAT-11（CAT 会话携带 `language_mode`，切换为纯客户端状态、不调用 `/next`、不前进）。

> 实现说明：投递接口（`/api/practice/.../questions/{pos}`、`/api/exam/.../questions/{pos}`、`/api/exam/.../next`）一次性返回两种语言，客户端按模式渲染并即时切换、无需再次请求——包括 CAT（当前题的双语内容已投递，前进式 `/next` 流程不变，切换不前进）。

### 6.12 设置与界面国际化（FR-SET / FR-I18N）

新增「设置 / Settings」页面作为个人偏好的唯一入口。页面承载两类独立的语言选择：(1) **界面语言**（UI chrome 国际化，`en`/`zh`）控制导航、按钮、页面标题、表单标签、提示等界面字符串的显示语言；(2) **题目内容语言**（`language_mode`，en/zh/bilingual，沿用 FR-LANG）控制题干/选项/解析的渲染语言。两者互不影响。界面语言选择后整个系统的界面字符串即时切换为英文或中文，并作为个人偏好持久化。

界面国际化仅覆盖**手写 UI 界面字符串**，**不翻译分类数据**（CISSP domain 名称、书本/章节标题、知识点名称、标签）——这些是 taxonomy 数据，保持入库原文。题目内容语言已有独立机制（FR-LANG），不受界面语言影响。

| ID | 需求 | 优先级 |
|---|---|---|
| FR-SET-01 | 提供「设置」页面作为个人偏好唯一入口，登录后可访问 | P0 |
| FR-SET-02 | 原侧边栏账户区的题目内容语言选择器（`language_mode`）迁入设置页；侧边栏账户区改为「设置」入口 + 退出 | P0 |
| FR-SET-03 | 设置页同时承载界面语言选择（English/中文）与题目内容语言选择（en/zh/bilingual）两张卡片 | P0 |
| FR-I18N-01 | 界面语言取值 `en` / `zh`，默认 `en`，作为个人偏好保存在用户档案（`User.interface_language`） | P0 |
| FR-I18N-02 | 界面语言经既有 `GET/PUT /api/users/me/preferences` 读写；非法枚举值返回 422 | P0 |
| FR-I18N-03 | 切换界面语言后，所有 UI 界面字符串（导航、按钮、页面标题、表单标签、提示、设置页本身）即时切换，无需刷新 | P0 |
| FR-I18N-04 | 首屏即按用户界面语言渲染，无英文闪烁、无 hydration mismatch（cookie 种子 + 服务端注入初始语言） | P0 |
| FR-I18N-05 | 界面国际化仅覆盖 UI 界面字符串；不翻译 taxonomy 数据（domain/书本/章节/知识点/标签名称），题目内容语言由 FR-LANG 独立处理 | P0 |
| FR-I18N-06 | `UserOut`、`/auth/me`、`/auth/login`、`/auth/register` 响应包含 `interface_language` | P1 |

> 实现说明：界面语言偏好持久化在后端 `User.interface_language`（默认 `en`），前端以 cookie 种子的客户端 i18n context 渲染（无新依赖、无 `[locale]` 路由）。详见设计文档 `docs/superpowers/specs/2026-06-27-settings-and-ui-i18n-design.md`。

## 7. 非功能需求

### 7.1 性能

| ID | 需求 | 目标 |
|---|---|---:|
| NFR-PERF-01 | 常规页面首屏加载 | < 2s |
| NFR-PERF-02 | 练习下一题接口 P95 响应时间 | < 300ms |
| NFR-PERF-03 | 答案提交接口 P95 响应时间 | < 300ms |
| NFR-PERF-04 | CAT 选题接口 P95 响应时间 | < 500ms |
| NFR-PERF-05 | 导入 1000 道题 | < 60s |
| NFR-PERF-06 | 架构可扩展题库规模 | >= 100,000 题 |
| NFR-PERF-07 | 架构可扩展答题记录规模 | >= 10,000,000 条 |

### 7.2 安全

| ID | 需求 |
|---|---|
| NFR-SEC-01 | 密码使用 bcrypt、argon2 等强哈希存储 |
| NFR-SEC-02 | 生产环境必须启用 HTTPS |
| NFR-SEC-03 | 登录失败需要限流和锁定策略 |
| NFR-SEC-04 | 所有非公开 API 必须认证 |
| NFR-SEC-05 | 管理接口必须做角色权限校验 |
| NFR-SEC-06 | 所有数据库访问使用 ORM 或参数化查询 |
| NFR-SEC-07 | 富文本内容必须进行 XSS 清洗和白名单过滤 |
| NFR-SEC-08 | 上传文件必须限制类型、大小并进行安全扫描 |

### 7.3 数据完整性

| ID | 需求 |
|---|---|
| NFR-DATA-01 | 已完成练习和考试必须保存题目快照，避免题目后续修改影响历史记录 |
| NFR-DATA-02 | 题目删除使用软删除，不得破坏历史答题记录 |
| NFR-DATA-03 | 用户学习数据每日备份 |
| NFR-DATA-04 | 导入任务必须可追踪、可重试、可回滚或可批量归档 |
| NFR-DATA-05 | 关键管理操作必须写审计日志 |

### 7.4 可用性与可访问性

| ID | 需求 |
|---|---|
| NFR-UX-01 | 练习页面应减少干扰，突出题干、选项、计时和提交 |
| NFR-UX-02 | 普通练习支持桌面、平板和移动端 |
| NFR-UX-03 | CAT 模拟考试优先保障桌面端体验 |
| NFR-UX-04 | 支持键盘选择选项和提交答案 |
| NFR-UX-05 | 颜色反馈不能作为唯一状态提示 |
| NFR-UX-06 | 目标满足 WCAG 2.1 AA |
| NFR-UX-07 | 解析页应适合长文本、表格、代码块和图片 |
| NFR-UX-08 | 支持浅色和深色模式可作为 P2 增强 |

### 7.5 合规

| ID | 需求 |
|---|---|
| NFR-COMP-01 | 题库必须记录来源和授权状态 |
| NFR-COMP-02 | 系统不得默认导入或分发未经授权的官方真题或第三方版权题库 |
| NFR-COMP-03 | 页面应展示商标归属说明：CISSP 和 ISC2 为 ISC2, Inc. 的注册商标 |
| NFR-COMP-04 | 页面应说明本产品不是 ISC2 官方考试平台，除非获得授权不得暗示官方背书 |
| NFR-COMP-05 | 机构版应支持租户数据隔离 |

## 8. 信息架构与关键页面

### 8.1 页面清单

| 页面 | 核心内容 |
|---|---|
| 登录/注册 | 注册、登录、忘记密码 |
| 首页仪表盘 | 学习概览、薄弱 domain、今日建议、继续练习 |
| 题库导入 | 上传文件、字段映射、预览校验、导入结果 |
| 题目管理 | 筛选、编辑、审核、批量操作、纠错反馈 |
| 分类管理 | domain、知识点、书本、章节、标签 |
| 练习配置 | 选择范围、题量、模式、计时、选项打乱 |
| 答题页 | 题干、选项、进度、计时、提交、标记 |
| 解析页 | 答案、解析、错误选项解释、知识点、笔记 |
| 错题本 | 错题筛选、重练、掌握状态 |
| 收藏题 | 收藏题列表和专项练习 |
| 固定模拟考试 | 规则确认、考试答题、计时、提交 |
| CAT 模拟考试 | CAT 规则确认、动态出题、前进式答题 |
| 考试报告 | 总结果、domain 分析、耗时分析、复习建议 |
| 设置 | 界面语言（English/中文）、题目内容语言（en/zh/bilingual） |
| 管理后台 | 用户、题库、分类、配置、报表、审计 |

### 8.2 答题页原则

- 主区域只展示当前题目和选项。
- 练习模式下可以提交后立即显示解析。
- 考试模式下不显示解析，结束后统一查看。
- CAT 模拟考试中提交后直接进入下一题，不允许返回修改。
- 题干、选项和解析都要支持长文本和代码块。

## 9. 技术架构

### 9.1 总体架构

```text
用户浏览器
  |
  | HTTPS / REST
  v
Next.js App Router 前端
  |
  | REST API
  v
FastAPI 后端
  |-- Auth Service
  |-- Question Bank Service
  |-- Import Service
  |-- Practice Service
  |-- Exam Service
  |-- CAT Engine
  |-- Analytics Service
  |-- Admin Service
  |
  | SQL / Cache / Queue
  v
PostgreSQL + Redis + Background Worker
```

### 9.2 前端 Next.js

- 使用 Next.js App Router、React、TypeScript。
- 服务端数据建议使用 TanStack Query。
- 本地练习状态可使用 Zustand 或 React Context。
- 表单使用 React Hook Form + Zod 校验。
- UI 组件建议使用 shadcn/ui 或同类组件库。
- 图表可使用 ECharts、Recharts 或 Tremor。
- 富文本渲染使用 Markdown/HTML 白名单清洗。

### 9.3 后端 FastAPI

- 使用 FastAPI 提供 REST API。
- 数据库建议 PostgreSQL。
- ORM 可使用 SQLAlchemy 2.x 或 SQLModel。
- 数据迁移使用 Alembic。
- 后台任务使用 Celery、RQ 或 Arq 处理导入、去重、报表生成。
- Redis 用于缓存、限流、任务状态和 CAT 临时状态。
- 搜索可先使用 PostgreSQL full-text，后续扩展 Elasticsearch/OpenSearch。

### 9.4 核心数据模型

| 模型 | 说明 |
|---|---|
| User | 用户信息、角色、机构、状态、`language_mode`（默认题目内容语言模式，FR-LANG-02/03）、`interface_language`（界面语言 en/zh，默认 en，FR-I18N-01） |
| Organization | 机构或租户 |
| Role/Permission | 角色和权限 |
| ExamBlueprint | 考试版本、题量、时长、通过线、生效日期 |
| ExamDomain | CISSP domain、权重、版本 |
| Book | 书本或资料来源 |
| Chapter | 书本章节 |
| KnowledgePoint | 知识点树 |
| Question | 题目主体、题型、状态、难度、`available_languages`、授权 |
| QuestionTranslation | 按语言存储的题干、选项内容、解析（`(question_id, language)` 唯一，FR-LANG-01） |
| QuestionOption | 选项顺序、正确性（与语言无关的答案键；内容见 QuestionTranslation） |
| Explanation | （v1.1 已废弃，内容并入 QuestionTranslation） |
| QuestionMapping | 题目与 domain、章节、知识点、标签的映射 |
| ImportJob | 导入任务、状态、错误报告、来源 |
| EtlDataset | ETL 数据集（目录、来源、版本、题目数、语言覆盖度） |
| EtlRun | 单次 ETL 运行（数据集、阶段、计数、错误报告、耗时、操作人），关联 ImportJob |
| ChapterDomainMapping | 章节→domain 映射规则，供 ETL 加载时自动套用 |
| QuestionExternalKey | 题目外部稳定 ID（如 `osg-v10-ch01-q01`），唯一键为 `(dataset_slug, external_id)`，用于幂等加载与去重 |
| PracticeSession | 练习会话、范围、状态、统计（`config.language_mode` 存语言模式） |
| PracticeAnswer | 练习答题记录和题目快照（快照含双语内容与模式，FR-LANG-07） |
| ExamSession | 固定模拟考试或 CAT 模拟考试会话（`config.language_mode` 存语言模式） |
| ExamAnswer | 考试答题记录、能力估计、耗时 |
| UserQuestionState | 收藏、笔记、错题、掌握状态 |
| AuditLog | 管理操作和关键变更日志 |

### 9.5 核心 API

```text
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
GET    /api/auth/me

# FR-LANG：用户语言模式偏好（FR-LANG-02/03）；FR-I18N：界面语言偏好（FR-I18N-01/02）
GET    /api/users/me/preferences
PUT    /api/users/me/preferences

GET    /api/domains
POST   /api/domains
GET    /api/books
POST   /api/books
GET    /api/books/{book_id}/chapters
GET    /api/knowledge-points

GET    /api/questions
POST   /api/questions
GET    /api/questions/{question_id}
PUT    /api/questions/{question_id}
DELETE /api/questions/{question_id}
POST   /api/questions/{question_id}/review
POST   /api/questions/import
GET    /api/questions/import/{job_id}
GET    /api/questions/export
GET    /api/questions/language-coverage            # FR-LANG-10
GET    /api/admin/questions/language-coverage      # 管理端覆盖率（admin:view_reports）

GET    /api/etl/datasets
GET    /api/etl/datasets/{dataset}
POST   /api/etl/runs                 # 启动 ETL（支持 dry-run 预览）
GET    /api/etl/runs
GET    /api/etl/runs/{run_id}
POST   /api/etl/runs/{run_id}/commit # 预览确认后提交加载
POST   /api/etl/runs/{run_id}/rollback
GET    /api/etl/mappings             # 章节→domain 映射
POST   /api/etl/mappings
PUT    /api/etl/mappings/{mapping_id}

POST   /api/practice/sessions
GET    /api/practice/sessions/{session_id}
GET    /api/practice/sessions/{session_id}/next
POST   /api/practice/sessions/{session_id}/answers
GET    /api/practice/sessions/{session_id}/summary

POST   /api/exams/sessions
GET    /api/exams/sessions/{session_id}/next
POST   /api/exams/sessions/{session_id}/answers
GET    /api/exams/sessions/{session_id}/result

POST   /api/cat/sessions
GET    /api/cat/sessions/{session_id}/next
POST   /api/cat/sessions/{session_id}/answers
GET    /api/cat/sessions/{session_id}/result

GET    /api/analytics/overview
GET    /api/analytics/domains
GET    /api/analytics/trends
GET    /api/analytics/weak-areas

POST   /api/questions/{question_id}/bookmark
DELETE /api/questions/{question_id}/bookmark
POST   /api/questions/{question_id}/notes
PUT    /api/notes/{note_id}
```

> FR-LANG 投递：`/api/practice/.../questions/{pos}`、`/api/exam/.../questions/{pos}`、`/api/exam/.../next` 一次性返回两种语言（`stem`/选项 `content`/解析均为 `{en, zh}`），客户端按 `language_mode` 渲染并即时切换。会话创建接口（`POST /api/practice/sessions`、`POST /api/exam/sessions`）接受可选 `language_mode`，缺省取用户偏好。

### 9.6 ETL 管道架构

ETL 作为独立服务模块（`app/etl/`），由抽取器、转换器、加载器三段管线组成，可由 API 或 CLI 触发：

- **`app/etl/extract.py`**：按数据集目录读取 `manifest.json` 与题目文件，产出原始记录流（`RawQuestion`），按外部 ID 去索引。源格式适配器：`JsonlExtractor`、`JsonExtractor`、`CsvExtractor`、`XlsxExtractor`。
- **`app/etl/transform.py`**：对原始记录执行 §10.4 清洗规则，产出 `CleanedQuestion` 中间结构与错误/冲突清单；纯函数、无副作用、可单测。
- **`app/etl/load.py`**：在单个事务内将 `CleanedQuestion` 写入 ORM（`Book`/`Chapter`/`Question`/`QuestionOption`/`Explanation`/`QuestionMapping`/`QuestionExternalKey`），登记 `EtlRun` + `ImportJob`，更新历史快照；按外部 ID 幂等。
- **`app/etl/runner.py`**：编排三段管线，支持 `dry-run`（只 Extract+Transform 产出预览）与 `commit`（执行 Load），记录耗时与计数。

数据集目录约定为 `docs/questions/<dataset>/`（开发期）或可配置的导入根目录（生产期）。ETL 不修改源文件；所有变更通过 ORM 落库并经 `AuditLog` 审计。大批次 ETL 通过后台任务（Celery/RQ/Arq）异步执行，前端通过 `GET /api/etl/runs/{run_id}` 轮询进度。

```text
docs/questions/<dataset>/ ──Extract──▶ RawQuestion ──Transform──▶ CleanedQuestion ──Load──▶ ORM + ImportJob + EtlRun
        (源文件只读)            (按外部ID索引)        (清洗/校验/去重/富化)        (单事务, 幂等, 审计)
```

## 10. 导入模板建议

### 10.1 CSV/XLSX 字段

| 字段 | 必填 | 示例 |
|---|---|---|
| question_text | 是 | Which security principle... |
| question_type | 是 | single_choice |
| option_a | 是 | Confidentiality |
| option_b | 是 | Integrity |
| option_c | 否 | Availability |
| option_d | 否 | Accountability |
| correct_answers | 是 | A |
| explanation | 是 | The best answer is... |
| option_explanations | 否 | JSON 格式逐项解释 |
| domain | 是 | 1 |
| knowledge_points | 否 | risk management; due care |
| book | 否 | OSG 10th Edition |
| chapter | 否 | Chapter 1 |
| difficulty | 否 | medium |
| tags | 否 | governance;risk |
| source | 否 | user_import |
| license_status | 否 | user_owned |
| language | 否 | en |
| question_text_zh | 否 | 哪项安全原则……（FR-LANG-08，中文题干） |
| option_a_zh … option_d_zh | 否 | 保密性……（与对应 en 选项 1:1 配对） |
| explanation_zh | 否 | 最佳答案是……（中文解析） |
| option_explanations_zh | 否 | JSON 格式逐项中文解释 |

> FR-LANG-08：`*_zh` 字段可选；若提供任一 `*_zh`，则所提供选项的 zh 必须完整且与 en 按字母 1:1 配对；zh 不完整的题目仍可导入但标记 `needs_revision`，不阻塞批次。导入后单语题目可后续补充另一语言。

### 10.2 导入校验规则

- 单选题必须只有一个正确答案。
- 多选题必须有两个或以上正确答案。
- 正确答案必须对应存在的选项。
- domain 必须属于当前考试版本。
- 难度缺失时默认为 medium。
- 题干或解析为空时不允许发布。
- 授权状态为空时允许导入，但必须标记为未确认，不能进入共享题库。
- 若提供任一 `*_zh` 字段，则所提供选项的 zh 必须完整且与 en 1:1 配对（FR-LANG-08）；不完整者标记 `needs_revision` 但不阻塞导入。

### 10.3 ETL 数据集源格式（JSONL + 清单）

ETL 的首选输入是一个数据集目录，例如 `docs/questions/osg10/`：

```
docs/questions/<dataset>/
├── manifest.json          # 数据集清单（必填）
├── questions.jsonl        # 题目记录，每行一道题（必填）
├── zh_overrides.json      # 中文人工译文覆盖，按外部 ID 索引（可选）
└── translate_queue.json   # 待翻译/缺译的外部 ID 列表（可选）
```

**manifest.json** — 数据集级元数据：

| 字段 | 说明 | 示例 |
|---|---|---|
| source | 原始来源描述 | `book-md/CISSP_OSG_v10-en/...` |
| total_questions | 题目总数 | `420` |
| chapters | 章节数 | `21` |
| type_counts | 题型分布 | `{"single_choice":385,"multiple_choice":32,"matching":3}` |
| zh_reused_from_v9 / zh_from_overrides / zh_pending_count | 中文覆盖度统计 | `400 / 20 / 0` |

**questions.jsonl** — 每行一道题，字段如下：

| 字段 | 说明 | 示例 |
|---|---|---|
| id | 外部稳定 ID，幂等去重主键 | `osg-v10-ch01-q01` |
| source | 来源元信息 | `{book, edition, section, chapter, chapter_title, number}` |
| type | 题型 | `single_choice` / `multiple_choice` / `matching` |
| stem | 双语题干 | `{"en":"...","zh":"..."}` |
| options | 选项数组 | `[{key:"A", text:{en,zh}}]` |
| correct_keys | 正确选项 key 数组 | `["C"]` 或 `["A","C","D","F"]` |
| explanation | 双语解析 | `{"en":"...","zh":"..."}` |
| meta | 质量与翻译标记 | `{choose_all, matching, issues, zh_source, zh_issues}` |
| prompt_items | 仅 matching 题：配对项 | `[{key, text:{en,zh}}]` |

ETL 读取时以 `manifest.json` 建立数据集记录，逐行解析 `questions.jsonl`，`zh_overrides.json` 在 Transform 阶段按 ID 覆盖 `stem/explanation/options` 的 zh 字段，`translate_queue.json` 中的题标记为缺译并入库为 `draft`。

### 10.4 ETL 清洗（Transform）规则

抽取后的原始记录在 Transform 阶段做以下处理，全部不修改源文件：

1. **题型归一化**：`single_choice`/`multiple_choice`/`true_false` 直接映射到 `QuestionType`；`matching` 归一化为 `single_choice`（每题恰好 1 个正确项，`correct_keys` 长度为 1），`prompt_items` 存入 `questions.prompt_items` JSONB，并标记 `needs_revision`（开放问题 §16.7）。
2. **双语合并**：题干/选项/解析同时保留 en 与 zh；zh 优先级为 `zh_overrides.json` > 源记录 zh > 空；缺译项写 `translate_queue`。题库 `language` 字段记录主语言（默认 `en`），双语以独立字段或变体存储。
3. **必填校验**：题干、至少 2 个选项、`correct_keys`、解析非空；`correct_keys` 必须全部命中存在选项 key。
4. **答案一致性**：单选恰好 1 个正确项；多选 ≥2 个正确项；不满足则记入错误报告，该题不入库。
5. **来源映射**：`source.book`+`edition` → 复用或新建 `Book`；`chapter`+`chapter_title` → 复用或新建 `Chapter`；`ChapterDomainMapping` 将章节映射到 CISSP domain，写入 `QuestionMapping.domain_id`。无映射规则的章节，domain 留空待人工补充。
6. **去重**：外部 ID 命中已有题 → 比对内容指纹，无变化则跳过，有变化则更新并递增 `version`；题干 hash 命中不同外部 ID → 标记冲突，跳过待人工裁决。
7. **富化默认值**：难度缺失 → `medium`；`license_status` 缺失 → `unconfirmed`；`meta.issues`/`zh_issues` 非空或 `matching` 题 → 入库状态 `draft` + 标记待修订。
8. **快照**：更新已有题时，先用 `snapshot_question()` 写入 `QuestionRevision` 历史快照，再更新当前版本。
9. **错误隔离**：单题 Transform 失败不中断整批，失败原因与原始 ID 写入 `EtlRun.error_report`，批次最终状态为 `partial` 或 `completed`。

## 11. CAT 模拟策略

### 11.1 MVP 策略

MVP 可采用规则驱动加简化能力估计：

1. 每道题设置难度值，范围 1-5。
2. 用户初始能力值设为中位。
3. 答对后能力估计上升，答错后能力估计下降。
4. 下一题从相近难度题池中选择，同时满足 domain 权重覆盖。
5. 防止同一知识点或同一来源题目连续出现过多。
6. 达到 100 题后，如果能力估计明显高于或低于通过阈值，可结束考试。
7. 如果判断不稳定，则继续出题，直到 150 题或时间耗尽。

### 11.2 后续增强

后续版本可引入正式 IRT 模型：

- 题目难度参数 b。
- 区分度参数 a。
- 猜测参数 c。
- 能力值 theta。
- 标准误 SE。
- 题目曝光率控制。
- 题库参数校准流程。

注意：在没有足够真实答题样本和题目校准之前，不应把 3PL IRT 作为 P0 强依赖。否则算法看起来专业，但结果可信度不足。

### 11.3 CAT 边界说明

- CAT 模拟报告中的通过/未通过只是学习评估，不应被包装成官方预测。
- 报告应优先给出“准备度”和“薄弱项”，避免过度承诺考试结果。
- 管理后台应允许调整 CAT 参数，并保留参数版本，方便复盘不同算法版本下的考试结果。

## 12. MVP 范围

### 12.1 MVP 必须包含

1. 用户注册登录。
2. CSV/XLSX/JSON 题库导入。
3. ETL 管道：以 `docs/questions/` 数据集为输入，完成抽取、清洗、幂等加载，首批导入 OSG 第 10 版双语题库。
4. 导入模板、字段映射、预览校验、错误报告。
4. 题目管理和基本分类管理。
5. 单选、多选题练习。
6. 按 domain、书本、章节筛选练习。
7. 答题后查看答案详解和错误选项解释。
8. 错题本、收藏题和个人笔记。
9. 固定题量模拟考试。
10. 基础 CAT 模拟考试。
11. 学习仪表盘和 domain 正确率分析。
12. 基础管理后台。
13. 题目中英文双语存储与展示，用户可选 `en`/`zh`/`bilingual` 语言模式并在答题中即时切换（FR-LANG-01..07、09）。
14. 设置页与界面国际化：设置页承载界面语言（English/中文）与题目内容语言选择，界面语言切换后整个 UI 界面即时切换并持久化（FR-SET-01..03、FR-I18N-01..05）。

### 12.2 MVP 暂不包含

1. PDF/DOCX 自动解析。
2. 拖拽题、热点题等复杂高级题型完整交互。
3. 机构版计费和订阅。
4. AI 自动生成题目。
5. 离线练习。
6. 原生移动 App。

## 13. 发布阶段

| 阶段 | 周期 | 目标 |
|---|---:|---|
| Phase 0 | 1 周 | 数据模型、导入模板、页面原型、技术脚手架 |
| Phase 1 | 3-4 周 | 登录、题库导入、题目管理、基础练习 |
| Phase 2 | 2-3 周 | 错题本、收藏、个人笔记、解析增强、学习仪表盘 |
| Phase 3 | 3-4 周 | 固定模拟考试、基础 CAT 模拟考试、考试报告 |
| Phase 4 | 2-3 周 | 管理后台、内容质量、性能、安全、审计 |
| Phase 5 | 持续 | 机构版、多语言、复杂题型、AI 辅助、正式 IRT 校准 |

## 14. 验收标准

1. 用户可以上传符合模板的 CSV/XLSX/JSON 文件，并成功导入题目、选项、答案和解析。
2. 导入时系统可以发现必填字段缺失、答案格式错误、domain 不存在和重复题。
3. ETL 可以读取 `docs/questions/` 数据集（`manifest.json` + `questions.jsonl` + `zh_overrides.json`），完成清洗后幂等加载为可练习题目，重复运行不产生重复题。
4. ETL 预览（dry-run）能给出新增/更新/跳过/冲突/错误计数与明细，确认后再实际写入。
5. ETL 对 `matching` 题型、缺译题、带 `issues` 的题入库为 `draft` 并标记待修订，不阻塞整批导入。
6. ETL 每次运行登记 `EtlRun` + `ImportJob`，记录数据集、计数、错误报告与操作人。
7. 用户可以按书本、章节、domain 组合筛选题目并开始练习。
8. 用户提交答案后能看到正确答案、解析和错误选项解释。
9. 用户答错的题会自动进入错题本。
10. 用户可以收藏题目、添加个人笔记并在后续练习中筛选。
11. 用户可以启动固定模拟考试，并获得考试报告。
12. 用户可以启动 CAT 模拟考试，系统按动态策略出题并在 100-150 题内结束。
13. CAT 模拟考试中，用户提交后不能返回修改上一题。
14. 管理员可以维护考试版本、domain、书本、章节和知识点。
15. 系统可以展示用户各 domain 的正确率、题量、耗时和趋势。
16. 系统对题库内容来源、授权状态、导入批次和管理操作有记录。
17. 已完成练习和考试的历史记录不因题目后续编辑而改变。
18. 题目的题干、每个选项、解析按中英文分别存储（FR-LANG-01）。
19. 用户可选 `en`/`zh`/`bilingual` 语言模式，默认作为个人偏好保存，创建会话时可覆盖（FR-LANG-02/03）。
20. `en`/`zh` 会话不投递缺失该语言的题目；`bilingual` 按题并排展示、选项 1:1（FR-LANG-04/05）。
21. 答题中即时切换语言模式不丢失已选答案、计时、进度；CAT 切换不调用 `/next`、不前进（FR-LANG-06）。
22. 答案快照冻结所选模式与双语内容，历史不受后续编辑影响（FR-LANG-07）。
23. 编辑器分语言编辑/预览 en 与 zh，发布校验所需语言完整性（FR-LANG-09）。
24. 管理端可查询语言覆盖率并按缺失语言过滤（FR-LANG-10）。
25. 登录后侧边栏账户区提供「设置」入口且不再直接暴露题目内容语言下拉；设置页同时承载界面语言（English/中文）与题目内容语言（en/zh/bilingual）两张卡片（FR-SET-01..03）。
26. 用户选择界面语言后，所有 UI 界面字符串（导航、按钮、页面标题、表单标签、提示）即时切换为该语言，刷新后保持；首屏无英文闪烁（FR-I18N-03/04）。
27. 界面语言偏好持久化在后端 `User.interface_language`，经 `/api/users/me/preferences` 读写，非法枚举值返回 422；`/auth/me` 等响应包含 `interface_language`（FR-I18N-01/02/06）。
28. 界面国际化仅覆盖 UI 界面字符串，不翻译 taxonomy 数据（domain/书本/章节/知识点/标签名称）；题目内容语言由 FR-LANG 独立处理（FR-I18N-05）。

## 15. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| CAT 官方算法不可公开复制 | 过度承诺会误导用户 | 明确学习用途，使用准备度和薄弱项表达 |
| 题库版权不清 | 法律和商业风险 | 记录来源、授权状态、导入批次，限制共享 |
| 用户导入格式混乱 | 导入失败率高 | 模板、字段映射、预览校验、错误报告 |
| 题目质量参差不齐 | 学习效果下降 | 审核流程、纠错反馈、争议题统计 |
| 章节和 domain 映射成本高 | 内容维护压力大 | 支持批量标注，后续引入 AI 辅助 |
| 过早实现复杂题型 | 延误 MVP | MVP 聚焦单选、多选，复杂题型先做数据结构预留 |
| 缺少 IRT 校准数据 | CAT 结果不可信 | MVP 使用规则驱动，后续通过答题数据校准 |
| 机构版权限复杂 | 后期重构成本高 | 提前设计租户、角色和审计模型 |
| ETL 源数据脏（缺译、题型不匹配、章节无 domain 映射） | 入库质量差或整批失败 | dry-run 预览、单题错误隔离、问题题入库 draft 待修订、章节映射表可维护 |

## 16. 开放问题

1. MVP 优先面向个人考生，还是从第一版就支持培训机构？
2. 首批题库是否由用户自行导入，还是提供授权样例题库？
3. 是否需要中英文双语界面？题库内容是否优先英文？**已决议（2026-06-26，v1.1）**：题库内容（题干、选项、解析）按中英文分别存储并支持 `en`/`zh`/`bilingual` 展示与即时切换（FR-LANG-01..10，见 §6.11）。**UI 界面字符串（chrome）国际化已于 v1.2 纳入范围（2026-06-27）**：新增界面语言 `en`/`zh` 选择（FR-I18N-01..06，见 §6.12），切换后整个 UI 界面即时切换并持久化；仅覆盖手写界面字符串，taxonomy 数据（domain/书本/章节/知识点/标签名称）有意不译，留待后续版本。
4. 书本章节是否优先支持 OSG、AIO、Eleventh Hour 等常见教材？
5. CAT 模拟结果是否显示“通过/未通过”，还是显示“准备度等级”更稳妥？
6. 是否需要部署为 SaaS，还是先做自托管 Web 应用？
7. `matching` 题型在 MVP 中如何落库：~~归一化为多选、扩展 `QuestionType` 新增 `matching` 枚举，还是暂存为 draft 待后续支持配对交互？~~ **已决议（2026-06-21）**：归一化为 `single_choice`（每题恰好 1 个正确项），`prompt_items` 存入 `questions.prompt_items` JSONB，并标记 `needs_revision`。后续如需配对交互再扩展枚举。
8. OSG 章节到 CISSP 8 大 domain 的映射规则由谁维护、是否随教材版本变化？**已决议（2026-06-21）**：以 `ChapterDomainMapping`（GLOBAL）承载，OSG v10 的 21 章→8 domain 默认映射随 seed 一起初始化（见 §10.4 与 ETL 设计文档），后续可经 `/api/etl/mappings` 维护、随教材版本以新 `dataset_slug` 区分。
9. 双语内容如何落库？~~**已决议（2026-06-21）**：每个源题生成两条 `Question` 行（`language='en'` 与 `'zh'`），经同一 `external_id` 关联（`QuestionExternalKey` 唯一约束 `(dataset_slug, external_id, language)`）。保留现有 `stem`/`content` 单一 Text 列不动；练习/考试会话在渲染时按所选语言取对应行。~~ **已修订（2026-06-26，v1.1）**：改为“一题一行 + `question_translations` 多语言行”模型——一条 `Question` 持结构/规范字段与 `available_languages`，`question_translations` 按语言存题干/选项内容/解析（`(question_id, language)` 唯一）；`QuestionOption` 仅保留 `order_index`+`is_correct`（与语言无关的答案键）；`Explanation` 表废弃，内容并入翻译行；`QuestionExternalKey` 唯一键改为 `(dataset_slug, external_id)`。该模型支持手工命题题目的并排展示、即时切换与分语言编辑（FR-LANG-05/06/09），旧“两行”方案被取代。ETL 代码沿用并适配新模型（见 §6.3/§9.6）。

## 17. 推荐下一步

1. 确认 MVP 目标用户：个人自学版或机构教学版。
2. 确认第一版导入模板字段。
3. 确认题目状态流转：草稿、待审核、已发布、需修订、已归档。
4. 设计核心页面线框图：导入、练习、解析、考试、报告、管理后台。
5. 基于本 PRD 拆分数据模型、API 设计和前端任务。
6. 先实现固定模拟考试，再实现基础 CAT，降低算法不确定性。

## 18. 术语表

| 术语 | 定义 |
|---|---|
| CISSP | Certified Information Systems Security Professional |
| ISC2 | CISSP 认证所属组织 |
| CAT | Computerized Adaptive Testing，根据答题表现动态选题的考试形式 |
| Domain | CISSP 考试大纲中的知识领域 |
| OSG | Official Study Guide，常见 CISSP 官方学习指南简称 |
| AIO | All-in-One Exam Guide，常见 CISSP 学习资料简称 |
| IRT | Item Response Theory，项目反应理论 |
| 3PL | 三参数 Logistic IRT 模型，包含区分度、难度和猜测参数 |
| theta | 能力估计值 |
| SE | 标准误，用于表达能力估计的不确定性 |
| 题目快照 | 答题时保存的题目和选项副本，用于保证历史记录不被后续编辑影响 |
