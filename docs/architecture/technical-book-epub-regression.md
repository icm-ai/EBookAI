# Technical-book PDF → EPUB end-to-end regression plan (post-M21)

> **Status: PROPOSED / DOC-ONLY / NOT GATED** · Linked to [Issue #4](https://github.com/icm-ai/EBookAI/issues/4). This document and the [candidate registry](../../benchmark/technical-books/candidates.json) define an evaluation plan; **they do not constitute reviewed gold, verified publication fidelity, enabled jobs, or permission to redistribute the books**. Current M21 reviewer assignments, campaign, ablation targets, governance policies, and CI gates remain unchanged.

## 1. 目标、范围与不可混淆的结论

目标是建立一种**来源绑定、可人工复核、可量化、可复现**的技术书端到端回归体系，从 `PDF → Parser → BookIR → Reconstruction → EPUB3 → Reader` 逐层定位内容损失，而不将“EPUB 文件可打开”误当成“原书完整无误”。

已有能力（本阶段复用，不另起炉灶）：
- [M12 Golden Corpus](golden-corpus.md)：合成 PDF → BookIR → EPUB 的确定性结构及文本断言、Publication QA、EPUBCheck、DOM/文本流指纹；**不能**以 DOM 一致宣称视觉一致。
- [M13 Real-world Corpus](real-world-parser-benchmark.md)：rights-cleared SHA-256 固定输入，PyMuPDF/MinerU/Marker 解析对比与无真值 proxy；当前 runner 是 **parser-level**。
- [M14–20 Gold/Review/Governance](gold-annotation-benchmark.md)：稀疏 `draft → reviewed`，来源 SHA 绑定，双 reviewer + consensus provenance、受控 baseline 与独立审批。
- [M21 Occam pilot](runtime-ablation-occam.md)：A/B/C/D 解析、路由、修复消融，需覆盖现有八种 difficulty buckets 且至少八页 reviewed gold；**本计划完全独立，不修改其证据地板或默认结论**。
- [BookIR EPUB compiler](../../backend/src/book/compiler/epub.py)：当前版本对 `FIGURE`/`TABLE`/`FORMULA` 尚缺独立完整的输出与 asset manifest；这是待测的输出能力缺口，而非一个已通过验证的方案。

严格区分四类结论：

| 层次 | 可以证明什么 | 不能据此推断 |
|---|---|---|
| ZIP/EPUBCheck/Publication QA | 包结构、XHTML/OPF/manifest/navigation 合规性 | 源文本、公式或图像完整 |
| Parser/BookIR proxy | 字符数、块数、页覆盖、SourceRef 覆盖与相对差异 | 真实准确率 |
| 人工 reviewed gold | **仅**标注页、已覆盖任务上的准确率 | 全书 100% 准确 |
| EPUB 阅读器截图与人工复核 | 指定阅读器/窗口/字号上的视觉与交互行为 | 其他设备必然相同 |

## 2. 候选语料及版本固定

候选信息在 `benchmark/technical-books/candidates.json`；它**不是** `benchmark/corpus/manifest.json`，不得交给现有 `book.benchmark.cli fetch/run` 直接执行。三份上传源 PDF 的 SHA-256 和物理页数已重新通过本地文件检验。

| Candidate ID | 文档 | 物理页数 | SHA-256（精确 PDF 字节） | 主要覆盖 |
|---|---|---:|---|---|
| `ai-infra-book-2026-09-14` | 李博杰《深入理解 AI Infra》v1.0, 2026-09-14 | 518 | `828ae3645c1c24803e505b5ccaacf9b416d1a0c8cb8a61b40cc082f4914ddd9c` | 中文技术段落、中英混排、公式、矢量图表、图注、多级目录 |
| `udl-prince-2026-02-08` | Simon J. D. Prince, *Understanding Deep Learning*, 2026-02-08 | 541 | `f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32` | 行内/块级数学、矩阵、彩色/矢量图、代码、索引 |
| `fde-fanbing-userpdf-2026-07` | 范冰《前置部署工程师》，PDF 封面 2026-07 开源版 | 99 | `cc80095e9f08c1c51b1a8a6c2fa859f445746f9817f1e631043849aca93f200e` | 中文长段落、分页续接、FDE/AI 中英混排、编号列表、参考资料 |

**修订边界**：官方 GitHub/网页的最新版不自动等于这些上传 PDF。尤其 FDE 上游使用《前线部署工程师》标题，不能与用户 PDF《前置部署工程师》静默混同。不得在同一 benchmark run 中把上传 PDF 的源 SHA 与后续 Markdown/EPUB 的内容混合作为金标准。第三方/官方 EPUB 只能作为**独立同版本经过核验的辅助参考**，不能预设为无误 ground truth。

**版权与数据边界**：
- AI Infra：[作者仓库](https://github.com/bojieli/ai-infra-book)；本计划未核实“上传 PDF 的精确字节及其衍生 EPUB”是否允许公开再分发。
- UDL：[作者网站](http://udlbook.com)；用户 PDF 声明 MIT Press 和 **CC BY-NC-ND**。内部对照、格式转换及发布衍生物所需的权利应由项目负责人确认，**不可将 CC 授权推断为任意再分发授权**。
- FDE：[作者仓库](https://github.com/xdash/FDE-the-Guidance-Book-of-Forward-Deployed-Engineer) 声明免费阅读、非商业分享，商业用途需作者许可；还需核实与用户 PDF 的修订对应性。
- **默认三份均 `redistributable=false / rights_review_required`**。当前**不提交** PDF、EPUB、整页截图、含连续书稿文本的 gold、OCR 摘录或富含原文的公开 CI artifact；私有评测存储须限制访问和保留周期。不能仅因用户上传而断言团队获商业/公开 benchmark 授权。

## 3. 分层测试集（18 页待标注候选，绝非已 reviewed gold）

候选 JSON 各选 **6 个 PDF zero-based `page_index`**，共 18 个页级 review target。它们经 PDF 文本/绘图元素抽查选取，具体标注任务仍须由 reviewer 根据可见原稿确认；没有标注的任务输出 `NA`，**不得**按 0 或 1 计入。

- **AI Infra**：p7 目录；p11 架构图；p39 公式；p65 定量图表；p384 性能图；p517 卷末内容。定位图注/公式与周围正文的关系、长目录层级。
- **UDL**：p4 目录；p34 矢量图；p110 数学推导；p125 代码；p244 Vision Transformer 插图；p460 矩阵附录。重点检查 PDF 数学字体提取和图文交错。
- **FDE**：p1 目录；p2 第一章；p15–16 相邻页，测试分页及文字连续性；p91 案例编号；p94 附录资料。对连续段落、列表、标点和中文/拉丁语之间的空格做专项检查。

### 3.1 Gold Annotation 的正确生命周期

`candidate → rights-approved & source-pinned local fixture → draft annotation → independent reviewer A/B → consensus/adjudication → reviewed gold with provenance → baseline proposal → governed approval/activation`

与 [M14 schema](gold-annotation-benchmark.md) 一致：`document_id`、`source_sha256`、`status`、`annotated_by`、`reviewed_by`、`pages[].page_index`、`tasks`、`elements`、`reading_order`。不同任务可以**稀疏标注**：`text` 任务必须覆盖所声称评测的**完整**页面文本，而不能仅收集若干关键词充当全页 recall。

来源内容可能受到版权保护：公开 gold 可以优先保留 *coordinates、类型、ID、hash、脱敏统计*；需要原文计算字符级指标时在合法授权的受控环境保存和比对，不可将隐去文本的公开 gold 宣称足以完成完整文字准确率评测。不要为推进 Milestone 而伪造 reviewer 身份、分钟数或 consensus。

### 3.2 两个独立的回归轴

**A. Parser / BookIR quality（复用现有功能）**：
- `text.f1`，`reading_order.pair_accuracy`；
- `structures.headings/lists/tables/figures/captions/footnotes/formulas.f1`；
- 已审核 task coverage、页覆盖、bbox/provenance coverage、fail/timeout/skip 与 elapsed time；
- proxy（normalized character count、跨 parser consensus、Quality Engine score）单独展示，**不能**与人工准确率混称。

**B. End-to-end PDF→EPUB fidelity（拟新增，不能声称已存在 CLI/CI）**：

| 指标 | 可审计的定义 | 判定依据 |
|---|---|---|
| `epub.text_recall` / `text_precision` | 有效 gold 正文字符或 token 在 EPUB 正文 DOM 的召回 / 准确（忽略声明允许的空白规范化，检查重复） | 同 revision 的 reviewed full-page text；若无，`NA` |
| `epub.reading_order` | 经锚点匹配后的完整元素有序对正确比例，缺失元素按错计 | reviewed `reading_order` |
| `epub.navigation` | TOC href 命中率、分级结构正确率、source page-anchor 可达率 | 人工章节/索引 gold + 资源一致性 |
| `epub.figures` | source-linked 图像/图注召回与配对正确率、裁切缺失数、资源 MIME/尺寸/sha | reviewed figure/caption gold + 源区域对照 |
| `epub.formulas` | MathML 内容结构/符号人工正确率（有语义 gold 时）**与** visual fallback 可见完整率（分别报告） | reviewed math gold 或原 PDF 区域人工核对 |
| `epub.tables` | 行列/单元格结构正确率（语义输出）；视觉回退仅计保真覆盖率 | reviewed table gold |
| `epub.footnotes` | 脚注正文保留、正向/回链可达率和注号匹配 | reviewed footnote gold |
| `epub.assets` | 本地资源在 OPF manifest 中注册、引用存在、解码成功、源节点 → asset provenance | 机器校验；缺失不可静默发布 |
| `epub.reflow` | 指定字体大小、窗口宽度下内容被截断/溢出/重叠/无法放大案例数 | 固定环境截图 + 人工审核 |
| `epub.conformance` | EPUBCheck 错误/警告、Publication QA、XHTML XML parse、nav/manifest/spine、ZIP CRC | 自动检查 |
| `epub.determinism` | 同一 BookIR/同一工具版本多次构建的 EPUB byte/digest 或 normalized DOM digest 比较 | 明确固定构建元数据和环境 |
| `runtime` | 耗时 p50/p95、峰值 RSS、输出体积、失败率、人工复核分钟/页、AI 费用 | 固定硬件/版本/模型与原始日志 |

完整性分母应来自 reviewed 来源节点或明确的 page task universe；**“PDF 541 页 → EPUB 541 个 page anchor”“744 图片文件全可解码”只证明结构/资源，不证明公式完全正确**。全书数字不得由 18 页样本外推成全书绝对准确率。

## 4. 试验设计：区分 Parser 收益与 Renderer 收益

**隔离对照**，避免把不同算法阶段的改善混成一个胜负：

1. 固定同一 source PDF SHA、parser 版本/配置与 BookIR 快照；比较 `BookIR Compiler current`、`semantic rendering`、`hybrid semantic + source-pinned visual fallback`，测 **B 轴**；
2. 固定相同 EPUB 编译器与渲染策略，比较不同 parser / reconstruction（M21 结论产生后按已接受的变体配置），测 **A 轴**；
3. 记录是否用了 image fallback（不是 semantic formula/table success）、source bbox，含回退导致的字号/复制能力损失；关键输出按 `Semantic / Visual / NeedsReview` 分层统计；
4. 固定阅读器版本、viewport（窄屏/平板）、字号（默认与放大）、配色（亮/暗）、字体来源和截图 hash，比较具体阅读器上的可访问性及渲染质量；原版固定页图可作为视觉参照，**不得作为“可重排合格”证据**。

建议**先只在合成 fixture + rights-cleared 样本上引入自动结构门禁**，包括无断链、无非法 XHTML/OPF、无静默遗漏非文本节点、资源完整性、确定性。需要人工语义 gold 的阈值和 baseline，待有 reviewed evidence 后再由受控 PR 提议，不能根据“直觉 99%”设置伪精度阈值。

## 5. 自动化流程：当前已有命令 vs 待实现工作

### 5.1 当前已支持、可立即执行（不使用三本候选注册表）

```bash
# Synthetic BookIR → EPUB end-to-end golden suite（现有）
PYTHONPATH=backend/src python backend/tests/golden/run_corpus.py \
  --output artifacts/golden-regression --external-epubcheck

# NIST real parser benchmark（现有 benchmark/corpus/manifest.json）
PYTHONPATH=backend/src python -m book.benchmark.cli fetch \
  --manifest benchmark/corpus/manifest.json
PYTHONPATH=backend/src python -m book.benchmark.cli verify \
  --manifest benchmark/corpus/manifest.json
PYTHONPATH=backend/src python -m book.benchmark.cli run \
  --manifest benchmark/corpus/manifest.json \
  --backends pymupdf,mineru,marker \
  --output artifacts/parser-benchmark
PYTHONPATH=backend/src python -m book.benchmark.cli gold-validate \
  --manifest benchmark/corpus/manifest.json
```

`--external-epubcheck` 依赖运行环境已安装 EPUBCheck，不能将找不到工具解释为成功。MinerU/Marker 可选，缺失是 `skipped`，并且不能自动作为 parser failure。上述命令是**已有入口**，并不加载 `benchmark/technical-books/candidates.json`。

### 5.2 拟新增的自动化接口（**尚未实现**）

```text
Private source resolver (exact sha + rights gate; fail closed)
 → Parser matrix (isolated, pinned versions) → BookIR snapshots
 → Gold matching (reviewed tasks only; draft observational)
 → Renderer strategy matrix (current / semantic / hybrid)
 → EPUBCheck + Publication QA + EPUB asset/link audit
 → Reader screenshot matrix + human review queue
 → Cross-stage regression report (quality / runtime / cost / NA)
 → Proposal for baseline; independent approval for new gates
```

建议未来提供 **`book.benchmark.technical_books`** 的独立命令或 runner，而非直接修改现有 `book.benchmark.cli` 或复用 NIST corpus ID。**这只是待评估接口名称，不是当前可运行命令。**

- `preflight`：校验来源是否允许使用、revision 与 SHA、精确页数、所需 reviewers、依赖可用性、parser/renderer 环境哈希；任何不符均 `blocked`，不可假装测试成功。
- `run`：输出按 `{doc-id}/{source-sha}/{parser}/{strategy}` 归档，生成 deterministic manifest、每页指标与来源对应；不得在公开 artifact 里泄漏受权利限制的正文和渲染截图。
- `report`：严格区分 `PASS`、`FAIL`、`SKIPPED`、`BLOCKED_RIGHTS`、`WAITING_FOR_REVIEW`、`INVALID_EVIDENCE`；gold 度量必须附样本量、任务范围和 reviewer/provenance ID。
- `gate`：结构校验先以合法的合成 fixture 执行；人工准确率必须具有 canonical consensus provenance 和显式获批的 baseline 才可作为 gate。

## 6. CI / 数据流安全与治理

**建议分级，先不新增 workflow 文件**：

| Stage | 数据 | 触发 | 门禁策略 |
|---|---|---|---|
| S0（现有）| Synthetic Golden/NIST | GitHub CI | **保持原逻辑不变** |
| S1（建议）| 三份私有固定 PDF + 候选 review targets | 人工本地/授权私有 runner | 仅保存本地报告，`provisional`；不改变 CI |
| S2（建议）| 经授权且完成 consensus 的 reviewed gold | 受控 benchmark PR | 提交脱敏指标/候选 baseline，沿用 M17–19 审批流程 |
| S3（建议）| 审核通过的技术书指标与许可兼容 fixture | 独立 `workflow_dispatch`/受控 CI | 单独 gate，先 shadow，再经独立审批激活 |

不得把用户上传 PDF 或对照 EPUB 当作 public GitHub Actions artifact；若使用 GitHub-hosted runner，必须先评估代码和中间产物的泄漏面。对受限文件，优先本地或隔离私有 runner、受控缓存与严格 artifact allowlist。

**当前状态应始终为** `candidate_only / 0 new reviewed technical-book pages / no new baseline / no newly activated gate`。除非真实人工评审、权限确认、政策批准，不得以此文档声称完成任何上述后续阶段。

## 7. 分阶段实施与验收（与 Issue #4 衔接）

**R0 — 本 PR（仅文档，已定义）：**
- [x] 三本书真实 PDF 页数、来源 SHA 及修订边界已核实。
- [x] 候选 corpus 清单、18 个待人工确认的 page/task targets。
- [x] 现有模块与新增端到端指标分层，以及阶段化自动化契约。
- [x] 明确候选不触发门禁、不覆盖现有治理，不提交书稿/衍生 EPUB。

**R1 — Synthetic EPUB rendering fixtures（未来代码工作）**
- [ ] 在版权安全的 synthetic fixture 上覆盖 Figure/Caption、Formula(MathML/图片)、Table(HTML/视觉)、Footnote、代码块、导航、资源引用。
- [ ] 输出两个轴的结构报告；外部 EPUBCheck、DOM/资产完整性与固定环境 reflow smoke。
- [ ] 同一 BookIR 在相同编译参数下可重复构建；明确非确定性源头。

**R2 — Private technical-book pilot（需授权与人工复核）**
- [ ] 每本先从 6 个候选页中完成可用的源许可审批、双 reviewer 独立确认、必要冲突仲裁与 consensus provenance。
- [ ] 通过人工源页对照逐任务打分；覆盖上述结构、内容、导航和 reflow 指标；标注页之外输出 `NA`。
- [ ] 记录失败和人为干预成本，不仅记录成功输出。

**R3 — Governance / CI promotion（需另行独立审批）**
- [ ] 推出本领域单独的 reviewed baseline proposal、coverage floor、regression budget；写清测量定义与合理阈值来源。
- [ ] 先 shadow report、后 gated release；受限语料的内容永不流入公共 artifacts。
- [ ] 审核后才能更改 `benchmark/corpus/manifest.json`、`benchmark/corpus/review-plan.json`、gold、CI、M21 状态或默认渲染策略。

## 8. 明确的非目标

- 不修改 M21 Occam A/B/C/D 变体、reviewer 分工、PR #3、现有 NIST corpus、gold status、baseline registry、Sigstore/EPUBCheck gate。
- 不依据自动文字抽取与 EPUB 的逐字符一致，直接推断源 PDF 排版或数学语义已无误。
- 不把此次先前聊天中的个人转换结果作为 EBookAI 已完成的 regression evidence。
- 不承诺自动转换“100% 无误”；以明确页/task 的 reviewed evidence、内容错误清单与未覆盖范围表达结论。
