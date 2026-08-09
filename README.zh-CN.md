# LoopLedger

**完全离线地从 MBOX、Maildir 或 EML 中找出“我已经发出请求、对方仍未回复”的邮件开放循环。**

[虚构数据在线报告](https://kanadek.github.io/loopledger/) ·
[English](README.md) · [算法说明](docs/algorithm.md) · [故障修复](docs/repair.md)

LoopLedger 不是套着邮件外观的空白仪表盘。它会真实解析邮件导出、重建线程、判断最后一封
有效邮件的方向、解释中英文请求信号，并输出可核验的 HTML、JSON、CSV、ICS 和 SHA-256
清单。运行时只使用 Python 标准库，不登录邮箱、不调用云端、不发送邮件。

## 两分钟验收

```bash
git clone https://github.com/KanadeK/loopledger.git
cd loopledger
python -m pip install -e .

loopledger sample examples/demo.mbox --force
loopledger doctor examples/demo.mbox
loopledger scan examples/demo.mbox --as-of 2026-02-01 --output demo-output
loopledger verify demo-output/manifest.json
```

固定的虚构样例会得到：9 封邮件、6 个线程、3 个逾期待回复事项。修改日期、正文或回复后，
结果会随真实输入改变；篡改任何报告文件后，`verify` 会以退出码 `5` 失败。

## 功能

- 读取 MBOX、Maildir、单个 EML 或递归 EML 目录；
- 优先使用 `Message-ID`、`In-Reply-To`、`References` 重建线程；
- 识别问题、明确请求、审批/评审、截止时间和跟进措辞，并保留原因码；
- 支持常见英文与中文请求表达；
- 排除群发列表、退信、收据、`no-reply` 和自动通知；
- 使用稳定 ID 保存忽略、已解决和稍后提醒状态，不修改原邮箱；
- 生成无 JavaScript 的独立 HTML、JSON、CSV、日历提醒和完整性清单；
- 提供 `--strict` 与 `--fail-on-overdue`，适合定时任务和 CI。

## 扫描自己的导出

从 [Google Takeout](https://takeout.google.com/) 导出 Mail 并在本地解压：

```bash
loopledger doctor "Takeout/Mail/All mail Including Spam and Trash.mbox"
loopledger scan "Takeout/Mail/All mail Including Spam and Trash.mbox" --output follow-up-report
```

Gmail 的 `Sent` 标签通常可以推断你的地址。对于其他导出，请显式传入本人地址和别名：

```bash
loopledger scan mailbox.mbox \
  --identity you@example.com \
  --identity alias@example.org \
  --output follow-up-report
```

先运行只读的 `doctor`，它会报告可用邮件数、身份、来源类型、字节数、完整 SHA-256 和被
跳过的邮件。

## 输出

| 文件 | 用途 |
| --- | --- |
| `index.html` | 响应式本地审阅报告，所有邮件文本均转义，无 JavaScript |
| `report.json` | 带版本的证据数据，适合自动化和二次处理 |
| `report.csv` | 每个开放循环一行，可导入表格/任务系统 |
| `follow-ups.ics` | 可导入日历的全天跟进提醒 |
| `manifest.json` | 所有输出的字节数、SHA-256 以及源文件指纹 |

报告会包含主题、地址和最后一封邮件的短摘录，即使处理过程不联网，也应将输出视为敏感
数据。参见 [隐私与安全边界](docs/privacy.md)。

## 判定规则

每个线程依次执行：排除自动邮件 → 判断收发方向 → 要求最后一封有效邮件是本人发出 →
只分析未引用的当前正文 → 默认等待 3 天 → 7 天后标记逾期 → 应用忽略/解决/稍后提醒状态。

默认请求阈值为 `3`。如果更重视召回率，可使用 `--include-all-outbound`，此时所有“最后
一封由我发出”的线程都会进入报告，弱匹配会明确标记为 `last_message_is_outbound`。

完整算法、权衡和已知限制见 [docs/algorithm.md](docs/algorithm.md)。

## 退出码与修复

| 退出码 | 含义 |
| ---: | --- |
| `0` | 成功 |
| `2` | 输入、身份、时间或状态文件错误 |
| `3` | 严格模式发现被跳过的邮件 |
| `4` | 策略模式发现逾期事项，但报告仍已写出 |
| `5` | 输出文件缺失或哈希不匹配 |

每种失败的定位和恢复命令均写在 [docs/repair.md](docs/repair.md)。完整发布前门禁为：

```bash
python -m pip install -e ".[dev]"
python scripts/verify.py
python scripts/package_release.py
```

门禁覆盖 Ruff、严格 MyPy、83 项测试、分支覆盖率下限、构建、包元数据、干净虚拟环境
安装、真实样例、篡改检测和秘密扫描。详细验收矩阵见
[docs/acceptance.md](docs/acceptance.md)。

## 明确不做什么

LoopLedger 不是邮件客户端、CRM、AI 回信生成器、IMAP 守护进程或 Gmail 插件。它不会
登录、打标签、写草稿或发送提醒。对方只回复“我会处理”时，当前请求会视为已回复；跟踪
对方承诺是否兑现属于另一个问题。损坏的邮件头和含蓄表达也可能产生误判，因此报告始终
保留判定证据供人工复核。

项目的 [调研记录](docs/research.md) 公开了选择这个边界的社区证据、GitHub 竞品和检索
限制，不以无法证明的“全球绝无同类”作为宣传。

欢迎阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 参与改进。请勿在公开 Issue 上传真实邮箱或
私人报告。本项目采用 [MIT License](LICENSE)。
