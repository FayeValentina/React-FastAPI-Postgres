import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  TextField,
  FormControlLabel,
  Switch,
  Slider,
  Typography,
  Grid,
  Chip,
  Autocomplete,
  MenuItem,
  Alert,
  FormControl,
  InputLabel,
  Select,
  Paper,
  Divider,
} from '@mui/material';
import { 
  BotConfigCreate, 
  BotConfigResponse, 
  BotConfigUpdate,
  SORT_METHODS,
  TIME_FILTERS,
  POPULAR_SUBREDDITS 
} from '../../types/bot';

interface BotConfigFormProps {
  config?: BotConfigResponse | null;
  onSubmit: (data: BotConfigCreate | BotConfigUpdate) => void;
  loading?: boolean;
  error?: string | null;
  formSubmitRef?: React.MutableRefObject<(() => void) | null>;
}

interface FormData {
  name: string;
  description: string;
  target_subreddits: string[];
  posts_per_subreddit: number | '';
  comments_per_post: number | '';
  sort_method: string;
  time_filter: string;
  enable_ai_filter: boolean;
  ai_confidence_threshold: number;
  min_comment_length: number | '';
  max_comment_length: number | '';
  auto_publish_enabled: boolean;
  publish_interval_hours: number | '';
  max_daily_posts: number | '';
}

interface FormErrors {
  [key: string]: string;
}

const BotConfigForm: React.FC<BotConfigFormProps> = ({
  config,
  onSubmit,
  loading = false,
  error = null,
  formSubmitRef,
}) => {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    target_subreddits: ['python', 'programming'],
    posts_per_subreddit: 50,
    comments_per_post: 20,
    sort_method: 'hot',
    time_filter: 'day',
    enable_ai_filter: true,
    ai_confidence_threshold: 0.8,
    min_comment_length: 10,
    max_comment_length: 280,
    auto_publish_enabled: false,
    publish_interval_hours: 24,
    max_daily_posts: 5,
  });

  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [subredditInput, setSubredditInput] = useState('');

  // Initialize form data when config changes
  useEffect(() => {
    if (config) {
      setFormData({
        name: config.name,
        description: config.description || '',
        target_subreddits: config.target_subreddits,
        posts_per_subreddit: config.posts_per_subreddit,
        comments_per_post: config.comments_per_post,
        sort_method: config.sort_method,
        time_filter: config.time_filter,
        enable_ai_filter: config.enable_ai_filter,
        ai_confidence_threshold: config.ai_confidence_threshold,
        min_comment_length: config.min_comment_length,
        max_comment_length: config.max_comment_length,
        auto_publish_enabled: config.auto_publish_enabled,
        publish_interval_hours: config.publish_interval_hours,
        max_daily_posts: config.max_daily_posts,
      });
    }
  }, [config]);

  const validateForm = useCallback((): boolean => {
    const errors: FormErrors = {};

    if (!formData.name.trim()) {
      errors.name = '请输入配置名称';
    } else if (formData.name.length > 100) {
      errors.name = '配置名称不能超过100个字符';
    }

    if (formData.target_subreddits.length === 0) {
      errors.target_subreddits = '至少选择一个目标subreddit';
    } else if (formData.target_subreddits.length > 10) {
      errors.target_subreddits = '最多只能选择10个subreddit';
    }

    if (formData.posts_per_subreddit === '' || formData.posts_per_subreddit < 1 || formData.posts_per_subreddit > 500) {
      errors.posts_per_subreddit = '帖子数量必须在1-500之间';
    }

    if (formData.comments_per_post === '' || formData.comments_per_post < 1 || formData.comments_per_post > 100) {
      errors.comments_per_post = '评论数量必须在1-100之间';
    }

    if (formData.ai_confidence_threshold < 0 || formData.ai_confidence_threshold > 1) {
      errors.ai_confidence_threshold = 'AI置信度必须在0-1之间';
    }

    if (formData.min_comment_length === '' || formData.min_comment_length < 1) {
      errors.min_comment_length = '最小评论长度必须大于0';
    }

    if (formData.max_comment_length === '' || (typeof formData.min_comment_length === 'number' && typeof formData.max_comment_length === 'number' && formData.max_comment_length < formData.min_comment_length)) {
      errors.max_comment_length = formData.max_comment_length === '' ? '最大评论长度必须大于0' : '最大评论长度不能小于最小长度';
    }

    if (formData.publish_interval_hours === '' || formData.publish_interval_hours < 1) {
      errors.publish_interval_hours = '发布间隔必须大于0小时';
    }

    if (formData.max_daily_posts === '' || formData.max_daily_posts < 1) {
      errors.max_daily_posts = '每日最大发布数必须大于0';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }, [formData]);

  const handleChange = (field: keyof FormData, value: unknown) => {
    // Handle number fields specially
    if (['posts_per_subreddit', 'comments_per_post', 'min_comment_length', 'max_comment_length', 'publish_interval_hours', 'max_daily_posts'].includes(field)) {
      const strValue = String(value);
      const numValue = strValue === '' ? '' : parseInt(strValue, 10);
      setFormData(prev => ({
        ...prev,
        [field]: numValue,
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [field]: value,
      }));
    }

    // Clear field error when user starts typing
    if (formErrors[field]) {
      setFormErrors(prev => ({
        ...prev,
        [field]: '',
      }));
    }
  };

  const handleSubredditAdd = (subreddit: string) => {
    const cleanSubreddit = subreddit.replace(/^r\//, '').trim().toLowerCase();
    if (cleanSubreddit && !formData.target_subreddits.includes(cleanSubreddit)) {
      handleChange('target_subreddits', [...formData.target_subreddits, cleanSubreddit]);
    }
    setSubredditInput('');
  };

  const handleSubredditRemove = (subredditToRemove: string) => {
    handleChange(
      'target_subreddits',
      formData.target_subreddits.filter(s => s !== subredditToRemove)
    );
  };

  const handleSubmit = useCallback((e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }
    
    if (!validateForm()) {
      return;
    }

    // Prepare data for submission
    const submitData = {
      ...formData,
      posts_per_subreddit: formData.posts_per_subreddit === '' ? 50 : formData.posts_per_subreddit,
      comments_per_post: formData.comments_per_post === '' ? 20 : formData.comments_per_post,
      min_comment_length: formData.min_comment_length === '' ? 10 : formData.min_comment_length,
      max_comment_length: formData.max_comment_length === '' ? 280 : formData.max_comment_length,
      publish_interval_hours: formData.publish_interval_hours === '' ? 24 : formData.publish_interval_hours,
      max_daily_posts: formData.max_daily_posts === '' ? 5 : formData.max_daily_posts,
    };
    
    // Remove empty description
    if (!submitData.description.trim()) {
      const { description, ...dataWithoutDescription } = submitData;
      void description; // Mark as intentionally unused
      return onSubmit(dataWithoutDescription);
    }

    onSubmit(submitData);
  }, [formData, onSubmit, validateForm]);

  // Expose submit function to parent via ref
  useEffect(() => {
    if (formSubmitRef) {
      formSubmitRef.current = () => handleSubmit();
    }
  }, [formSubmitRef, handleSubmit]);

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ maxWidth: 800 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* 基本信息 */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              基本信息
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="配置名称"
                  value={formData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  error={!!formErrors.name}
                  helperText={formErrors.name}
                  required
                  disabled={loading}
                />
              </Grid>
              
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="描述 (可选)"
                  value={formData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  multiline
                  rows={2}
                  disabled={loading}
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* 目标Subreddits */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              目标Subreddits
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Autocomplete
              fullWidth
              freeSolo
              options={POPULAR_SUBREDDITS}
              inputValue={subredditInput}
              onInputChange={(_, newValue) => setSubredditInput(newValue)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSubredditAdd(subredditInput);
                }
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="添加Subreddit"
                  placeholder="输入subreddit名称，如 'python' 或 'r/python'"
                  helperText={formErrors.target_subreddits || "按回车键添加，或从建议中选择"}
                  error={!!formErrors.target_subreddits}
                  disabled={loading}
                />
              )}
            />
            
            <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {formData.target_subreddits.map((subreddit) => (
                <Chip
                  key={subreddit}
                  label={`r/${subreddit}`}
                  onDelete={() => handleSubredditRemove(subreddit)}
                  disabled={loading}
                />
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* 爬取设置 */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              爬取设置
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="每个subreddit的帖子数量"
                  type="number"
                  value={formData.posts_per_subreddit}
                  onChange={(e) => handleChange('posts_per_subreddit', e.target.value)}
                  error={!!formErrors.posts_per_subreddit}
                  helperText={formErrors.posts_per_subreddit}
                  inputProps={{ min: 1, max: 500 }}
                  disabled={loading}
                />
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="每个帖子的评论数量"
                  type="number"
                  value={formData.comments_per_post}
                  onChange={(e) => handleChange('comments_per_post', e.target.value)}
                  error={!!formErrors.comments_per_post}
                  helperText={formErrors.comments_per_post}
                  inputProps={{ min: 1, max: 100 }}
                  disabled={loading}
                />
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>排序方式</InputLabel>
                  <Select
                    value={formData.sort_method}
                    onChange={(e) => handleChange('sort_method', e.target.value)}
                    label="排序方式"
                    disabled={loading}
                  >
                    {SORT_METHODS.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>时间筛选</InputLabel>
                  <Select
                    value={formData.time_filter}
                    onChange={(e) => handleChange('time_filter', e.target.value)}
                    label="时间筛选"
                    disabled={loading}
                  >
                    {TIME_FILTERS.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* AI过滤设置 */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              AI过滤设置
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <FormControlLabel
              control={
                <Switch
                  checked={formData.enable_ai_filter}
                  onChange={(e) => handleChange('enable_ai_filter', e.target.checked)}
                  disabled={loading}
                />
              }
              label="启用AI过滤"
              sx={{ mb: 2 }}
            />
            
            {formData.enable_ai_filter && (
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Typography gutterBottom>
                    AI置信度阈值: {formData.ai_confidence_threshold}
                  </Typography>
                  <Slider
                    value={formData.ai_confidence_threshold}
                    onChange={(_, value) => handleChange('ai_confidence_threshold', value)}
                    min={0}
                    max={1}
                    step={0.1}
                    marks
                    disabled={loading}
                  />
                </Grid>
              </Grid>
            )}
            
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="最小评论长度"
                  type="number"
                  value={formData.min_comment_length}
                  onChange={(e) => handleChange('min_comment_length', e.target.value)}
                  error={!!formErrors.min_comment_length}
                  helperText={formErrors.min_comment_length}
                  inputProps={{ min: 1 }}
                  disabled={loading}
                />
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="最大评论长度"
                  type="number"
                  value={formData.max_comment_length}
                  onChange={(e) => handleChange('max_comment_length', e.target.value)}
                  error={!!formErrors.max_comment_length}
                  helperText={formErrors.max_comment_length}
                  inputProps={{ min: 1 }}
                  disabled={loading}
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* 自动发布设置 */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              自动发布设置
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <FormControlLabel
              control={
                <Switch
                  checked={formData.auto_publish_enabled}
                  onChange={(e) => handleChange('auto_publish_enabled', e.target.checked)}
                  disabled={loading}
                />
              }
              label="启用自动发布"
              sx={{ mb: 2 }}
            />
            
            {formData.auto_publish_enabled && (
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="发布间隔 (小时)"
                    type="number"
                    value={formData.publish_interval_hours}
                    onChange={(e) => handleChange('publish_interval_hours', e.target.value)}
                    error={!!formErrors.publish_interval_hours}
                    helperText={formErrors.publish_interval_hours}
                    inputProps={{ min: 1 }}
                    disabled={loading}
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="每日最大发布数"
                    type="number"
                    value={formData.max_daily_posts}
                    onChange={(e) => handleChange('max_daily_posts', e.target.value)}
                    error={!!formErrors.max_daily_posts}
                    helperText={formErrors.max_daily_posts}
                    inputProps={{ min: 1 }}
                    disabled={loading}
                  />
                </Grid>
              </Grid>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default BotConfigForm;