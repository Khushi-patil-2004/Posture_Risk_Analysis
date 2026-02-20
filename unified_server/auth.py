# Authentication Module - JWT-based Auth (Procedural)
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from sqlalchemy import select, insert, update
import config
from database import users_table, get_connection
import logger


def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return hash_password(plain_password) == hashed_password


def create_jwt_token(user_id: int, username: str) -> str:
    """
    Create JWT token for user
    
    Args:
        user_id: User's database ID
        username: Username
        
    Returns:
        JWT token string
    """
    expiration = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
    
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": expiration,
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    
    logger.log_auth("JWT Token Created", {
        "user_id": user_id,
        "username": username,
        "expires_at": expiration.isoformat()
    })
    
    return token


def decode_jwt_token(token: str) -> Optional[Dict]:
    """
    Decode and verify JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.log_error("JWT Decode Failed", Exception("Token expired"))
        return None
    except jwt.InvalidTokenError as e:
        logger.log_error("JWT Decode Failed", e)
        return None


def extract_user_id(token: str) -> Optional[int]:
    """
    Extract user ID from JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        User ID or None if invalid
    """
    payload = decode_jwt_token(token)
    if payload:
        return payload.get("user_id")
    return None


def register_user(username: str, password: str, age: Optional[int] = None, 
                 height_cm: Optional[int] = None, weight_kg: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
    """
    Register a new user
    
    Args:
        username: Desired username
        password: Plain text password
        age: User's age
        height_cm: User's height in cm
        weight_kg: User's weight in kg
        
    Returns:
        Tuple of (success: bool, message: str, user_id: Optional[int])
    """
    try:
        conn = get_connection()
        
        # Check if username already exists
        check_query = select(users_table).where(users_table.c.username == username)
        result = conn.execute(check_query).first()
        
        if result:
            logger.log_warning("Registration Failed", {"username": username, "reason": "Username already exists"})
            conn.close()
            return False, "Username already exists", None
        
        # Insert new user
        password_hash = hash_password(password)
        insert_query = insert(users_table).values(
            username=username,
            password_hash=password_hash,
            age=age,
            height_cm=height_cm,
            weight_kg=weight_kg
        )
        
        result = conn.execute(insert_query)
        conn.commit()
        user_id = result.inserted_primary_key[0]
        
        logger.log_auth("User Registered", {
            "user_id": user_id,
            "username": username,
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg
        })
        
        conn.close()
        return True, "User registered successfully", user_id
        
    except Exception as e:
        logger.log_error("Registration Failed", e, {"username": username})
        return False, f"Registration error: {str(e)}", None


def login_user(username: str, password: str) -> Tuple[bool, str, Optional[str], Optional[Dict]]:
    """
    Authenticate user and generate JWT token
    
    Args:
        username: Username
        password: Plain text password
        
    Returns:
        Tuple of (success: bool, message: str, token: Optional[str], user_data: Optional[Dict])
    """
    try:
        conn = get_connection()
        
        # Fetch user
        query = select(users_table).where(users_table.c.username == username)
        result = conn.execute(query).first()
        
        if not result:
            logger.log_warning("Login Failed", {"username": username, "reason": "User not found"})
            conn.close()
            return False, "Invalid credentials", None, None
        
        # Verify password
        user_dict = dict(result._mapping)
        if not verify_password(password, user_dict['password_hash']):
            logger.log_warning("Login Failed", {"username": username, "reason": "Incorrect password"})
            conn.close()
            return False, "Invalid credentials", None, None
        
        # Generate token
        token = create_jwt_token(user_dict['id'], username)
        
        user_data = {
            "id": user_dict['id'],
            "username": user_dict['username'],
            "age": user_dict['age'],
            "height_cm": user_dict['height_cm'],
            "weight_kg": user_dict['weight_kg']
        }
        
        logger.log_auth("Login Successful", {
            "user_id": user_dict['id'],
            "username": username
        })
        
        conn.close()
        return True, "Login successful", token, user_data
        
    except Exception as e:
        logger.log_error("Login Failed", e, {"username": username})
        return False, f"Login error: {str(e)}", None, None


def get_user_profile(user_id: int) -> Optional[Dict]:
    """
    Fetch user profile by ID
    
    Args:
        user_id: User's database ID
        
    Returns:
        User profile dict or None if not found
    """
    try:
        conn = get_connection()
        
        query = select(users_table).where(users_table.c.id == user_id)
        result = conn.execute(query).first()
        
        if not result:
            conn.close()
            return None
        
        user_dict = dict(result._mapping)
        profile = {
            "id": user_dict['id'],
            "username": user_dict['username'],
            "age": user_dict['age'],
            "height_cm": user_dict['height_cm'],
            "weight_kg": user_dict['weight_kg'],
            "created_at": user_dict['created_at'].isoformat() if user_dict['created_at'] else None
        }
        
        logger.log_db("User Profile Fetched", {"user_id": user_id})
        
        conn.close()
        return profile
        
    except Exception as e:
        logger.log_error("Profile Fetch Failed", e, {"user_id": user_id})
        return None


def update_user_profile(user_id: int, age: Optional[int] = None, 
                       height_cm: Optional[int] = None, weight_kg: Optional[int] = None) -> Tuple[bool, str]:
    """
    Update user profile
    
    Args:
        user_id: User's database ID
        age: New age (optional)
        height_cm: New height in cm (optional)
        weight_kg: New weight in kg (optional)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        conn = get_connection()
        
        updates = {}
        if age is not None:
            updates['age'] = age
        if height_cm is not None:
            updates['height_cm'] = height_cm
        if weight_kg is not None:
            updates['weight_kg'] = weight_kg
        
        if not updates:
            conn.close()
            return False, "No updates provided"
        
        query = update(users_table).where(users_table.c.id == user_id).values(**updates)
        conn.execute(query)
        conn.commit()
        
        logger.log_auth("Profile Updated", {
            "user_id": user_id,
            **updates
        })
        
        conn.close()
        return True, "Profile updated successfully"
        
    except Exception as e:
        logger.log_error("Profile Update Failed", e, {"user_id": user_id})
        return False, f"Update error: {str(e)}"


# Helper function to create default test user
def create_test_user():
    """Create a default test user for development"""
    success, message, user_id = register_user(
        username="demo_user",
        password="test123",
        age=28,
        height_cm=170,
        weight_kg=65
    )
    
    if success:
        logger.log_success("Test User Created", {
            "username": "demo_user",
            "password": "test123",
            "user_id": user_id
        })
    else:
        logger.log_warning("Test User Creation", {"message": message})
    
    return success, user_id
