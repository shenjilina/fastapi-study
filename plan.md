# 【最终终版】14天新手可控｜FastAPI\+LangChain\+Chroma\+Alembic\+UV 商用级RAG开发计划（每日2小时·零漏洞完整版）

## 一、项目固定技术栈（商用稳定版）

- **后端框架**：FastAPI（高性能接口、自动文档）

- **ORM框架**：SQLAlchemy 2\.0（标准企业级数据库操作）

- **数据库迁移**：Alembic（数据库版本可控、可回滚）

- **RAG核心框架**：LangChain（统一切片、检索、Prompt、问答链、对话记忆）

- **向量数据库**：Chroma（本地持久化、轻量稳定）

- **大模型**：Ollama（本地私有化部署、无外网依赖）

- **嵌入模型**：sentence\-transformers（通用语义向量化）

- **支持文档格式**：TXT、PDF

- **依赖管理**：UV（现代工程化、版本锁定、环境隔离）

## 二、项目强制架构铁律（补全漏洞·绝对禁止违规）

**本章节为项目架构底线，所有代码必须严格遵守，杜绝新手架构混乱、线上BUG**

### 1\. 单向分层调用规则（无反向依赖）

controller → service → crud / core / utils → model

core/langchain 为底层基础能力，仅被 service 调用，不依赖任何业务层代码

**绝对禁止**：core调用api、utils调用db、model依赖上层业务、controller写业务逻辑

### 2\. 分层唯一职责（彻底解耦）

- **controller**：仅处理路由接收、参数校验、统一响应、依赖注入，无任何业务、DB、RAG逻辑

- **service**：组装业务流程、事务控制、串联底层能力，不操作数据库、不实例化底层组件

- **crud**：纯粹数据库增删改查，无业务逻辑、无RAG、无LLM调用

- **model**：仅定义数据表字段、关联关系、状态枚举，无任何业务代码

- **schema**：仅做请求/响应数据校验、结构化定义

- **core/langchain**：封装所有LangChain底层组件、向量库、LLM、RAG链，全局唯一实例

- **utils**：纯无状态工具函数，不依赖业务、不存储全局变量

### 3\. 核心补充架构规范（修复原计划重大漏洞）

- **依赖注入规范**：所有数据库会话必须通过 Depends\(get\_db\) 注入，禁止全局Session、禁止手动创建会话，杜绝并发卡死

- **无状态规范**：所有core、utils、service层代码纯无状态，不存储用户上下文、临时数据，避免多用户数据错乱

- **LangChain隔离规范**：业务层仅调用封装好的方法，禁止在service/controller实例化LangChain对象、手写Prompt、自定义切片规则

- **开发顺序强制规范**：所有新功能严格遵循 **model → schema → crud → service → controller**，杜绝逆向开发

## 三、最终完整项目目录（工程化终版·无缺失）

```Plain Text
rag_project/
├── api/                          # 业务模块层
│   ├── __init__.py
│   ├── rag/                      # RAG问答核心模块
│   │   ├── __init__.py
│   │   ├── controller.py
│   │   ├── service.py
│   │   ├── crud.py
│   │   ├── model.py
│   │   ├── schema.py
│   │   └── enums.py              # 新增：问答、知识库状态枚举
│   ├── document/                 # 文档管理模块
│   │   ├── __init__.py
│   │   ├── controller.py
│   │   ├── service.py
│   │   ├── crud.py
│   │   ├── model.py
│   │   ├── schema.py
│   │   └── enums.py              # 新增：文档解析状态枚举
│   └── user/                     # 用户权限模块
│       ├── __init__.py
│       ├── controller.py
│       ├── service.py
│       ├── crud.py
│       ├── model.py
│       └── schema.py
├── core/                         # 全局核心底层
│   ├── __init__.py
│   ├── db.py                     # 数据库会话、引擎、依赖注入
│   ├── app.py                    # FastAPI应用初始化
│   ├── exceptions.py             # 全局异常捕获、自定义业务异常
│   ├── security.py               # JWT鉴权、密码加密
│   ├── constants.py              # 新增：全局常量（token阈值、上下文最大token等）
│   └── langchain/                # LangChain底层统一封装
│       ├── __init__.py
│       ├── embedding.py
│       ├── chroma_store.py
│       ├── llm.py
│       ├── retriever.py
│       └── rag_chain.py
├── config/                       # 全局配置中心
│   ├── __init__.py
│   ├── settings.py               # 主配置（环境变量统一管理）
│   └── log_config.py             # 新增：日志标准化配置
├── common/                       # 公共通用组件
│   ├── __init__.py
│   ├── response.py               # 统一接口返回格式
│   ├── middleware.py            # 跨域、请求日志、耗时统计
│   └── dependencies.py           # 新增：全局依赖（鉴权、参数清洗）
├── utils/                        # 无状态工具函数
│   ├── __init__.py
│   ├── file_parser.py            # PDF/TXT文档解析
│   ├── text_utils.py             # 新增：文本清洗、token截断、去重工具
│   └── hash_utils.py             # 新增：文件MD5去重工具
├── scripts/                      # 运维脚本
│   ├── alembic/                  # 数据库版本迁移
│   └── init_db.py                # 新增：基础数据初始化脚本
├── logs/                         # 新增：日志存储目录
├── .env                          # 新增：环境变量文件
├── .gitignore                    # 新增：git忽略配置
├── .python-version               # UV生成：Python版本锁定
├── pyproject.toml                # UV：项目依赖声明
├── uv.lock                       # UV：依赖版本锁定
├── init_app.py                   # 应用统一初始化入口
└── main.py                       # 项目启动入口
```

## 四、UV现代化依赖管理规范（最终版·替代pip）

彻底废弃 requirements\.txt，采用 UV 工业级依赖管理，解决版本冲突、环境不一致、安装卡顿问题

### 1\. 全局安装UV

```Plain Text
pip install uv
```

### 2\. 项目初始化标准命令（Day1必做）

```Plain Text
# 初始化项目结构、配置文件
uv init

# 安装生产核心依赖
uv add fastapi uvicorn sqlalchemy alembic chromadb sentence-transformers python-multipart python-dotenv PyPDF2 langchain langchain-chroma langchain-ollama langchain-text-splitters langchain-core

# 安装开发依赖（仅调试用，不参与生产部署）
uv add --dev pytest ruff ipython

# 同步虚拟环境、锁定版本
uv sync
```

### 3\. 项目通用运行命令

```Plain Text
# 启动项目
uv run main.py

# 数据库迁移
uv run alembic revision --autogenerate -m "备注"
uv run alembic upgrade head

# 单元测试、代码检查
uv run pytest
uv run ruff check
```

### 4\. UV核心规范

- uv\.lock 强制纳入版本管控，保证团队/部署环境完全一致

- 严格区分生产/开发依赖，生产环境无冗余包

- 自动管理虚拟环境，无需手动激活/退出

## 五、漏洞补齐核心能力（原计划缺失·商用必备）

所有缺失能力已全部嵌入14天开发流程，无遗漏、无BUG隐患

- **数据模型补齐**：新增知识库表、文档状态字段、用户关联外键、对话关联知识库/用户、数据状态枚举

- **RAG核心漏洞修复**：文档MD5去重、向量重复过滤、知识库隔离检索、上下文Token截断、无检索结果兜底

- **向量库能力补齐**：支持文档/向量精准删除、垃圾数据清理、向量库异常恢复

- **安全能力补齐**：文件类型白名单、文件大小限制、参数清洗、LLM超时保护、接口容错

- **稳定性补齐**：Ollama重试机制、数据库事务回滚、空数据兜底、切片异常捕获

- **工程化补齐**：标准化日志、多环境配置、代码规范校验、单元测试、初始化脚本

## 六、14天每日2小时开发计划（最终定稿·零漏洞·可商用）

### Day1｜项目架构打底：UV环境搭建 \+ 基础工程初始化

**核心目标**：搭建标准化、无漏洞的项目骨架，完成UV工程化环境，服务可正常启动

- 创建完整终版目录结构，补齐所有缺失文件夹与空文件

- 执行UV全套初始化命令，锁定Python版本与依赖

- 编写 config/settings\.py 多环境配置、读取\.env环境变量

- 编写 core/db\.py 数据库引擎、会话、依赖注入（杜绝全局Session漏洞）

- 编写 init\_app\.py、main\.py 标准化应用启动入口

- 编写 \.gitignore、log\_config\.py 基础工程配置

- uv run main\.py 测试服务正常启动，无报错

### Day2｜数据库架构：Alembic迁移 \+ 完整商用数据表建模

**核心目标**：补齐所有缺失数据表、关联关系、状态字段，打通数据库版本管理

- 初始化 scripts/alembic 迁移目录，修正配置关联项目Base

- 编写全套ORM模型：用户表、知识库表、文档表、对话记录表

- 完善表关联：用户\-知识库、知识库\-文档、对话\-用户\-知识库

- 新增状态字段：文档（待解析/成功/失败）、知识库（正常/禁用）

- uv run 执行迁移脚本，自动创建完整数据表

- 编写通用CRUD基础模板，规范数据库操作格式

### Day3｜工程规范固化：统一响应 \+ 全局异常 \+ 中间件 \+ 全局依赖

**核心目标**：彻底统一项目规范，解决新手代码杂乱、异常无兜底问题

- 编写 common/response\.py 标准化成功/失败返回格式

- 编写 core/exceptions\.py 自定义业务异常 \+ 全局异常捕获

- 编写 common/middleware\.py 跨域、请求日志、接口耗时统计

- 编写 common/dependencies\.py 全局参数清洗、基础依赖

- 编写 core/constants\.py 全局常量配置

- 统一注册所有中间件、异常处理器，全局生效

### Day4｜LangChain底层封装①：Embedding \+ Chroma向量库（单例无漏洞）（已完成）

**核心目标**：搭建无状态、全局唯一、可复用的向量底层能力

**完成状态**：已完成嵌入模型单例、Chroma 持久化向量库、基础增删查能力、异常恢复逻辑与本地功能验证

- [x] 编写 core/langchain/embedding\.py 全局嵌入模型单例

- [x] 编写 core/langchain/chroma\_store\.py 持久化向量库，封装增删查基础能力

- [x] 补齐向量库异常兜底、损坏自动恢复逻辑

- [x] 本地测试：文本入库、向量检索、向量删除功能正常

### Day5｜LangChain底层封装②：LLM \+ 检索器 \+ 工具能力补齐

**核心目标**：完成大模型、检索器底层封装，补齐文档处理工具链

- 编写 core/langchain/llm\.py Ollama全局单例，新增超时、重试机制

- 编写 core/langchain/retriever\.py 向量检索器，支持知识库隔离检索

- 完善 utils/file\_parser\.py 支持PDF/TXT解析，新增文件损坏、空文件兜底

- 编写 utils/hash\_utils\.py 文件MD5去重工具，杜绝重复文档入库

- 编写 utils/text\_utils\.py 文本清洗、Token截断工具，解决上下文溢出问题

### Day6｜文档管理模块全流程开发（分层规范\+去重\+状态管控）

**核心目标**：实现商用级文档上传、解析、切片、入库、去重、状态管理全链路

- 严格按顺序开发：schema → crud → service → controller

- 定义文档模块请求/响应模型、状态枚举

- CRUD实现文档元数据增删改查、状态更新

- Service层组装业务：文件校验→MD5去重→文本解析→LangChain智能切片→向量入库→数据库存元数据

- 新增安全校验：文件格式白名单、文件大小限制

- Controller层极简路由，仅接收参数、调用业务、返回结果

- 测试：重复文档自动拦截、异常文件兜底、正常文档入库成功

### Day7｜标准RAG问答链封装（企业级Prompt\+容错）

**核心目标**：搭建稳定、精准、可扩展的LangChain标准RAG核心链路

- 编写 core/langchain/rag\_chain\.py 统一RAG问答链

- 自定义专业系统Prompt，适配知识库问答场景

- 组装标准化链路：知识库隔离检索→上下文拼接→Token截断→LLM生成

- 新增无检索结果兜底回答、LLM调用异常捕获

- 完善RAG对话CRUD，保存用户、知识库、问答内容关联数据

### Day8｜RAG问答业务接口落地（完整闭环）

**核心目标**：实现上传文档→专属知识库检索→智能问答→记录持久化完整闭环

- 完善 rag/schema\.py 问答请求、响应结构化定义

- 优化 rag/service\.py 仅调用底层封装能力，无硬编码逻辑

- 编写 rag/controller\.py 极简问答接口，依赖注入数据库会话

- 测试核心能力：知识库隔离问答、关联文档溯源、对话记录入库

- 修复链路漏洞：空提问拦截、超长上下文截断、检索失败兜底

### Day9｜全局异常兜底 \+ 接口标准化 \+ BUG全修复

**核心目标**：消灭所有隐性BUG，项目达到稳定可用状态

- 统一所有接口返回格式，对齐公共响应规范

- 补全所有边界异常：空文件、超大文件、LLM超时、向量库异常

- 新增数据库事务回滚，避免数据不一致

- 全接口自测，保证所有正常/异常场景均可正常响应

### Day10｜RAG精度优化：参数调优 \+ Prompt升级 \+ 检索优化

**核心目标**：提升问答准确度、专业性、适配性

- 优化切片大小、重叠度、检索TopK参数，适配知识库场景

- 升级系统Prompt，强化知识库专属问答、拒绝无关问题

- 优化检索逻辑，提升关联文档匹配精度

- 对比优化前后问答效果，固化最优参数

### Day11｜LangChain流式问答开发（商用打字机效果）

**核心目标**：提升前端交互体验，实现流式实时问答

- 在core/langchain封装流式RAG问答链，复用底层Prompt与检索逻辑

- 适配FastAPI SSE流式响应规范

- 解决流式场景下对话记录异步入库、异常兜底问题

- 测试流式输出稳定、无卡顿、无乱码

### Day12｜多轮对话记忆 \+ 用户权限体系落地

**核心目标**：实现上下文连续问答、用户知识库隔离、基础权限管控

- 接入LangChain对话记忆组件，实现多轮上下文关联问答

- 优化记忆窗口，防止上下文过载

- 完善用户模块分层代码，实现注册、登录基础能力

- 封装JWT鉴权全局依赖，实现接口权限管控、用户知识库隔离

- 测试：不同用户数据完全隔离、多轮对话上下文连贯

### Day13｜工程化完善：日志 \+ 多环境配置 \+ 初始化脚本

**核心目标**：项目具备生产部署条件，规范化运维

- 完善log\_config\.py，实现日志分级、自动分割、持久化存储

- 拆分dev/prod多环境配置，通过\.env区分环境参数

- 编写scripts/init\_db\.py 基础数据初始化脚本

- 优化UV开发/生产依赖隔离，清理冗余配置

- 新增代码规范校验，统一项目编码风格

### Day14｜全流程验收 \+ 架构梳理 \+ 项目定稿可部署

**核心目标**：项目终验，达到商用、可部署、可二次开发标准

- 全链路完整测试：用户登录→知识库创建→文档上传→智能问答→多轮对话→流式输出→记录持久化

- 排查并修复所有残留BUG、兼容性问题

- 梳理项目架构文档、分层调用逻辑、核心能力说明

- 整理部署规范、开发规范、UV运维命令、迁移命令

- 项目最终定稿，支持本地运行、服务器私有化部署、二次迭代开发

## 七、最终项目商用能力（14天完成后完整能力）

- ✅ 企业级严格分层架构，零耦合、可扩展、易维护

- ✅ UV现代化工程化依赖管理，版本锁定、环境统一

- ✅ Alembic数据库版本可控，支持升级、回滚、多环境同步

- ✅ 多用户、多知识库数据隔离，完全商用权限逻辑

- ✅ PDF/TXT文档解析、智能切片、MD5去重、状态管控

- ✅ Chroma向量持久化、精准检索、向量删除、异常恢复

- ✅ LangChain标准RAG问答、多轮对话记忆、上下文截断

- ✅ 普通问答\+流式打字机双模式输出

- ✅ 完整异常兜底、事务回滚、超时重试、安全校验

- ✅ 统一接口响应、标准化日志、全局异常、跨域处理

- ✅ 可直接私有化部署、适配毕设、项目实战、商用二次开发

## 八、项目运维常用UV\+Alembic终版命令

- **安装新依赖**：uv add 包名

- **卸载依赖**：uv remove 包名

- **同步环境（换设备/拉代码）**：uv sync

- **清空缓存**：uv cache clean

- **启动项目**：uv run main\.py

- **生成迁移脚本**：uv run alembic revision \-\-autogenerate \-m "备注"

- **执行数据库升级**：uv run alembic upgrade head

- **代码规范校验**：uv run ruff check

> （注：部分内容可能由 AI 生成）
