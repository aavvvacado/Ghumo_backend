from app.database.session import engine
from app.database.models import LocalContribution

LocalContribution.__table__.create(engine, checkfirst=True)
print("LocalContribution table created.")
