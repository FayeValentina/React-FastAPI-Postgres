import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# 获取脚本所在目录的绝对路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_sales_data(num_records=1000000):
    # 定义常量
    CURRENCIES = ['AUD', 'CAD', 'DKK', 'EUR', 'GBP', 'HKD', 'INR', 'JPY', 'KRW', 'RMB', 'SEK', 'SGD', 'THB', 'TWD', 'USD']
    
    # 从文件读取商品分类列表
    seg3_path = os.path.join(SCRIPT_DIR, 'seg3.txt')
    try:
        with open(seg3_path, 'r', encoding='utf-8') as f:
            SEG3_CATEGORIES = [line.strip() for line in f if line.strip()]
        print(f"成功读取了 {len(SEG3_CATEGORIES)} 个商品分类")
    except FileNotFoundError:
        print(f"错误：找不到文件 {seg3_path}")
        raise
    except Exception as e:
        print(f"读取seg3.txt时发生错误：{str(e)}")
        raise

    # 生成日期范围
    start_date = datetime(2005, 1, 1)
    end_date = datetime(2023, 12, 31)
    days_range = (end_date - start_date).days
    
    # 生成随机数据
    sales_dates = [start_date + timedelta(days=np.random.randint(0, days_range)) for _ in range(num_records)]
    planned_sales_volume = np.random.randint(100, 10000, num_records)
    
    # 生成实际销售量（计划销售量的50%-150%）
    actual_sales_volume = planned_sales_volume * np.random.uniform(0.5, 1.5, num_records)
    
    # 生成计划单价
    planned_unit_price = np.random.uniform(10, 1000, num_records)
    
    # 生成实际单价（计划单价的80%-120%）
    actual_unit_price = planned_unit_price * np.random.uniform(0.8, 1.2, num_records)
    
    # 生成其他随机数据
    standard_cost = np.random.uniform(5, 800, num_records)
    currencies = np.random.choice(CURRENCIES, num_records)
    seg3_categories = np.random.choice(SEG3_CATEGORIES, num_records)

    # 创建DataFrame
    df = pd.DataFrame({
        'SALES_DATE': sales_dates,
        'PLANNED_SALES_VOLUME': planned_sales_volume,
        'ACTUAL_SALES_VOLUME': actual_sales_volume,
        'PLANNED_UNIT_PRICE': planned_unit_price,
        'ACTUAL_UNIT_PRICE': actual_unit_price,
        'STD_COST_AMOUNT': standard_cost,
        'SEG3': seg3_categories,
        'CURRENCY': currencies
    })

    # 格式化数值列，保留2位小数
    float_columns = ['ACTUAL_SALES_VOLUME', 'PLANNED_UNIT_PRICE', 'ACTUAL_UNIT_PRICE', 'STD_COST_AMOUNT']
    df[float_columns] = df[float_columns].round(2)

    return df

def main():
    # 生成数据
    print("开始生成数据...")
    df = generate_sales_data()

    # 保存为CSV文件（推荐）
    output_path = os.path.join(SCRIPT_DIR, 'sales_data.csv')
    print(f"保存数据到CSV文件: {output_path}")
    df.to_csv(output_path, index=False)

    print("数据生成完成！")

if __name__ == "__main__":
    main()