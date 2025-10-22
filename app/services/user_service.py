from sqlalchemy.orm import Session
from app.models.user import User,UserLLMConfig, LLMProvider, LLMModel
from app.core.security import azure_ad_dependency
from app.db.session import get_db
from datetime import datetime, timezone
from app.core.config import settings
import os
import logging
import time

log_file = "logs/upload.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

logger = logging.getLogger(__name__)
def get_or_create_user(db: Session, current_user: dict):
    """
    Get or create a user based on Azure AD token data.
    """
    user_email = current_user.get("UserEmail")
    object_id = current_user.get("ObjectId")

    # Check if user exists by email or object ID
    user = db.query(User).filter(
        (User.UserEmail == user_email) | (User.ObjectId == object_id)
    ).first()

    if not user:
        logger.info(f"Creating new user: {user_email}")
        user = User(
            UserEmail=user_email,
            UserName=current_user.get("UserName"),
            ObjectId=object_id,
            UserType=current_user.get("UserType", "User"),
            RecordStatus='A',
            CreatedAt=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user

def create_default_llm_config_if_not_exists(db: Session, user):
    """
    Creates a default LLM config entry for the user if none exists.
    Looks up ProviderId and ModelId from default .env values.
    """

    # Check if config already exists
    existing_config = db.query(UserLLMConfig).filter(UserLLMConfig.UserId == user.UserId).first()
    if existing_config:
        return existing_config
    # Load default values from .env
    default_model_name = settings.AZURE_OPENAI_DEPLOYMENT_NAME
    default_provider_name = settings.LLMProvider

    # Look up ProviderId
    provider = db.query(LLMProvider).filter(LLMProvider.Name == default_provider_name).first()
    if not provider:
        raise ValueError(f"Provider '{default_provider_name}' not found in LLMProvider table.")
    #print(f"Provider: {provider.Name}, ID: {provider.Id}")
    # Look up ModelId
    model = db.query(LLMModel).filter(LLMModel.ModelName == default_model_name).first()
    if not model:
        raise ValueError(f"Model '{default_model_name}' not found in LLMModel table.")
    #print(f"Model: {model.ModelName}, ID: {model.Id}")
    # Create new config
    config = UserLLMConfig(
        UserId=user.UserId,
        ProviderId=provider.Id,
        ModelId=model.Id,
        CreatedAt=datetime.now(timezone.utc)
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return config