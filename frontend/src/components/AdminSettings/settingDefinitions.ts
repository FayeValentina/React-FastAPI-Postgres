import { AdminSettingKey } from '../../types/adminSettings';

export type AdminSettingValueType = 'int' | 'float' | 'boolean';

export interface AdminSettingDefinition {
  key: AdminSettingKey;
  label: string;
  description?: string;
  type: AdminSettingValueType;
  min?: number;
  max?: number;
  step?: number;
}

export const FEATURE_TOGGLE_KEYS: AdminSettingKey[] = [
  'RAG_STRATEGY_ENABLED',
  'RAG_STRATEGY_LLM_CLASSIFIER_ENABLED',
  'RAG_RERANK_ENABLED',
  'RAG_USE_LINGUA',
  'BM25_ENABLED',
  'QUERY_REWRITE_ENABLED',
];

export const ADMIN_SETTING_DEFINITIONS: AdminSettingDefinition[] = [
  {
    key: 'RAG_STRATEGY_ENABLED',
    label: '策略层开关',
    description: '控制是否启用基于查询特征的策略层。开启后会动态覆盖 top_k、相似度阈值等核心参数；关闭则使用静态或 Redis 配置。',
    type: 'boolean',
  },
  {
    key: 'RAG_STRATEGY_LLM_CLASSIFIER_ENABLED',
    label: 'LLM 查询意图分类器',
    description: '开启后将调用 LLM 对查询意图进行判定，并在高置信度时覆盖策略场景；关闭则仅依赖启发式分类。',
    type: 'boolean',
  },
  {
    key: 'RAG_TOP_K',
    label: '候选文档数量 (TOP_K)',
    description: '检索阶段返回的候选文档数量。值越大返回的候选越多，召回率更高但重排与生成成本随之上升；值越小成本更低但可能遗漏相关内容。',
    type: 'int',
    min: 1,
    max: 100,
  },
  {
    key: 'RAG_MIN_SIM',
    label: '最小相似度 (MIN_SIM)',
    description: '低于该阈值的文档将被过滤，范围在 0 和 1 之间。值越大筛选越严格，结果更精确但可能缺少备选；值越小放宽过滤，召回更多但噪声增加。',
    type: 'float',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD',
    label: 'LLM 分类置信度阈值',
    description: '当 LLM 返回的置信度低于该阈值时，将回退至启发式分类结果。范围 0-1。',
    type: 'float',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'RAG_MMR_LAMBDA',
    label: 'MMR 多样性权重 (MMR_LAMBDA)',
    description: 'MMR 算法中平衡相关性与多样性的权重，0 表示偏向多样性，1 表示偏向相关性。值越大越重视与查询的相关性；值越小越强调内容多样性。',
    type: 'float',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'RAG_PER_DOC_LIMIT',
    label: '每文档返回片段数 (PER_DOC_LIMIT)',
    description: '限制每个文档可返回的片段数量，用于控制结果集中单一文档的占比。值越大可以给单个文档更多曝光，但可能导致结果不均衡；值越小提升文档多样性但易忽略长文重要片段。',
    type: 'int',
    min: 0,
  },
  {
    key: 'RAG_OVERSAMPLE',
    label: '初始检索过采样 (OVERSAMPLE)',
    description: '为了提高召回率可额外检索的文档数量，用于后续过滤。值越大预取候选越多，召回更全面但会加重负载；值越小效率高但后续可用候选减少。',
    type: 'int',
    min: 1,
  },
  {
    key: 'RAG_MAX_CANDIDATES',
    label: '最大候选数量 (MAX_CANDIDATES)',
    description: '用于后续 rerank 阶段的最大候选文档数量上限。值越大 rerank 空间更充分但耗时更长；值越小速度更快但可能错过高质量候选。',
    type: 'int',
    min: 1,
  },
  {
    key: 'RAG_RERANK_ENABLED',
    label: 'Cross-Encoder 重排开关',
    description: '控制是否在向量召回后执行 Cross-Encoder 重排。开启可显著提高候选质量，但会增加每次请求的推理时间。',
    type: 'boolean',
  },
  {
    key: 'BM25_ENABLED',
    label: 'BM25 关键字检索',
    description: '开启后会结合 PostgreSQL 全文检索结果与向量召回进行融合，提高关键字匹配能力；关闭则仅依赖向量召回。',
    type: 'boolean',
  },
  {
    key: 'RAG_RERANK_CANDIDATES',
    label: '重排候选数量',
    description: '送入 Cross-Encoder 重排的候选数量。值越大排序更精细但耗时更长；值越小速度快但可能错过相关片段。',
    type: 'int',
    min: 1,
    max: 200,
  },
  {
    key: 'RAG_RERANK_SCORE_THRESHOLD',
    label: '重排得分阈值',
    description: '低于该阈值的候选会被丢弃，范围 0-1。阈值越高越严格，噪声更少但可能漏掉边缘内容；阈值越低覆盖更多但上下文可能变杂。',
    type: 'float',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'RAG_RERANK_MAX_BATCH',
    label: '重排批处理大小',
    description: 'Cross-Encoder 推理时的批处理大小。增大可提高吞吐，过大可能导致显存/内存压力；减小可降低单批负载但调度成本上升。',
    type: 'int',
    min: 1,
    max: 128,
  },
  {
    key: 'BM25_TOP_K',
    label: 'BM25 候选数量上限',
    description: '参与 BM25 召回的最大片段数。数值越大关键词召回更充分但融合开销更高；数值越小性能更好但可能遗漏相关片段。',
    type: 'int',
    min: 0,
    max: 200,
  },
  {
    key: 'RAG_SAME_LANG_BONUS',
    label: '同语言奖励 (SAME_LANG_BONUS)',
    description: '如果检索结果与查询语言一致，将加成该权重。值越大越偏向与查询语言相同的结果；值越小对跨语言内容更开放。',
    type: 'float',
    min: 0,
    max: 5,
    step: 0.1,
  },
  {
    key: 'RAG_CONTEXT_TOKEN_BUDGET',
    label: '上下文 token 预算',
    description: '允许拼接到提示中的最大 token 数，超过该预算的内容将被截断。值越大上下文更完整但会增加模型调用成本；值越小响应更快但可能丢失关键信息。',
    type: 'int',
    min: 0,
  },
  {
    key: 'RAG_CONTEXT_MAX_EVIDENCE',
    label: '上下文证据片段上限',
    description: '构建回答上下文时最多可包含的片段数量。值越大可引用的证据更多但上下文冗长；值越小上下文精简但可能不足以支撑回答。',
    type: 'int',
    min: 0,
  },
  {
    key: 'BM25_WEIGHT',
    label: 'BM25 融合权重',
    description: '调整 BM25 与向量相似度的融合比例。值越大越偏向关键字匹配，值越小更依赖向量语义相似度。',
    type: 'float',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'BM25_MIN_SCORE',
    label: 'BM25 最小得分阈值',
    description: 'BM25 原始得分低于该阈值的候选会被忽略，用于过滤低质量关键字命中。',
    type: 'float',
    min: 0,
    step: 0.01,
  },
  {
    key: 'RAG_CHUNK_TARGET_TOKENS_EN',
    label: '英文分片目标长度',
    description: '英文文档分片的目标 token 长度。值越大单片覆盖内容更多但相关度可能下降；值越小分片更细致但数量增加、索引成本变高。',
    type: 'int',
    min: 1,
  },
  {
    key: 'RAG_CHUNK_TARGET_TOKENS_CJK',
    label: '中日韩分片目标长度',
    description: '中日韩文档分片的目标 token 长度。值越大单片更长、召回覆盖更广但可能引入噪声；值越小粒度更精细但需要更多片段才能涵盖全文。',
    type: 'int',
    min: 1,
  },
  {
    key: 'RAG_CHUNK_TARGET_TOKENS_DEFAULT',
    label: '默认分片目标长度',
    description: '未显式分类语言时使用的分片目标 token 长度。值越大可以减少分片数量但片内主题可能混杂；值越小分片更集中却会增大索引体积。',
    type: 'int',
    min: 1,
  },
  {
    key: 'RAG_CHUNK_OVERLAP_RATIO',
    label: '分片重叠比例',
    description: '相邻分片之间的 token 重叠比例，范围 0-1。值越大上下文衔接更完整但索引冗余增加；值越小片段独立性更高但可能割裂语义。',
    type: 'float',
    min: 0,
    max: 1,
    step: 0.05,
  },
  {
    key: 'RAG_CODE_CHUNK_MAX_LINES',
    label: '代码分片最大行数',
    description: '代码类型文档分片的最大行数。值越大单片涵盖的代码块更多但定位精度下降；值越小保留局部语义但可能需要组合多个片段。',
    type: 'int',
    min: 1,
  },
  {
    key: 'RAG_CODE_CHUNK_OVERLAP_LINES',
    label: '代码分片重叠行数',
    description: '相邻代码分片的重叠行数。值越大上下文连续性更强但片段冗余增加；值越小索引体积更小但函数或代码块可能被拆散。',
    type: 'int',
    min: 0,
  },
  {
    key: 'RAG_USE_LINGUA',
    label: '启用 Lingua 语言检测',
    description:
      '开启后优先使用 Lingua 进行语言识别，准确度更高；关闭时会退回到轻量规则或正则，适合对依赖体积敏感的环境。',
    type: 'boolean',
  },
  {
    key: 'RAG_IVFFLAT_PROBES',
    label: 'IVFFLAT 探针数量',
    description: '向量索引的查询探针数量，直接影响检索性能与速度。值越大检索更准确但查询耗时增加；值越小响应更快但召回率可能下降。',
    type: 'int',
    min: 1,
  },
  {
    key: 'QUERY_REWRITE_ENABLED',
    label: '查询改写开关',
    description: '允许后端针对用户查询执行改写或预处理逻辑，以改善召回效果。关闭时使用原始查询文本。',
    type: 'boolean',
  },
];

export const ADMIN_SETTING_DEFINITION_MAP = ADMIN_SETTING_DEFINITIONS.reduce<Record<AdminSettingKey, AdminSettingDefinition>>(
  (acc, definition) => {
    acc[definition.key] = definition;
    return acc;
  },
  {} as Record<AdminSettingKey, AdminSettingDefinition>,
);
