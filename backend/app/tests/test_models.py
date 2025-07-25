from app.db.base import SessionLocal
from app.models import User
from app.core.security import get_password_hash


def clean_test_data():
    db = SessionLocal()
    try:
        # 清理所有测试数据
        db.query(User).delete()
        db.commit()
        print("测试数据已清理")
    except Exception as e:
        print(f"清理数据时出错: {str(e)}")
        db.rollback()
    finally:
        db.close()


def create_test_data():
    db = SessionLocal()
    try:
        # 创建测试用户
        user1 = User(
            email="test1@example.com",
            username="testuser1",
            hashed_password=get_password_hash("password123"),
            full_name="Test User 1",
            is_active=True
        )
        user2 = User(
            email="test2@example.com",
            username="testuser2",
            hashed_password=get_password_hash("password123"),
            full_name="Test User 2",
            is_active=True
        )
        db.add_all([user1, user2])
        db.commit()

        # 测试用户创建
        print("\n=== 测试数据创建成功 ===")
        print(f"User 1: {user1.username} - {user1.email}")
        print(f"User 2: {user2.username} - {user2.email}")

    except Exception as e:
        print(f"Error: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    clean_test_data()  # 先清理数据
    create_test_data() 