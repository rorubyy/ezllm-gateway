from fastapi import HTTPException, Depends, status
from utils.config_loader import config_loader
from utils.setting import settings
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def user_token_auth(api_token: str = Depends(oauth2_scheme)):
    try:
        _, user_configs = config_loader.load_configs()
        
        # Check if the api_token is valid
        if api_token not in user_configs:
            raise ValueError("Invalid user key")
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(ve)
        )
    except Exception as e:
        # Handle other potential exceptions that might occur during execution
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error: " + str(e)
        )

def master_token_auth(api_token: str = Depends(oauth2_scheme)):
    try:
        if api_token != settings.MASTER_TOKEN:
            raise ValueError("Unauthorized")

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )