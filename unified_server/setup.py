# Setup Script for Unified Posture Analysis Server
# Run this script to initialize the system

import sys
import subprocess
from database import init_database, test_connection, drop_all_tables
from auth import create_test_user
import logger

def install_dependencies():
    """Install Python dependencies"""
    logger.log_lifecycle("SETUP", "Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        logger.log_success("Dependencies Installed", {})
        return True
    except Exception as e:
        logger.log_error("Dependency Installation Failed", e)
        return False


def setup_database(fresh_start=False):
    """Initialize database"""
    logger.log_lifecycle("SETUP", "Setting up database...")
    
    # Test connection
    if not test_connection():
        logger.log_error("Database Setup Failed", Exception("Cannot connect to database"))
        return False
    
    # Drop all tables if fresh start
    if fresh_start:
        logger.log_warning("Fresh Start", {"action": "Dropping all tables"})
        drop_all_tables()
    
    # Create tables
    if not init_database():
        return False
    
    logger.log_success("Database Ready", {})
    return True


def create_default_user():
    """Create default test user"""
    logger.log_lifecycle("SETUP", "Creating test user...")
    
    success, user_id = create_test_user()
    
    if success:
        logger.log_success("Test User Ready", {
            "username": "demo_user",
            "password": "test123",
            "user_id": user_id
        })
    
    return success


def main():
    """Main setup function"""
    logger.log_lifecycle("SETUP START", "Unified Posture Analysis Server")
    
    print("\n" + "="*80)
    print("UNIFIED POSTURE ANALYSIS SERVER - SETUP")
    print("="*80 + "\n")
    
    print("1. Install dependencies? (y/n): ", end="")
    if input().lower() == 'y':
        install_dependencies()
    
    print("\n2. Fresh database setup (drops existing tables)? (y/n): ", end="")
    fresh = input().lower() == 'y'
    
    if not setup_database(fresh_start=fresh):
        print("\n❌ Setup failed!")
        return
    
    print("\n3. Create test user (demo_user / test123)? (y/n): ", end="")
    if input().lower() == 'y':
        create_default_user()
    
    logger.log_lifecycle("SETUP COMPLETE", "")
    
    print("\n" + "="*80)
    print("✅ SETUP COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("  1. Run server: uvicorn main:app --reload --port 8000")
    print("  2. Access API docs: http://localhost:8000/docs")
    print("  3. Login with: username='demo_user', password='test123'")
    print("\n")


if __name__ == "__main__":
    main()
