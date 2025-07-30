// Bot配置相关的类型定义

export interface BotConfigBase {
  name: string;
  description?: string;
  target_subreddits: string[];
  posts_per_subreddit: number;
  comments_per_post: number;
  sort_method: string;
  time_filter: string;
  enable_ai_filter: boolean;
  ai_confidence_threshold: number;
  min_comment_length: number;
  max_comment_length: number;
  auto_publish_enabled: boolean;
  publish_interval_hours: number;
  max_daily_posts: number;
}

export type BotConfigCreate = BotConfigBase;

export type BotConfigUpdate = Partial<BotConfigBase>;

export interface BotConfigResponse extends BotConfigBase {
  id: number;
  user_id: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BotConfigToggleResponse {
  id: number;
  is_active: boolean;
  message: string;
}

// 排序方式选项
export const SORT_METHODS = [
  { value: 'hot', label: '热门' },
  { value: 'new', label: '最新' },
  { value: 'top', label: '顶部' },
  { value: 'controversial', label: '争议' },
  { value: 'rising', label: '上升' },
  { value: 'gilded', label: '已镀金' },
];

// 时间筛选选项
export const TIME_FILTERS = [
  { value: 'all', label: '全部时间' },
  { value: 'day', label: '今天' },
  { value: 'week', label: '本周' },
  { value: 'month', label: '本月' },
  { value: 'year', label: '今年' },
  { value: 'hour', label: '本小时' },
];

// 常用的subreddit建议
export const POPULAR_SUBREDDITS = [
  'python',
  'programming',
  'MachineLearning',
  'artificial',
  'technology',
  'datascience',
  'webdev',
  'javascript',
  'reactjs',
  'FastAPI',
];