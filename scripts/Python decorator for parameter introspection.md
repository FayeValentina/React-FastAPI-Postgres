当然，这里有一份详细的 Markdown 文档，解释了如何通过编写一个 Python 装饰器来获取函数的参数名、注解（类型提示）和默认值，并且特别强调了如何解析和解构复杂的嵌套类型参数。

-----

# Python 装饰器高级用法：获取并解构函数参数

本文档将详细介绍如何创建一个 Python 装饰器，用于在运行时动态地获取函数的参数信息，包括参数的**名称**、**类型注解**和**默认值**。我们还将探讨如何处理并“解构”复杂的嵌套类型注解，例如 `List[Dict[str, int]]`。

## 1\. 核心概念：`inspect` 模块

Python 的标准库 `inspect` 是实现这一功能的关键。它允许我们在程序运行时“检查”活动对象，如模块、类和函数。

我们将主要使用以下两个组件：

  - `inspect.signature(func)`: 这个函数返回一个 `Signature` 对象，它代表了指定函数的调用签名。
  - `Signature.parameters`: 这是一个有序字典，将参数名映射到 `Parameter` 对象。

每个 `Parameter` 对象都包含了关于单个参数的所有信息：

  - `Parameter.name`: 参数的名称 (字符串)。
  - `Parameter.annotation`: 参数的类型注解。如果未提供，其值为 `inspect.Parameter.empty`。
  - `Parameter.default`: 参数的默认值。如果参数没有默认值，其值为 `inspect.Parameter.empty`。
  - `Parameter.kind`: 参数的种类（例如，位置或关键字、仅关键字、可变参数 `*args` 等）。

## 2\. 基础：获取参数的基本信息

让我们从一个可以获取参数名、注解和默认值的基本装饰器开始。

```python
import functools
import inspect

def simple_inspector(func):
    """一个获取函数参数基本信息的装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"--- 分析函数 '{func.__name__}' ---")
        sig = inspect.signature(func)
        
        for name, param in sig.parameters.items():
            param_name = param.name
            param_annot = param.annotation if param.annotation is not inspect.Parameter.empty else "未指定"
            param_default = param.default if param.default is not inspect.Parameter.empty else "无默认值"
            
            print(f"  > 参数: {param_name}")
            print(f"    - 类型注解: {param_annot}")
            print(f"    - 默认值: {param_default}")
            
        print("--- 函数执行 ---")
        return func(*args, **kwargs)
    return wrapper

@simple_inspector
def get_user_data(user_id: int, include_details: bool = True):
    return {"id": user_id, "details_included": include_details}

# 调用
get_user_data(101, include_details=False)
```

**输出:**

```text
--- 分析函数 'get_user_data' ---
  > 参数: user_id
    - 类型注解: <class 'int'>
    - 默认值: 无默认值
  > 参数: include_details
    - 类型注解: <class 'bool'>
    - 默认值: True
--- 函数执行 ---
```

这个装饰器已经很不错了，但如果类型注解是 `List[str]` 这样的泛型，它只会打印 `typing.List[str]`，而不会深入其内部结构。

## 3\. 进阶：解构嵌套的复杂类型

当参数的类型注解是复杂的嵌套结构时（例如 `List[List[Dict[str, Any]]]`），我们希望能够递归地解析它。为此，我们需要 `typing` 模块的帮助。

  - `typing.get_origin(tp)`: 获取泛型类型的“根”容器。例如，对于 `List[int]`，它返回 `list`。
  - `typing.get_args(tp)`: 获取泛型类型的内部参数元组。例如，对于 `List[int]`，它返回 `(int,)`。

我们可以编写一个递归函数来逐层“剥开”类型注解。

## 4\. 最终实现：功能完备的参数分析装饰器

现在，我们将所有功能整合到一个装饰器中。它不仅能获取基本信息，还能递归解构复杂的类型注解。

```python
import functools
import inspect
from typing import List, Dict, Any, Union, get_origin, get_args

def _recursive_parse_type(type_hint, indent=0):
    """一个递归的辅助函数，用于格式化和打印嵌套类型。"""
    prefix = "    " * indent
    origin = get_origin(type_hint)
    args = get_args(type_hint)
    
    # 如果是基本类型或无参数的泛型，直接返回其名称
    if not origin:
        type_name = getattr(type_hint, '__name__', str(type_hint))
        return f"{prefix}{type_name}"

    # 如果是泛型类型，则递归解析
    origin_name = getattr(origin, '__name__', str(origin))
    inner_types = ", ".join([_recursive_parse_type(arg) for arg in args])
    
    # 特殊处理 Union 类型以提高可读性
    if origin is Union:
        inner_types = " | ".join([_recursive_parse_type(arg) for arg in args])
        return f"{prefix}({inner_types})"

    return f"{prefix}{origin_name}[{inner_types}]"


def detailed_inspector(func):
    """
    一个功能完备的装饰器，用于获取并解构函数参数的
    名称、注解和默认值。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"--- 详细分析函数 '{func.__name__}' ---")
        sig = inspect.signature(func)
        
        if not sig.parameters:
            print("  (该函数没有参数)")
        
        for name, param in sig.parameters.items():
            print(f"\n  > 参数: {param.name} (类型: {str(param.kind).lower()})")
            
            # 1. 解析类型注解
            if param.annotation is not inspect.Parameter.empty:
                print("    - 类型注解:")
                # 调用辅助函数来递归解析类型
                parsed_type = _recursive_parse_type(param.annotation, indent=2)
                print(parsed_type)
            else:
                print("    - 类型注解: 未指定")
            
            # 2. 获取默认值
            if param.default is not inspect.Parameter.empty:
                # 使用 repr() 来清晰地显示字符串和 None
                print(f"    - 默认值: {repr(param.default)}")
            else:
                print("    - 默认值: (必需参数)")
                
        print("\n" + ("-"*20) + " 函数执行 " + ("-"*20))
        result = func(*args, **kwargs)
        print("-" * (44 + len(" 函数执行 ")))
        return result
        
    return wrapper
```

## 5\. 示例用法与输出

让我们用一个包含各种复杂参数的函数来测试我们最终的装饰器。

```python
# 示例函数
@detailed_inspector
def process_report(
    report_id: Union[int, str], 
    data: List[Dict[str, Any]], 
    priority: int = 1,
    *,
    metadata: Dict[str, str] = None
):
    """一个处理报告的示例函数"""
    print(f"正在处理报告 #{report_id}，优先级: {priority}...")
    return {"status": "processed", "items": len(data)}

# 调用
sample_data = [{"event": "login", "user": "admin"}, {"event": "logout", "user": "admin"}]
process_report("REP-001", sample_data, metadata={"source": "api"})

```

**输出分析:**

```text
--- 详细分析函数 'process_report' ---

  > 参数: report_id (类型: positional_or_keyword)
    - 类型注解:
        (int | str)
    - 默认值: (必需参数)

  > 参数: data (类型: positional_or_keyword)
    - 类型注解:
        list[dict[str, Any]]
    - 默认值: (必需参数)

  > 参数: priority (类型: positional_or_keyword)
    - 类型注解:
        int
    - 默认值: 1

  > 参数: metadata (类型: keyword_only)
    - 类型注解:
        dict[str, str]
    - 默认值: None

-------------------- 函数执行 --------------------
正在处理报告 #REP-001，优先级: 1...
---------------------------------------------
```

从输出中可以看到：

  - **`report_id`**: 成功将 `Union[int, str]` 解构为 `(int | str)` 的易读格式。
  - **`data`**: 成功将 `List[Dict[str, Any]]` 解构为 `list[dict[str, Any]]`。
  - **`priority`**: 正确地获取了类型 `int` 和默认值 `1`。
  - **`metadata`**: 识别出它是一个仅关键字参数 (`keyword_only`)，并正确显示了其类型和默认值 `None`。

## 6\. 应用场景

这种动态分析函数签名的技术在以下场景中非常有用：

  - **API 框架 (如 FastAPI, Flask)**: 自动进行请求数据的验证、转换和文档生成。
  - **依赖注入**: 根据参数的类型注解，自动注入所需的依赖对象。
  - **数据校验层**: 在函数执行前，自动校验传入的参数是否符合类型和值的约束。
  - **调试与日志**: 自动记录函数调用时的详细参数信息，方便调试。

通过 `inspect` 模块，Python 装饰器可以变得异常强大，实现许多高级的元编程和代码自动化功能。