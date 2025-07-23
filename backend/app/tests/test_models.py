from app.db.base import SessionLocal
from app.models import User, Post # type: ignore
from app.core.security import get_password_hash # type: ignore


def clean_test_data():
    db = SessionLocal()
    try:
        # 清理所有测试数据
        db.query(Post).delete()
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
        
        # 为用户创建文章
        post1 = Post(
            title="First Post",
            content="This is the first test post content",
            summary="First test post",
            published=True,
            author_id=user1.id
        )
        post2 = Post(
            title="Second Post",
            content="This is the second test post content",
            summary="Second test post",
            published=True,
            author_id=user1.id
        )
        post3 = Post(
            title="User 2's Post",
            content="This is a post by user 2",
            summary="Test post by user 2",
            published=True,
            author_id=user2.id
        )
        db.add_all([post1, post2, post3])
        db.commit()

        # 测试关系
        print("\n=== 测试数据创建成功 ===")
        print(f"User 1: {user1.username}")
        print(f"User 1's posts: {len(user1.posts)}")
        for post in user1.posts:
            print(f"- {post.title}")
        
        print(f"\nUser 2: {user2.username}")
        print(f"User 2's posts: {len(user2.posts)}")
        for post in user2.posts:
            print(f"- {post.title}")

    except Exception as e:
        print(f"Error: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    clean_test_data()  # 先清理数据
    create_test_data() 