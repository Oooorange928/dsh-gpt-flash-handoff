# GPT / Flash 协作模式 · 可分享 DSH Skill

GitHub 仓库 `dsh-gpt-flash-handoff` 提供的 DSH Skill ID 是 `gpt-flash-handoff`；仓库名与安装后调用名不同属于有意设计，请勿重命名内层 Skill。

> GPT plans and accepts; DeepSeek V4.1 Flash executes. A portable prompt-layer collaboration Skill for DeepSeek Harness.

版本：1.0.0 · 授权：MIT

**GPT 判断复杂度并规划 → DeepSeek V4.1 Flash 执行 → GPT 独立验收 → 向用户交接。**

这是自包含的提示层 Skill 包，不是 DSH 内核补丁、模型代理服务或引擎级强制调度器。简单任务由 GPT 直接完成，非 GPT 主模型及执行子代理不改变默认行为。安装不会替换主模型，也不会改变全局默认子代理路由。

## 1. 使用前提

- DSH 已提供 `skill`、`list_subagent_models`、`subagent` 工具；返工优先使用 `send_message`。
- 主会话选择 GPT 系列模型。
- 收件人自行在 DSH 设置中配置并授权 **DeepSeek V4.1 Flash**；不同机器的 provider/model id 可以不同。Skill 要求现场确认并显式传入，不写死某个人的渠道。
- 自动安装器使用 **Python 3.12 或更新版本**，仅标准库、离线运行，不需要 pip 或管理员权限（目标目录的正常写权限仍需具备）。Python 3.12 支持 Windows junction 检查。没有 Python 时可按第 5 节手动安装。
- 只在用户许可及工具权限允许的情况下派发；不会开启 Agent Teams，也不会绕过写入/部署审批。

**不要把 API Key、Token、密码发给模型。** 本包不包含认证信息，不提供模型额度，安装器不读取模型配置或私密数据库配置。收件人只需在自己的 DSH 设置里配置渠道。

## 2. 包内结构

```text
gpt-flash-handoff/
├─ README.md                     使用、安装、关闭和卸载
├─ LICENSE                       MIT 授权
├─ install.py                    离线安装器
├─ test_install.py               隔离目录回归测试
├─ build_package.py              从白名单生成清单和分享 ZIP
├─ manifest.json                 Skill 与全局规则的 SHA-256 清单
├─ VALIDATION.md                 GPT 独立验收记录与验证边界
├─ global-mode.md                可选的全局触发规则
└─ gpt-flash-handoff/
   ├─ SKILL.md                   协作流程
   └─ references/
      ├─ task-contract.md        自包含任务契约与三类检验例
      └─ acceptance-handoff.md   独立验收、返工与用户交接模板
```

分享 ZIP 只包含以上文件，不包含 ZIP 自身。公开仓库根目录另外附带 `gpt-flash-handoff-1.0.0.zip`，它是上述 11 个文件的 **v1.0.0 冻结快照**，方便直接下载；修改源码后必须重新运行打包与验收，并用新产物更新仓库中的版本快照。仓库不会打包发送者的全局记忆、模型渠道、账号、密钥、聊天记录、备份、运行日志或第三方 DSH 源码。

## 3. 推荐：按需安装

解压，终端进入含 `install.py` 的包根目录。先检查 `install.py` 和 `manifest.json`，再运行：

```sh
python install.py --dry-run
python install.py
```

安装到 `<DSH_HOME>/skills/gpt-flash-handoff/`。默认 home 依次为 `--home`、环境变量 `DSH_HOME`、当前用户的 `~/.dsh`。安装器首先打印实际 home 和 Skill 目标；请检查它们确实属于你正在使用的 DSH。

如果默认 home 不是当前实例的目录，用你自己的路径指定：

```sh
python install.py --home "/path/to/your-dsh-home" --dry-run
python install.py --home "/path/to/your-dsh-home"
```

Windows 的 `--home` 同样接受你自己的完整目录，含空格时加引号；上述 `/path/to/...` 是占位符，请替换，不是可直接使用的路径。

默认按需安装**不读取、修改用户级 `AGENTS.md` 内容**。相同版本重复安装不产生重复文件；已有 Skill 内容不一致或多出文件时拒绝覆盖，不擅自删除用户修改。

### 让 DSH 识别并使用

安装后，在 DSH 技能目录中确认出现 `gpt-flash-handoff`。若当前会话目录未更新，重新载入技能目录或新建会话；必要时按本机版本的方式重启 DSH。无需为这个包启动额外 Web 服务。

选择 GPT 主模型，把下面这段发给它：

> 请使用 gpt-flash-handoff 处理接下来的任务。先判断复杂度；复杂任务先写任务契约和验收标准，现场确认 DeepSeek V4.1 Flash 路由，派发执行后由你独立验收再交接。

安装器不会自动创建子代理，也不会仅凭安装就保证所有任务自动触发。若希望 GPT 主模型持续遵守这一模式，可选择下一节的全局模式。

## 4. 可选：全局触发模式

此模式在**该 DSH 用户 home** 的 `AGENTS.md` 追加一段带起止标记的规则，用于所有加载此文件的工作区和 GPT 主模型。它不是对所有独立 DSH 安装/其他操作系统用户的自动广播；非 GPT 主模型与执行子代理不改变行为。不同 GPT 版本或渠道别名以实际模型身份为准。

先选择自己的备份目录，必须位于包目录与已安装 Skill 目录之外。下例从解压包根目录执行，用上一级的独立备份目录：

```sh
python install.py --global --backup-dir "../dsh-skill-backups" --dry-run
python install.py --global --backup-dir "../dsh-skill-backups"
```

如果用了 `--home`，后续开启、关闭、卸载也都指定同一个 `--home`。

- 已有 `AGENTS.md` 被修改前，安装器将原始字节备份为独立 `.bak`；保留原有正文、UTF-8 BOM、原有换行。
- 仅接受 UTF-8（含 BOM），不猜测 GBK/UTF-16；编码不兼容会在写入前报错。
- 已有托管规则被编辑、出现重复/不完整标记时，拒绝自动替换或删除，需用户手动复核。
- 相同规则重复开启不重复追加。关闭只移除本包的原样标记块，不覆盖其他用户规则。
- 不保证跨进程事务：操作期间请不要同时编辑目标规则或 Skill。磁盘、权限或进程中断导致部分写入时，先检查目标和备份，不要盲目重跑。
- 安装器拒绝目标/祖先 symlink 与 Windows junction；如使用链接化配置目录，先决定真实位置及权限，不要强行绕过安全检查。

全局模式仍是**提示层约定**，系统/开发者指令、当前用户限制和工具审批优先，不是不可绕过的硬调度。

### 只关闭全局模式，保留 Skill

```sh
python install.py --disable-global --backup-dir "../dsh-skill-backups" --dry-run
python install.py --disable-global --backup-dir "../dsh-skill-backups"
```

### 完整卸载

先查看预演打印的 `SKILL_TARGET`，确认是你打算删除的那个 Skill，再执行：

```sh
python install.py --uninstall --yes --backup-dir "../dsh-skill-backups" --dry-run
python install.py --uninstall --yes --backup-dir "../dsh-skill-backups"
```

卸载只删除**与当前包完全相同**的已安装 Skill，并移除本包原样规则。不删除其他技能、不改模型设置。用户修改过的 Skill/规则会被保护性拒绝；需要自行审查后手动处理。备份不自动删除。若原先不存在 `AGENTS.md`，卸载后可能留下空文件；安装器不删除用户级规则文件本身。

## 5. 没有 Python：手动安装

1. 找到当前 DSH 的实际 `DSH_HOME`，将内层整个 `gpt-flash-handoff/` 文件夹复制到 `<DSH_HOME>/skills/`，不要覆盖同名用户修改。
2. 确认最终布局为 `<DSH_HOME>/skills/gpt-flash-handoff/SKILL.md`，两个 `references/` 文件与其一起复制。
3. 刷新技能目录/新建会话，选择 GPT，按第 3 节显式调用技能。
4. 若需全局模式，**先在自己选择的包外目录备份**已有 `AGENTS.md`，再将 `global-mode.md` 全部追加到其末尾；不要用本包替换整份全局文件，不重复追加。
5. 手动卸载前先检查目标：只删除内层 Skill；全局模式仅删除本包的起止标记块，不动其余正文与备份。

## 6. 模型路由与返工

Skill 要求首次派发及配置改变/调用失败后重新查 `list_subagent_models`。目录是建议性的：未列出 model id 不等于 API 不可用；身份无法确认时先请用户确认，不猜 id、不静默换模型。明确认证/权限/调用失败时如实报告。

支持 `high` 才使用它；否则使用已确认支持的档位，或省略 effort 走路由默认。provider/model 始终显式传入，防止执行子代理无意继承 GPT。

返工先尝试 `send_message` 给原子代理。如果 DSH 明确不能恢复该目标，记录实际错误，再确认 Flash 路由后创建替代 Flash 子代理，发送原契约及失败证据；可写范围和验收标准不降低。不会假装原子代理还在工作。

## 7. 离线自测与重新打包

在包根目录运行：

```sh
python -B test_install.py
```

测试会在包根目录的**父目录**创建并清理隔离的临时目录，因此从 GitHub 克隆后运行测试时，该父目录也必须可写。测试使用假的 DSH home，不读真实用户全局规则；覆盖默认安装、幂等、全局启用/关闭、精确备份、卸载、保护性拒绝和预演。测试脚本不调用模型，不产生 API 费用。

若修改包内模板，先检查内容，再运行以下命令重新生成清单、测试和分享 ZIP：

```sh
python -B build_package.py --manifest-only
python -B test_install.py
python -B build_package.py
```

生成的权威 ZIP 位于包根目录的上一级；这是打包器的固定输出位置。`build_package.py` 按固定白名单打包，不递归打包整个工作区，不会包含临时验证文件或备份。若维护公开仓库，还需在完整复验后把该新 ZIP 复制为仓库根目录的对应版本快照；不要让旧快照与源码并存。每次改模板都会改变 payload 校验值，安装器不自动覆盖旧版本或用户改动，请先审查并手动迁移。

SHA-256 清单用于检测意外损坏，**不是发布者身份签名**。不要因为校验通过就跳过源码审查。

## 8. 实际使用的边界

此包不能保证不同 DSH 版本的工具、目录发现及返回字段完全一致；收件人应在自己的 DSH 上确认技能加载与 Flash 渠道授权。GPT 必须自己读真产物、复跑适用验证，无法执行的项明确列为未验证，不能引用 Flash 自报成功替代验收。任务契约只传完成该任务必需且已授权的信息，不转发个人全局记忆或无关秘密。

本包可离线转发、修改和复用，保留 `LICENSE` 即可；无收费、登录或在线注册安装步骤。
