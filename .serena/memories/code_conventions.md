# FlowClip 代码规范和约定

## Python 后端规范

### 代码风格
- **Python 版本**: Python 3.8+
- **格式化**: 遵循 PEP 8
- **导入顺序**: 标准库 -> 第三方库 -> 本地模块
- **字符串**: 使用 f-string 进行字符串格式化

### 类型提示
- **强制要求**: 所有函数参数和返回值必须有类型提示
- **异步函数**: 使用 `async def` 和 `Awaitable[T]`
- **数据库模型**: 使用 SQLAlchemy 2.0 异步语法

### 数据库约定
- **模型定义**: 使用 SQLAlchemy 2.0 declarative base
- **异步查询**: 使用 `select()` 构造器和 `async_session.execute()`
- **连接管理**: 使用 `async with` 上下文管理器
- **迁移**: Alembic 版本控制

### API 设计
- **路径**: `/api/v1/` 前缀
- **HTTP 状态码**: 标准 REST 状态码
- **请求验证**: Pydantic 模型验证
- **响应格式**: 统一 JSON 响应结构
- **错误处理**: 统一异常处理器

### 文件命名
- **模块**: 小写字母 + 下划线 (snake_case)
- **类名**: 大驼峰命名 (PascalCase)
- **函数/变量**: 小写字母 + 下划线
- **常量**: 大写字母 + 下划线

## 前端规范

### TypeScript
- **严格模式**: 启用 strict 类型检查
- **接口定义**: 使用 interface 定义数据结构
- **枚举**: 使用 enum 替代魔法字符串
- **泛型**: 适当使用泛型提高代码复用性

### React 组件
- **函数组件**: 优先使用函数组件 + Hooks
- **组件命名**: 大驼峰命名 (PascalCase)
- **Props 类型**: 必须定义 TypeScript 接口
- **状态管理**: useState/useReducer for local state

### 文件结构
```
src/
├── components/     # 可复用组件
├── pages/         # 页面组件
├── services/      # API 调用服务
├── store/         # Zustand 状态管理
├── types/         # TypeScript 类型定义
├── hooks/         # 自定义 Hooks
└── utils/         # 工具函数
```

### CSS 和样式
- **Tailwind CSS**: 优先使用 Tailwind 工具类
- **组件样式**: 避免内联样式，使用 className
- **响应式**: 移动优先的响应式设计
- **主题**: 统一的颜色和间距系统

## 异步处理规范

### Celery 任务
- **任务定义**: 使用 `@celery_app.task` 装饰器
- **错误处理**: 完整的异常捕获和日志记录
- **任务链**: 复杂工作流使用 task.chain 或 group
- **状态跟踪**: 更新 ProcessingTask 状态

### WebSocket 通信
- **连接管理**: 使用 WebSocketManager 类
- **消息格式**: 统一的消息结构
- **错误处理**: 连接断开重连机制
- **权限验证**: Token 验证和用户隔离

## 测试规范

### 后端测试
- **测试框架**: pytest + pytest-asyncio
- **测试文件**: `test_*.py` 命名约定
- **测试覆盖率**: 目标 80% 以上覆盖率
- **Mock**: 使用 unittest.mock 进行依赖模拟

### 测试分类
- **单元测试**: 测试单个函数/类
- **集成测试**: 测试 API 端点
- **端到端测试**: 测试完整工作流
- **性能测试**: 测试负载和并发

## 数据库设计约定

### 表命名
- **小写复数**: 使用复数形式 (users, videos, projects)
- **关联表**: `table1_table2` 格式
- **时间戳**: created_at, updated_at 字段

### 字段约定
- **主键**: UUID v4 或自增整数
- **外键**: `table_name_id` 格式
- **软删除**: deleted_at 字段
- **JSON 字段**: 使用 JSON 类型存储复杂数据

### 索引策略
- **外键索引**: 所有外键字段建立索引
- **查询索引**: 根据常用查询条件建立
- **复合索引**: 多字段联合查询使用复合索引

## 安全规范

### 输入验证
- **Pydantic 模型**: 严格的输入验证
- **SQL 注入防护**: 使用参数化查询
- **XSS 防护**: HTML 内容清理
- **CSRF 防护**: 使用 SameSite cookies

### 认证授权
- **JWT Token**: 短期访问 Token + 长期刷新 Token
- **权限控制**: 基于角色的访问控制 (RBAC)
- **API 限流**: 防止 API 滥用
- **密码安全**: bcrypt 加密存储