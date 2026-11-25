import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import engine, Base
from backend.app.models.models import (
    PropertyImage, PropertyFeature, PropertyOffer, AIConversationState
)

def run_migration():
    print("Creating V2 tables if they don't exist...")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            PropertyImage.__table__,
            PropertyFeature.__table__,
            PropertyOffer.__table__,
            AIConversationState.__table__,
        ]
    )
    print("V2 tables created successfully.")

if __name__ == "__main__":
    run_migration()

