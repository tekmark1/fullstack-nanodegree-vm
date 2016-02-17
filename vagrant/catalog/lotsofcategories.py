from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Category, Base, Item, User

engine = create_engine('sqlite:///catalog.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)


session = DBSession()


# Create dummy user
User1 = User(name="Robo Barista", email="example@udacity.com")
session.add(User1)
session.commit()

# create Basektball Category
category1 = Category(user_id=1, name="Basketball")

session.add(category1)
session.commit()

# create Head Band item for Basketball category
item2 = Item(user_id=1, name="Head Band", description="Perfect for keeping the sweat out of your eyes", category=category1)

session.add(item2)
session.commit()





print "added menu items!"