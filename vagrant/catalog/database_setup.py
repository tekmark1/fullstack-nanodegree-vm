# import tools from sqlalchemy needed to create and generate datatables and relationships
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
 
Base = declarative_base()

# create table user
class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)

# create table category
# serialize this table for better readability
# establish foreignkey relationship with table user
class Category(Base):
    __tablename__ = 'category'
   
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
      """Return object data in easily serializeable format"""
      return {
        'id': self.id,
        'name': self.name,
        'user_id': self.user_id
      }

# create table item
# serialize this table for better readability
# establish foreignkey relationship with table user and table category
class Item(Base):
    __tablename__ = 'item'


    name =Column(String(80), nullable = False)
    id = Column(Integer, primary_key = True)
    description = Column(String(250))
    category_id = Column(Integer,ForeignKey('category.id'))
    category = relationship(Category)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)


    @property
    def serialize(self):
      """Return object data in easily serializeable format"""
      return {
        'id': self.id,
        'name': self.name,
        'description': self.description,
        'category_id': self.category_id,
        'user_id': self.user_id
       }


# create table
engine = create_engine('sqlite:///catalog.db')
 

Base.metadata.create_all(engine)
