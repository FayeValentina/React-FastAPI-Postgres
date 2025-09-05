import { TaskParameterInfo, TypeInfo, UIMetaInfo } from '../types/task-info';

export function isIgnoredParam(p: TaskParameterInfo): boolean {
  if (!p) return true;
  if (p.ui?.exclude_from_ui) return true;
  const name = p.name?.toLowerCase?.() || '';
  if (name === 'config_id' || name === 'context') return true;
  const t = p.type_info?.type?.toLowerCase?.();
  return t === 'context';
}

export function flattenOptional(t?: TypeInfo): TypeInfo | undefined {
  if (!t) return t;
  if (t.type === 'optional' && t.args && t.args.length === 1) return t.args[0];
  return t;
}

export type WidgetType = 'text' | 'number' | 'boolean' | 'email' | 'json' | 'select';

export function pickWidget(taskDotParam: string, t?: TypeInfo, ui?: UIMetaInfo): WidgetType {
  if (ui?.ui_hint) {
    const hint = ui.ui_hint.toLowerCase();
    if (hint === 'select') return 'select';
    if (hint === 'number') return 'number';
    if (hint === 'boolean') return 'boolean';
    if (hint === 'email') return 'email';
    if (hint === 'json') return 'json';
    return 'text';
  }
  const base = (t?.type || 'any').toLowerCase();
  if (base === 'int' || base === 'float' || base === 'number') return 'number';
  if (base === 'bool' || base === 'boolean') return 'boolean';
  if (base === 'str' || base === 'string') return taskDotParam.toLowerCase().endsWith('email') ? 'email' : 'text';
  // dict/list/union/any/complex
  return 'json';
}

export function parseDefault(raw: string | null | undefined, t?: TypeInfo): unknown {
  if (raw == null) return undefined;
  const base = (t?.type || '').toLowerCase();
  const trimmed = String(raw);
  // strip quotes
  if ((trimmed.startsWith("'") && trimmed.endsWith("'")) || (trimmed.startsWith('"') && trimmed.endsWith('"'))) {
    return trimmed.slice(1, -1);
  }
  if (trimmed === 'True') return true;
  if (trimmed === 'False') return false;
  if ((base === 'int' || base === 'float' || base === 'number') && !Number.isNaN(Number(trimmed)) && trimmed.trim() !== '') {
    return Number(trimmed);
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
}

export function coerceOnChange(input: unknown, t?: TypeInfo): unknown {
  const base = (t?.type || '').toLowerCase();
  if (base === 'int' || base === 'float' || base === 'number') {
    const n = Number(input);
    return Number.isNaN(n) ? undefined : n;
  }
  if (base === 'bool' || base === 'boolean') {
    if (typeof input === 'boolean') return input;
    if (input === 'true' || input === '1') return true;
    if (input === 'false' || input === '0') return false;
    return Boolean(input);
  }
  if (base === 'str' || base === 'string' || base === 'email') {
    return String(input ?? '');
  }
  // complex types: expect JSON string
  if (typeof input === 'string') {
    try { return JSON.parse(input); } catch { return input; }
  }
  return input;
}

export function isEmptyValue(v: unknown): boolean {
  if (v === undefined || v === null) return true;
  if (typeof v === 'string') return v.trim() === '';
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === 'object') return Object.keys(v as Record<string, unknown>).length === 0;
  return false;
}

// ---------- JSON 示例生成（仅基于 type_info 推断，不需预定义） ----------

function exampleFromTypeInfo(t?: TypeInfo, depth: number = 0): unknown {
  if (!t || depth > 3) return '<any>';
  const base = (t.type || '').toLowerCase();
  if (base === 'str' || base === 'string') return 'string';
  if (base === 'int' || base === 'number') return 0;
  if (base === 'float') return 0.0;
  if (base === 'bool' || base === 'boolean') return false;
  if (base === 'any') return '<any>';
  if (base === 'literal') {
    const first = t.args && t.args[0];
    return first ? first.type : '<literal>';
    }
  if (base === 'optional') {
    return exampleFromTypeInfo(t.args && t.args[0], depth + 1);
  }
  if (base === 'union') {
    const nonNull = (t.args || []).find((a) => (a.type || '').toLowerCase() !== 'nonetype');
    return exampleFromTypeInfo(nonNull || (t.args && t.args[0]), depth + 1);
  }
  if (base === 'list' || base === 'typing.list' || base === 'list[typing.dict]') {
    const item = exampleFromTypeInfo(t.args && t.args[0], depth + 1);
    return [item];
  }
  if (base === 'dict' || base === 'typing.dict' || base === 'mapping') {
    const valueType = t.args && t.args[1];
    const value = exampleFromTypeInfo(valueType, depth + 1);
    return { key: value };
  }
  // fallback for complex/unknown
  return '<any>';
}

export function jsonExampleForParamFromType(t?: TypeInfo): string | undefined {
  const example = exampleFromTypeInfo(t);
  if (example === undefined) return undefined;
  try {
    return JSON.stringify(example, null, 2);
  } catch {
    return String(example);
  }
}
