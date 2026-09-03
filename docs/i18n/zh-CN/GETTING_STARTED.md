# ContractGraph-QA 互操作：五分钟入门

[English](../en/GETTING_STARTED.md) · 简体中文 · [हिन्दी](../hi/GETTING_STARTED.md) · [Español](../es/GETTING_STARTED.md) · [العربية](../ar/GETTING_STARTED.md)

ContractGraph-QA、LiminalQA 和 PythiaLabs 组成一个面向有状态、高风险
Agent 工作流的“证据优先”安全栈。每个项目保留自己的判定权限；适配器只交换
严格的 JSON 证据，不会把报告变成执行许可。

## 三个项目分别做什么

| 项目 | 职责 | 不代表什么 |
|---|---|---|
| ContractGraph-QA | 有界状态/动作搜索、精确对象证据、重放输入 | 穷尽性正确证明或动作授权 |
| LiminalQA | 双时态 QA 上下文，以及非权威的重放/验证债务候选 | 已验证的 CGQA finding 或 LTP 连续性结论 |
| PythiaLabs | 把外部证据作为建议上下文，执行新的确定性授权门 | 外部证据本身可以返回 `ALLOW` |

## 运行固定版本的契约

在 ContractGraph-QA 仓库中运行：

```bash
python -m pip install .
cgqa liminalqa-conformance > report.json
```

通过的报告必须包含全部 14 个 golden 与 fail-closed 向量，并始终记录：

```json
{"status":"PASS","counts":{"total":14,"passed":14,"failed":0},"authority":{"classification":"conformance_evidence_only","mayAuthorizeAction":false}}
```

完整报告还会固定 suite SHA-256、两个生产者契约、每个 case 的 ID 和输入
摘要、`sideEffectExecuted=false` 以及声明边界。

## 在你的编程语言中验证

仓库提供 TypeScript/JavaScript、Go、Java/JVM 和 .NET 的轻量适配器。
它们验证原生 runner 的证据，刻意不重新实现 CGQA/LiminalQA 的判定逻辑。

```bash
node sdks/typescript/bin/cgqa-report-validate.js report.json

cd sdks/go && go run ./cmd/cgqa-report-validate ../../report.json

mvn -q -f sdks/java/pom.xml exec:java -Dexec.args=report.json

dotnet run --project sdks/dotnet/src/ContractGraphQA.Interop.Cli -- report.json
```

包管理器坐标和本地引用方式见 [SDK 发布指南](../../SDK_RELEASE.md)。Python
是 ContractGraph-QA 的参考 runner，Rust 是 LiminalQA 的原生 runner，Elixir
是 PythiaLabs 的原生 runner。

[SDK v0.1.0 已可从 GitHub 公开下载](https://github.com/safal207/ContractGraph-QA/releases/tag/interop-sdk-v0.1.0)，
Go 模块可通过
`go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0` 安装。`.tgz`、
JAR/POM 和 `.nupkg` 均为 release 资源；npm、Maven Central 和 nuget.org
的正式发布仍在等待配置。

## Fail-closed 边界

所有适配器都会拒绝重复 JSON 键、未知关键字段、任何 pin 漂移、缺失或重复
case、`UNSAFE_ACCEPTED`、`mayAuthorizeAction=true` 以及任何已执行副作用。
输入上限为 1 MiB；验证不会访问网络、执行候选、写数据库或操作目标系统。

有效报告只说明该实现通过了固定的合成向量。真实动作之前仍须针对当前证据
重新验证精确对象，并运行当前的 Pythia 或人工授权门。`PASS` 永远不是许可。

完整协议见 [ContractGraph-QA ↔ LiminalQA 互操作说明](../../LIMINALQA_INTEROP.md)。
