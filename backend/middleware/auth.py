from fastapi import Header, HTTPException
import os

ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', '2a-immobilier-admin-key-2024-secure')

async def verify_admin_key(x_api_key: str = Header(None)):
    '''Vérifie la clé API admin'''
    if not x_api_key or x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail='Clé API admin invalide')
    return True
