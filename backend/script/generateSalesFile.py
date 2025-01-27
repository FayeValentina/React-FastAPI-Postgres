import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import math

# 获取脚本所在目录的绝对路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def read_txt_file(filename):
    """读取txt文件内容"""
    file_path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        raise
    except Exception as e:
        print(f"读取{filename}时发生错误：{str(e)}")
        raise

def read_relation_mapping():
    """读取关系映射文件"""
    relation_path = os.path.join(SCRIPT_DIR, 'relation.csv')
    try:
        df = pd.read_csv(relation_path)
        # 创建映射字典
        sales_unit_to_company = dict(zip(df['SALES_UNIT'], df['COMPANY_CODE']))
        sales_unit_to_currency = dict(zip(df['SALES_UNIT'], df['CURRENCY']))
        return df['SALES_UNIT'].tolist(), sales_unit_to_company, sales_unit_to_currency
    except Exception as e:
        print(f"读取relation.csv时发生错误：{str(e)}")
        raise

def generate_invoice_num(index):
    """生成唯一的订单编号"""
    return f"TBC{str(index).zfill(10)}"

def calculate_records_per_customer(total_records, num_customers, months):
    """计算每个客户每月平均应该生成多少条记录"""
    records_per_customer = total_records / num_customers / months
    return max(1, math.floor(records_per_customer))

def get_next_month_date(current_date):
    """获取下个月的第一天"""
    if current_date.month == 12:
        return datetime(current_date.year + 1, 1, 1)
    else:
        return datetime(current_date.year, current_date.month + 1, 1)

def generate_monthly_dates(start_date, end_date, records_per_month):
    """为每月生成指定数量的日期"""
    dates = []
    current_date = start_date
    
    while current_date <= end_date:
        # 计算当月的最后一天
        next_month = get_next_month_date(current_date)
        month_end = min(end_date, next_month - timedelta(days=1))
        
        # 在当月随机选择指定数量的天数
        for _ in range(records_per_month):
            random_day = current_date + timedelta(days=np.random.randint((month_end - current_date).days + 1))
            dates.append(random_day)
        
        # 移到下个月
        current_date = next_month
    
    return dates

def generate_sales_data(total_records=200000):
    # 读取数据
    CUSTOMER_NOS = read_txt_file('CUSTOMER_NO.txt')
    SEG5S = read_txt_file('SEG5.txt')
    
    # 读取关系映射
    SALES_UNITS, sales_unit_to_company, sales_unit_to_currency = read_relation_mapping()
    
    # 设置日期范围
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 6, 30)
    
    # 计算月份数
    months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
    
    # 计算每个客户每月应生成的记录数
    records_per_month = calculate_records_per_customer(total_records, len(CUSTOMER_NOS), months)
    
    # 生成数据列表
    data = []
    invoice_counter = 1
    
    # 为每个客户生成数据
    for customer_no in CUSTOMER_NOS:
        # 生成该客户的所有日期
        dates = generate_monthly_dates(start_date, end_date, records_per_month)
        
        for date in dates:
            # 先选择 SALES_UNIT，然后根据映射获取对应的 COMPANY_CODE 和 CURRENCY
            sales_unit = np.random.choice(SALES_UNITS)
            company_code = sales_unit_to_company[sales_unit]
            currency = sales_unit_to_currency[sales_unit]
            
            # 生成一条记录
            record = {
                'CUSTOMER_NO': customer_no,
                'INVOICE_DATE': date,
                'ORDER_DATE': date,
                'OPEN_AMT': np.random.randint(1000,100001),
                'OPEN_QTY': np.random.randint(1000,10001),
                'SALES_AMT': np.random.randint(1000, 100001),
                'INVOICE_NUM': generate_invoice_num(invoice_counter),
                'SALES_QTY': np.random.randint(1000, 10001),
                'PACKED_QTY': np.random.randint(1000, 10001),
                'SALES_UNIT': sales_unit,
                'STD_COST_AMT': np.random.randint(1000, 100001),
                'SALES_AMT_ORG': np.random.randint(1000, 100001),
                'CURRENCY': currency,
                'SEG5': np.random.choice(SEG5S),
                'COMPANY_CODE': company_code
            }
            data.append(record)
            invoice_counter += 1
            
            if len(data) >= total_records:
                break
        if len(data) >= total_records:
            break
    
    # 创建DataFrame
    df = pd.DataFrame(data)
    
    # 如果生成的记录数超过要求，只保留指定数量
    if len(df) > total_records:
        df = df.head(total_records)
    
    # 按INVOICE_DATE排序
    df = df.sort_values('INVOICE_DATE')
    
    return df

def main():
    # 设置要生成的记录总数
    total_records = 220000
    print(f"开始生成{total_records}条数据...")
    
    # 生成数据
    df = generate_sales_data(total_records)
    
    # 保存为CSV文件
    output_path = os.path.join(SCRIPT_DIR, 'sales_data.csv')
    print(f"保存数据到CSV文件: {output_path}")
    df.to_csv(output_path, index=False)
    
    # 输出统计信息
    print(f"实际生成记录数: {len(df)}")
    print(f"客户数量: {df['CUSTOMER_NO'].nunique()}")
    print(f"日期范围: {df['INVOICE_DATE'].min()} 到 {df['INVOICE_DATE'].max()}")
    
    # 验证每个客户每月是否都有数据
    df['YearMonth'] = df['INVOICE_DATE'].dt.to_period('M')
    customer_monthly_counts = df.groupby(['CUSTOMER_NO', 'YearMonth']).size()
    min_records_per_customer_month = customer_monthly_counts.min()
    print(f"每个客户每月最少记录数: {min_records_per_customer_month}")
    print("数据生成完成！")

if __name__ == "__main__":
    main()