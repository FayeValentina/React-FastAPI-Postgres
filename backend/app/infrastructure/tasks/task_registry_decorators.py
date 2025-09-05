"""
任务注册系统（支持参数信息提取 + Annotated UI元信息）
"""
from typing import (
    Dict,
    Optional,
    Callable,
    Set,
    List,
    Any,
    get_origin,
    get_args,
    Annotated,
    Literal,
)
from enum import Enum

import logging
import importlib
import pkgutil
import inspect

logger = logging.getLogger(__name__)

# 全局任务注册表（唯一）
TASKS: Dict[str, Dict] = {}


def _unwrap_annotated(type_hint) -> tuple[Any, List[Any]]:
    """如果是 typing.Annotated[T, meta...], 返回 (T, [meta...]); 否则 (type_hint, [])."""
    try:
        origin = get_origin(type_hint)
        if origin is Annotated:
            args = list(get_args(type_hint))
            if args:
                base = args[0]
                meta = args[1:]
                return base, meta
    except Exception:
        pass
    return type_hint, []


def _merge_ui_meta(meta_list: List[Any]) -> Optional[Dict[str, Any]]:
    """将 Annotated 中的 meta 合并为字典，仅提取已知UI字段。"""
    if not meta_list:
        return None
    ui: Dict[str, Any] = {}
    keys = {
        'exclude_from_ui', 'ui_hint', 'choices', 'label', 'description',
        'placeholder', 'min', 'max', 'step', 'pattern', 'example'
    }
    for m in meta_list:
        if m is None:
            continue
        if isinstance(m, dict):
            for k, v in m.items():
                if k in keys:
                    ui[k] = v
        else:
            # 兼容对象形式的meta
            for k in keys:
                if hasattr(m, k):
                    ui[k] = getattr(m, k)
    return ui or None


def _infer_ui_from_type(base_type: Any, param_name: str, default_repr: Optional[str]) -> Optional[Dict[str, Any]]:
    """基于类型与名称的启发式 UI 推断（可被 Annotated 覆盖）。"""
    ui: Dict[str, Any] = {}

    try:
        origin = get_origin(base_type)
        # Literal → 下拉选择
        if origin is Literal:
            ui['ui_hint'] = ui.get('ui_hint') or 'select'
            ui['choices'] = ui.get('choices') or list(get_args(base_type))
    except Exception:
        pass

    # Enum → 下拉选择
    try:
        if inspect.isclass(base_type) and issubclass(base_type, Enum):
            ui['ui_hint'] = ui.get('ui_hint') or 'select'
            ui['choices'] = ui.get('choices') or [m.value for m in base_type]
    except Exception:
        pass

    # 名称启发：email
    if param_name.lower().endswith('email') and 'ui_hint' not in ui:
        ui['ui_hint'] = 'email'

    # 自动隐藏 context / fastapi.Depends 默认 / config_id
    base_name = getattr(base_type, '__name__', str(base_type)).lower()
    if param_name == 'config_id':
        ui['exclude_from_ui'] = True
    if param_name == 'context' or base_name == 'context':
        ui['exclude_from_ui'] = True
    if isinstance(default_repr, str) and (
        'Dependency(' in default_repr or 'Depends(' in default_repr or 'TaskiqDepends' in default_repr
    ):
        ui['exclude_from_ui'] = True

    return ui or None

def _parse_type_annotation(type_hint) -> str:
    """递归解析类型注解，返回字符串表示"""
    if type_hint is None or type_hint is inspect.Parameter.empty:
        return "未指定"
    # 解包 Annotated
    base_type, _ = _unwrap_annotated(type_hint)

    origin = get_origin(base_type)
    args = get_args(base_type)
    
    # 如果是基本类型或无参数的泛型，直接返回其名称
    if not origin:
        type_name = getattr(base_type, '__name__', str(base_type))
        return type_name
    
    # 如果是泛型类型，则递归解析
    origin_name = getattr(origin, '__name__', str(origin))
    
    if not args:
        return origin_name
    
    # 处理 Union 类型
    if hasattr(base_type, '__origin__') and str(base_type).startswith('typing.Union'):
        inner_types = " | ".join([_parse_type_annotation(arg) for arg in args])
        return f"({inner_types})"
    
    # 处理其他泛型类型
    inner_types = ", ".join([_parse_type_annotation(arg) for arg in args])
    return f"{origin_name}[{inner_types}]"

def _parse_type_annotation_to_dict(type_hint) -> Dict[str, Any]:
    """递归解析类型注解，返回结构化的字典"""
    if type_hint is None or type_hint is inspect.Parameter.empty:
        return {"type": "any"}
    # 解包 Annotated
    base_type, _ = _unwrap_annotated(type_hint)

    origin = get_origin(base_type)
    args = get_args(base_type)
    
    # 如果是基本类型或无参数的泛型，直接返回其名称
    if not origin:
        type_name = getattr(base_type, '__name__', str(base_type))
        return {"type": type_name.lower()}

    origin_name = getattr(origin, '__name__', str(origin)).lower()
    
    # 特殊处理 Union 类型
    if origin_name == 'union':
        # 对于 Optional[T] 即 Union[T, NoneType] 的常见情况
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            return {
                "type": "optional",
                "args": [_parse_type_annotation_to_dict(non_none_args[0])],
            }
        # 普通的 Union 类型
        return {
            "type": "union",
            "args": [_parse_type_annotation_to_dict(arg) for arg in args],
        }

    # 处理其他泛型类型
    if args:
        return {
            "type": origin_name,
            "args": [_parse_type_annotation_to_dict(arg) for arg in args],
        }
    else:
        return {"type": origin_name}

def _extract_parameter_info(func: Callable) -> List[Dict[str, Any]]:
    """提取函数参数信息"""
    try:
        sig = inspect.signature(func)
        params_info = []
        
        for name, param in sig.parameters.items():
            # 解包 Annotated 获取基础类型与UI元信息
            base_type, meta_list = _unwrap_annotated(param.annotation)
            type_str = _parse_type_annotation(base_type)
            type_info = _parse_type_annotation_to_dict(base_type)
            default_repr = (
                repr(param.default) if param.default is not inspect.Parameter.empty 
                else None
            )
            required = param.default is inspect.Parameter.empty
            kind = str(param.kind).replace('Parameter.', '').lower()

            # 合并UI元信息：推断 < Annotated 覆盖
            inferred_ui = _infer_ui_from_type(base_type, name, default_repr) or {}
            annotated_ui = _merge_ui_meta(meta_list) or {}
            ui = {**inferred_ui, **annotated_ui} if (inferred_ui or annotated_ui) else None

            param_info = {
                'name': param.name,
                'type': type_str,
                'type_info': type_info,
                'default': default_repr,
                'required': required,
                'kind': kind,
                'ui': ui,
            }
            params_info.append(param_info)
            
        return params_info
        
    except Exception as e:
        logger.warning(f"提取函数 {func.__name__} 参数信息失败: {e}")
        return []

def task(name: str, queue: str = "default"):
    """任务注册装饰器（支持参数信息提取）"""
    def decorator(func: Callable) -> Callable:
        # 提取参数信息
        params_info = _extract_parameter_info(func)
        
        TASKS[name] = {
            'worker_name': getattr(func, 'task_name', func.__name__),
            'queue': queue,
            'func': func,
            'parameters': params_info,
            'doc': inspect.getdoc(func) or ""
        }
        
        # 记录详细的注册信息
        params_summary = ", ".join([
            f"{p['name']}:{p['type']}" + ("" if p['required'] else f"={p['default']}")
            for p in params_info
        ])
        logger.info(f"注册任务: {name} -> {TASKS[name]['worker_name']} (队列: {queue})")
        if params_info:
            logger.info(f"  参数: {params_summary}")
            
        return func
    return decorator

# 简单的访问函数
def get_worker_name(task_type: str) -> str:
    """获取worker任务名"""
    if task_type not in TASKS:
        raise ValueError(f"未知任务类型: {task_type}")
    return TASKS[task_type]['worker_name']

def get_queue(task_type: str) -> str:
    """获取队列名"""
    return TASKS.get(task_type, {}).get('queue', 'default')

def get_function(task_type: str) -> Optional[Callable]:
    """获取任务函数"""
    return TASKS.get(task_type, {}).get('func')

def get_parameters(task_type: str) -> List[Dict[str, Any]]:
    """获取任务参数信息"""
    return TASKS.get(task_type, {}).get('parameters', [])

def get_doc(task_type: str) -> str:
    """获取任务文档字符串"""
    return TASKS.get(task_type, {}).get('doc', '')

def get_task_info(task_type: str) -> Optional[Dict[str, Any]]:
    """获取完整的任务信息"""
    if task_type not in TASKS:
        return None
    
    task = TASKS[task_type]
    return {
        'name': task_type,
        'worker_name': task['worker_name'],
        'queue': task['queue'],
        'parameters': task.get('parameters', []),
        'doc': task.get('doc', ''),
        'has_parameters': len(task.get('parameters', [])) > 0
    }

def all_queues() -> Set[str]:
    """获取所有队列名"""
    queues = {t['queue'] for t in TASKS.values()}
    queues.add('default')
    return queues

def is_supported(task_type: str) -> bool:
    """检查任务是否支持"""
    return task_type in TASKS

def list_all_tasks() -> List[Dict[str, Any]]:
    """列出所有已注册任务的详细信息"""
    return [get_task_info(task_name) for task_name in TASKS.keys()]

def print_task_registry():
    """打印所有已注册任务的详细信息（用于调试）"""
    if not TASKS:
        print("没有已注册的任务")
        return
    
    print(f"\n=== 已注册任务 ({len(TASKS)} 个) ===")
    for task_name, task_info in TASKS.items():
        print(f"\n任务名: {task_name}")
        print(f"  工作函数: {task_info['worker_name']}")
        print(f"  队列: {task_info['queue']}")
        
        if task_info.get('doc'):
            print(f"  文档: {task_info['doc']}")
        
        params = task_info.get('parameters', [])
        if params:
            print(f"  参数 ({len(params)} 个):")
            for param in params:
                required_text = "必需" if param['required'] else f"默认值: {param['default']}"
                print(f"    - {param['name']} ({param['type']}) - {required_text}")
        else:
            print("  参数: 无")
    print("=" * 50) 

# 保留必要的枚举
 

class SchedulerType(str, Enum):
    """调度器类型枚举"""
    CRON = "cron"
    DATE = "date"
    MANUAL = "manual"

class ScheduleAction(str, Enum):
    """调度操作类型枚举"""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RELOAD = "reload"

# 工具函数
def make_job_id(task_type: str, config_id: int) -> str:
    """生成job_id"""
    return f"{task_type}_{config_id}"

def extract_config_id(job_id: str) -> Optional[int]:
    """从job_id提取config_id"""
    try:
        return int(job_id.split('_')[-1])
    except (ValueError, IndexError):
        return None

def auto_discover_tasks(package_path: str = "app.modules.tasks.workers"):
    """
    自动发现并导入所有任务模块
    
    Args:
        package_path: 任务包路径
    """
    try:
        # 导入任务包
        package = importlib.import_module(package_path)
        
        # 遍历包中的所有模块
        for importer, modname, ispkg in pkgutil.iter_modules(
            package.__path__, 
            prefix=package.__name__ + "."
        ):
            if not ispkg:  # 只导入模块，不导入子包
                try:
                    importlib.import_module(modname)
                    logger.info(f"自动导入任务模块: {modname}")
                except Exception as e:
                    logger.warning(f"导入任务模块 {modname} 失败: {e}")
        
        logger.info(f"任务自动发现完成，共注册 {len(TASKS)} 个任务: {list(TASKS.keys())}")
        
        # 显示每个任务的详细参数信息（调试模式）
        for task_name in TASKS.keys():
            task_info = TASKS[task_name]
            params = task_info.get('parameters', [])
            if params:
                params_summary = ", ".join([
                    f"{p['name']}:{p['type']}" + ("" if p['required'] else f"={p['default']}")
                    for p in params
                ])
                logger.debug(f"  {task_name} 参数: {params_summary}")
            else:
                logger.debug(f"  {task_name} 参数: 无")
        
    except Exception as e:
        logger.error(f"任务自动发现失败: {e}")
        raise
