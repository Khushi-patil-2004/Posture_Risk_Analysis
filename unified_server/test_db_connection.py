"""Quick test to check database connection and demo_user"""
import database
import auth
from sqlalchemy import select

def test_connection():
    """Test basic database connectivity"""
    print("Testing database connection...")
    try:
        conn = database.get_connection()
        print("✅ Database connection successful!")
        
        # Check if demo_user exists
        query = select(database.users_table).where(
            database.users_table.c.username == "demo_user"
        )
        result = conn.execute(query).fetchone()
        conn.close()
        
        if result:
            print(f"✅ demo_user exists! ID: {result[0]}")
            print(f"   Username: {result[1]}")
            print(f"   Password hash: {result[2][:20]}...")
            
            # Test password verification
            is_valid = auth.verify_password("demo123", result[2])
            print(f"   Password 'demo123' valid: {is_valid}")
            
            return True
        else:
            print("❌ demo_user NOT FOUND in database!")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_connection()
