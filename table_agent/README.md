# 表格解析工作流智能体 (`table_agent`)

本目录包含了针对 AFAC2026 比赛 Track 2 进行表格解析工作流的模块化、生产级实现。代码遵循 Agent 开发规范，采用关注点分离（Separation of Concerns）的设计原则进行归类与重构。

---

## 一、 模块化 Agent 目录结构划分

按照成熟的 Agent 架构，代码划分为以下结构：

```
Code/table_agent/
├── README.md               # Agent 运行与架构说明文档（本文件）
├── config.py               # 集中式环境参数与运行阈值配置
├── client.py               # 线程安全且具备速率限制的 API 调用客户端环境
├── orchestrator.py         # 流程控制中枢（Workflow Agent 决策层）
└── tools/                  # 承载具体原子能力的 Agent 工具箱
    ├── __init__.py
    ├── layout.py           # 版面分析工具（栏目/表格垂直区域切分）
    ├── slicer.py           # 切片裁剪工具（横向切片/大宽表纵向二分）
    ├── merger.py           # 拼接重构工具（结构行对齐/去重与列融合）
    └── validator.py        # 格式校验工具（反 VLM 列死循环截断/行去重）
```

---

## 二、 各组件角色与 Agent 职责说明

1. **Agent 决策核心 (`orchestrator.py`)**
   - 扮演“规划与协调者”角色。驱动整个解析生命周期：接收输入图像 -> 触发版面探测 -> 切割分块 -> 调度并发调用 -> 协调合并对齐 -> 输出最终 CSV，并维护状态账本（Ledger）实现异常中断续跑。
2. **辅助配置器 (`config.py`)**
   - 集中存储 Workflow 中的物理参数（切片高度、重叠比例）与反幻觉阈值（列数上限 110、连续相似行去重阈值 0.95）。
3. **环境感知客户端 (`client.py`)**
   - 负责与外部环境 `FinixDoc-VL` API 通信，内部封装了多账号轮询和强制每个账号至少间隔 6s 请求的速率锁保护。
4. **Agent 工具集 (`tools/`)**
   - **`layout.py`**：感知图像列排版和纵向表格间距（多表物理切分）。
   - **`slicer.py`**：执行投影分析并确定最佳水平切割位置。
   - **`merger.py`**：核心对齐拼接逻辑。
   - **`validator.py`**：负责过滤幻觉和修补破损 HTML（包含防死循环去重与溢出截断）。

---

## 三、 项目执行命令

在工作区根目录下，您可以使用以下命令启动解析 Agent：

* **仅测试评测 9 张典型图片（利用缓存加速验证）**：
  ```bash
  python Code/table_agent/orchestrator.py --typical
  ```
* **全量处理并解析全量数据集**：
  ```bash
  python Code/table_agent/orchestrator.py
  ```
