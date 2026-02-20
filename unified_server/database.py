# Database Module - SQLAlchemy Core (Procedural, No ORM Classes)
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, text, UniqueConstraint
from sqlalchemy.sql import func
from datetime import datetime
import config

# Create engine - Convert postgresql:// to postgresql+psycopg:// for psycopg3
database_url = config.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(database_url, echo=False, pool_pre_ping=True)
metadata = MetaData()

# Table Definitions

# Users Table (Team 3 - User Management)
users_table = Table(
    'users',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('username', String(100), unique=True, nullable=False, index=True),
    Column('password_hash', String(255), nullable=False),
    Column('age', Integer, nullable=True),
    Column('height_cm', Integer, nullable=True),
    Column('weight_kg', Integer, nullable=True),
    Column('created_at', DateTime, server_default=func.now()),
)

# Sessions Table
sessions_table = Table(
    'sessions',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False, index=True),
    Column('start_time', DateTime, nullable=False),
    Column('end_time', DateTime, nullable=True),
    Column('current_phase', String(20), default='front'),  # front, side, completed
    Column('phase_start_time', DateTime, nullable=True),
    Column('expected_end_time', DateTime, nullable=True),
    Column('avg_fps', Float, nullable=True),
    Column('total_frames', Integer, default=0),
    Column('status', String(20), default='active'),  # active, completed, failed
)

# Raw Angles Table (Team 1 - Data Stream)
raw_angles_table = Table(
    'raw_angles',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('session_id', Integer, ForeignKey('sessions.id'), nullable=False, index=True),
    Column('frame_id', Integer, nullable=False),
    Column('camera_angle', String(10), nullable=False),  # FRONT or SIDE
    Column('angle_data', JSON, nullable=False),  # {neck_bend: 15.2, shoulder_slope: 3.4, ...}
    Column('confidence_data', JSON, nullable=False),  # {neck_bend: 0.95, shoulder_slope: 0.88, ...}
    Column('is_calibrated', Boolean, default=True),
    Column('fps_at_frame', Float, nullable=True),  # Dynamic FPS calculated for this frame
    Column('timestamp_iso', String(50), nullable=False),  # ISO timestamp from Team 1
    Column('timestamp_ms', Float, nullable=False, index=True),  # Unix timestamp in milliseconds
)

# Posture Results Table (Team 2 - Scoring Output)
posture_results_table = Table(
    'posture_results',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('session_id', Integer, ForeignKey('sessions.id'), nullable=False, index=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False, index=True),
    Column('metric_name', String(50), nullable=False),  # e.g., FRONT_neck_bend
    Column('risk_percent', Integer, nullable=False),
    Column('status', String(20), nullable=False),  # Good posture, Moderate risk, High risk
    Column('time_good_min', Float, default=0),
    Column('time_warning_min', Float, default=0),
    Column('time_bad_min', Float, default=0),
    Column('calculated_at', DateTime, server_default=func.now()),
)

# Recommendations Table (Team 2 - AI Output)
recommendations_table = Table(
    'recommendations',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('session_id', Integer, ForeignKey('sessions.id'), nullable=False, index=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False, index=True),
    Column('recommendation_text', Text, nullable=False),
    Column('priority', String(20), nullable=False),  # LOW, MEDIUM, HIGH
    Column('dominant_issue', String(50), nullable=True),
    Column('risk_level', String(20), nullable=True),  # LOW, MODERATE, HIGH
    Column('actions_json', JSON, nullable=True),  # List of actionable items
    Column('created_at', DateTime, server_default=func.now()),
)

# Angle Accumulation Table (Team 2 - Time per Unique Angle)
# Angle Accumulation Table (Team 2 - Time Distribution)
angle_accumulation_table = Table(
    'angle_accumulation',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('session_id', Integer, ForeignKey('sessions.id'), nullable=False, index=True),
    Column('camera_angle', String(10), nullable=False),  # FRONT or SIDE
    Column('metric_name', String(50), nullable=False),  # neck_bend, shoulder_slope, etc.
    Column('angle_value', Integer, nullable=False),  # Rounded to integer (15, 16, 17, ...)
    Column('total_time_seconds', Float, default=0),  # Accumulated time at this angle
    UniqueConstraint('session_id', 'camera_angle', 'metric_name', 'angle_value',
                     name='uq_angle_accumulation')  # For efficient upserts
)


# Database Initialization Functions

def init_database():
    """Create all tables if they don't exist"""
    try:
        metadata.create_all(engine)
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


def test_connection():
    """Test database connectivity"""
    try:
        with engine.connect() as conn:
            result = conn.execute(func.now())
            print(f"✅ Database connected successfully at {result.scalar()}")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def drop_all_tables():
    """Drop all tables managed by this metadata (use with caution!)"""
    try:
        # Use CASCADE to drop dependent objects
        metadata.drop_all(engine, checkfirst=True)
        print("⚠️  All managed tables dropped")
        return True
    except Exception as e:
        print(f"❌ Failed to drop tables: {e}")
        print("⚠️  Attempting manual CASCADE drop...")
        
        # Manual CASCADE drop for tables with dependencies
        try:
            with engine.connect() as conn:
                # Drop all tables including those from other projects
                table_names = ['video_uploads', 'extension_links', 'detection_sessions', 'recommendations', 'posture_results', 'angle_accumulation', 'raw_angles', 'sessions', 'users']
                for table_name in table_names:
                    try:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                        conn.commit()
                        print(f"  ✓ Dropped {table_name}")
                    except Exception as table_err:
                        print(f"  ✗ Could not drop {table_name}: {table_err}")
                
                print("⚠️  Manual CASCADE drop complete")
                return True
        except Exception as cascade_err:
            print(f"❌ Manual CASCADE drop failed: {cascade_err}")
            return False


def get_connection():
    """Get a database connection"""
    return engine.connect()
