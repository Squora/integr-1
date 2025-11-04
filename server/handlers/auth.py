from passlib.context import CryptContext
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def handle_login(db, username, password):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return {"error": "Invalid credentials"}
    return {"status": "logged in", "role": user.role}