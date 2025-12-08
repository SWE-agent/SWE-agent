# 环境共享机制 - 快速参考

## 关键概念

Star Topology的核心是**环境共享**：多个specialized agents共享同一个SWEEnv实例，避免重复初始化。

## agents.py 的关键修改

### 1. 添加 `role` 字段到 `DefaultAgentConfig`

```python
class DefaultAgentConfig(BaseModel):
    ...
    role: str | None = None
    """Agent role for multi-agent systems."""
```

### 2. 添加 `injected_env` 参数到 `__init__`

```python
def __init__(
    self,
    *,
    ...
    injected_env: SWEEnv | None = None,
):
    # Environment injection support
    self._env_is_injected = injected_env is not None
    if injected_env is not None:
        self._env = injected_env
    else:
        self._env = None
```

### 3. 修改 `from_config` 支持环境注入

```python
@classmethod
def from_config(cls, config: DefaultAgentConfig, injected_env: SWEEnv | None = None) -> Self:
    ...
    agent_name = config.role if config.role else config.name
    return cls(
        ...
        name=agent_name,
        injected_env=injected_env,
    )
```

### 4. 修改 `setup` 方法处理注入的环境

```python
def setup(
    self,
    env: SWEEnv | None = None,  # 改为可选
    problem_statement: ProblemStatement | ProblemStatementConfig | None = None,
    output_dir: Path = Path("."),
) -> None:
    # 检查是否使用注入的环境
    if self._env_is_injected:
        self.logger.info(f"Agent '{self.name}': using injected environment (shared)")
    else:
        if env is None:
            raise ValueError("Environment must be provided")
        self._env = env

    # 只有非注入环境才需要初始化
    if not self._env_is_injected:
        self.tools.install(self._env)
        self._env.set_env_variables(...)
    else:
        # Sub-agent: 跳过环境初始化
        self.logger.info(f"Sub-agent '{self.name}': skipping environment initialization")
```

## Coordinator如何使用

### 1. 创建共享环境

```python
env = SWEEnv.from_config(env_config)
```

### 2. 初始化环境（由Coordinator负责）

```python
def _initialize_shared_environment(self):
    # 启动环境
    self.env.start()

    # 安装工具（只做一次）
    tool_handler = ToolHandler(self.rca_config.tools)
    tool_handler.install(self.env)
```

### 3. 创建Sub-agents并注入环境

```python
# RCA Agent
rca_agent = DefaultAgent.from_config(
    self.rca_config,
    injected_env=self.env  # 注入共享环境
)

# Patch Agent
patch_agent = DefaultAgent.from_config(
    self.patch_config,
    injected_env=self.env  # 使用相同的环境
)
```

### 4. 运行agents

```python
# RCA Agent运行
result = rca_agent.run(
    env=None,  # 不需要传env，使用injected_env
    problem_statement=problem_statement,
    output_dir=output_dir,
)

# Patch Agent运行（共享相同环境）
result = patch_agent.run(
    env=None,  # 同样使用injected_env
    problem_statement=augmented_problem,
    output_dir=output_dir,
)
```

## 工作流程

```
1. Coordinator创建SWEEnv
   ↓
2. Coordinator启动环境并安装工具
   ↓
3. 创建RCA Agent (injected_env=env)
   ↓
4. RCA Agent.setup() → 检测到injected_env → 跳过初始化
   ↓
5. RCA Agent分析问题
   ↓
6. Coordinator提取RCA findings
   ↓
7. 创建Patch Agent (injected_env=env) ← 相同环境
   ↓
8. Patch Agent.setup() → 检测到injected_env → 跳过初始化
   ↓
9. Patch Agent使用RCA的成果（如reproduce_issue.py）
   ↓
10. Patch Agent实现修复
```

## 关键点

### ✅ 为什么需要 `_env_is_injected` 标志？

因为需要区分两种情况：
1. **普通Agent**: 需要初始化环境、安装工具
2. **Sub-agent**: 环境已就绪，跳过初始化

### ✅ 为什么 `setup(env=None)` 可以工作？

```python
if self._env_is_injected:
    # 使用__init__时注入的环境
    assert self._env is not None
else:
    # 使用setup参数提供的环境
    self._env = env
```

### ✅ 环境共享的好处

1. **状态持久化**: RCA创建的文件（如reproduce_issue.py）对Patch Agent可见
2. **避免重复初始化**: 不需要多次克隆仓库、安装工具
3. **资源效率**: 单个Docker容器，减少开销
4. **原子性**: 所有操作在同一环境中，保证一致性

## 故障排查

### 问题: "Deployment not started"

**原因**: 环境没有启动
**解决**: Coordinator必须调用 `env.start()` 和 `tool_handler.install(env)`

### 问题: Sub-agent重新安装工具

**原因**: `_env_is_injected` 标志未正确设置
**解决**: 确保通过 `injected_env` 参数传递环境

### 问题: Agent看不到前一个Agent的文件

**原因**: 使用了不同的环境实例
**解决**: 确保所有agents使用相同的 `injected_env` 参数

## 测试验证

```python
# 检查环境是否共享
coordinator = RepairCoordinator(env, rca_config, patch_config)

# 两个agent应该引用相同的环境
assert coordinator.env is coordinator._env
rca_agent = DefaultAgent.from_config(rca_config, injected_env=coordinator.env)
assert rca_agent._env is coordinator.env  # 相同实例
```

---
参考: star_topology_guide.md, FILE_RECOVERY_REPORT.md
