from sqlalchemy import text # type: ignore
from app.db.base import engine # type: ignore

def test_database_connection():
    try:
        # 尝试连接数据库并执行简单查询
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("数据库连接成功!")
            return True
    except Exception as e:
        print(f"数据库连接失败: {str(e)}")
        return False

if __name__ == "__main__":
    test_database_connection() 