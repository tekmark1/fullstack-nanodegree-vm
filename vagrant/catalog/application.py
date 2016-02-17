# import modules from flask framework tools and libraries for building the web app
# import sqlalchemy, including classes created in database_setup.py 
# import oauth2 tools to help with client authentication and authorization
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

# create instsance of Flask
app = Flask(__name__)

# connect to database created in database_setup.py
engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

# create an object (session) which allows us to perform our CRUD operations to the database
DBSession = sessionmaker(bind=engine)
session = DBSession()

# create a client_id from json data (client_id) retrieved from google signin
CLIENT_ID = json.loads(
	open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Catalog Application"

# create a randomized state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    # navigate to 'login.html'
    return render_template('login.html', STATE=state)

@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
    	response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    # display the following output if a user has successfully been logged in
    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("You are now logged in as %s." % login_session['username'])
    print "done!"
    return output

@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
        	json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
        	json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# helper function that will create a new user based upon login_session data
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

# helper function that will get a user's information based upon the inputed id
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user

# helper function that will get a user's id based upon an email address
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# return serialized JSON for a category's items 
@app.route('/catalog/<int:category_id>/item/JSON')
def categoryItemsJSON(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    items = session.query(Item).filter_by(
        category_id=category_id).all()
    return jsonify(CategoryItems=[i.serialize for i in items])

# return a serialized JSON for a given item
@app.route('/catalog/<int:category_id>/item/<int:item_id>/JSON')
def itemJSON(category_id, item_id):
    item = session.query(Item).filter_by(id=item_id).one()
    return jsonify(Item=item.serialize)

# return a serialized JSON with all of the categories in the catalog
@app.route('/catalog/JSON')
def categoriesJSON():
    categories = session.query(Category).all()
    return jsonify(categories=[c.serialize for c in categories])

# home page
# if user is not logged in, navigate to publicCatalog
# if user is logged in, navigate to the Catalog
@app.route('/')
@app.route('/catalog/')
def showCatalog():
	categories = session.query(Category).order_by(asc(Category.name))
	if 'username' not in login_session:
		return render_template('publicCatalog.html', categories=categories)
	else:
		return render_template('catalog.html', categories=categories)

# allow user to create a new category
# if user not logged int, navigate to login page
# otherwise, navigate to newCategory
# when new category is created, redirect to home page
@app.route('/catalog/new/', methods=['GET', 'POST'])
def newCategory():
	if 'username' not in login_session:
		return redirect('/login')
	if request.method == 'POST':
		newCategory = Category(name=request.form['name'], user_id=login_session['user_id'])
		session.add(newCategory)
		flash('New Category %s Successfully Created' % newCategory.name)
		session.commit()
		return redirect(url_for('showCatalog'))
	else:
		return render_template('newCategory.html')

# allow user to edit a category
# if user not logged int, navigate to login page
# if user's id does not match the login_session id (the user did not create this category) alert the user that he/she is not authorized to edit
# otherwise, navigate to editCategory
# when category is edited, redirect to home page
@app.route('/catalog/<int:category_id>/edit/', methods=['POST', 'GET'])
def editCategory(category_id):
	editedCategory = session.query(Category).filter_by(id=category_id).one()
	if 'username' not in login_session:
		return redirect('/login')
	if editedCategory.user_id != login_session['user_id']:
		return "<script>function myFunction() {alert('You are not authorized to edit this category. Please create your own category in order to edit.');}</script><body onload='myFunction()'>"
	if request.method == 'POST':
		if request.form['name']:
			editedCategory.name = request.form['name']
			flash('Your category, %s, has successfully been edited' % editedCategory.name)
			return redirect(url_for('showCatalog'))
	else:
		return render_template('editCategory.html', category=editedCategory)

# allow user to delete a category
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this category) alert the user that he/she is not authorized to delete
# otherwise, navigate to deleteCategory
# when category is delete, redirect to home page
@app.route('/catalog/<int:category_id>/delete/', methods=['POST', 'GET'])
def deleteCategory(category_id):
	deleteCategory = session.query(Category).filter_by(id=category_id).one()
	if 'username' not in login_session:
		return redirect('/login')
	if deleteCategory.user_id != login_session['user_id']:
		return "<script>function myFunction() {alert('You are not authorized to edit this category. Please create your own category in order to edit.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		session.delete(deleteCategory)
		session.commit()
		flash('You successfully deleted %s.' % deleteCategory.name)
		return redirect(url_for('showCatalog'))
	else:
		return render_template('deleteCategory.html', category=deleteCategory)

# allow user to view items for a category
# if user not logged in and
# if user's id does not match the login_session id navigate to publicItems
# otherwise, navigate to items.html
@app.route('/catalog/<int:category_id>/')
@app.route('/catalog/<int:category_id>/item/')
def showItems(category_id):
	category = session.query(Category).filter_by(id=category_id).one()
	user = getUserInfo(category.user_id)
	showItems = session.query(Item).filter_by(category_id=category_id).all()
	if 'username' not in login_session or user.id != login_session['user_id']:
		return render_template('publicItems.html', category=category, user=user, showItems=showItems)
	else:
		return render_template('items.html', category=category, user=user, showItems=showItems)

# allow user to view an item's description
# if user not logged in and
# if user's id does not match the login_session id navigate to publicItemDescription
# otherwise, navigate to itemDescription
@app.route('/catalog/<int:category_id>/item/<int:item_id>/description/')
def showItemDescription(category_id, item_id):
	category = session.query(Category).filter_by(id=category_id).one()
	item = session.query(Item).filter_by(category_id=category_id, id=item_id).one()
	user = getUserInfo(category.user_id)
	if 'username' not in login_session or user.id != login_session['user_id']:
		return render_template('publicItemDescription.html', category=category, item=item, user=user)
	else:
		return render_template('itemDescription.html', category=category, item=item, user=user)

# allow user to create new Item Description
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this item) alert the user that he/she is not authorized to add a description
# otherwise, navigate to newItemDescription
# when description is created, redirect to item description
@app.route('/catalog/<int:category_id>/item/<int:item_id>/description/new', methods=['GET', 'POST'])
def newItemDescription(category_id, item_id):
	if 'username' not in login_session:
		return redirect('/login')
	category = session.query(Category).filter_by(id=category_id).one()
	item = session.query(Item).filter_by(category_id=category_id, id=item_id).one()
	if login_session['user_id'] != category.user_id:
		return "<script>function myFunction() {alert('You are not authorized to add a description to this item. Please create your own category and item in order to add a description.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		item.description = request.form['description']
		session.add(item)
		flash('Your description has been created')
		session.commit()
		return redirect(url_for('showItemDescription', category_id=category.id, item_id=item.id))
	else:
		return render_template('newItemDescription.html', category=category, item=item)

# allow user to edit an Item Description
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this item) alert the user that he/she is not authorized to edit
# otherwise, navigate to editItemDescription
# when description is edited, redirect to item description
@app.route('/catalog/<int:category_id>/item/<int:item_id>/description/edit', methods=['GET', 'POST'])
def editItemDescription(category_id, item_id):
	if 'username' not in login_session:
		return redirect('/login')
	category = session.query(Category).filter_by(id=category_id).one()
	item = session.query(Item).filter_by(category_id=category_id, id=item_id).one()
	if login_session['user_id'] != category.user_id:
		return "<script>function myFunction() {alert('You are not authorized to add a description to this item. Please create your own category and item in order to add a description.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		item.description = request.form['description']
		session.add(item)
		flash('Your description has been edited')
		session.commit()
		return redirect(url_for('showItemDescription', category_id=category.id, item_id=item.id))
	else:
		return render_template('editItemDescription.html', category=category, item=item)

# allow user to delete an Item Description
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this item) alert the user that he/she is not authorized to delete
# otherwise, navigate to deleteItemDescription
# if description is deleted, redirect to item description
@app.route('/catalog/<int:category_id>/item/<int:item_id>/description/delete', methods=['GET', 'POST'])
def deleteItemDescription(category_id, item_id):
	category = session.query(Category).filter_by(id=category_id).one()
	item = session.query(Item).filter_by(category_id=category_id, id=item_id).one()
	if 'username' not in login_session:
		return redirect('/login')
	if category.user_id != login_session['user_id']:
		return "<script>function myFunction() {alert('You are not authorized to delete this description. Please create your own category, items, and descriptions in order to have this capability.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		item.description = ""
		session.add(item)
		session.commit()
		flash('You successfully deleted yout description')
		return redirect(url_for('showItemDescription', category_id=category.id, item_id=item.id))
	else:
		return render_template('deleteItemDescription.html', category=category, item=item)

# allow user to add a new Item
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this category alert the user that he/she is not authorized to create a new item
# otherwise, navigate to newItem
# if item is created, redirect to items page
@app.route('/catalog/<int:category_id>/item/new/', methods=['POST', 'GET'])
def newItem(category_id):
	if 'username' not in login_session:
		return redirect('/login')
	category = session.query(Category).filter_by(id=category_id).one()
	if login_session['user_id'] != category.user_id:
		return "<script>function myFunction() {alert('You are not authorized to add items to this category. Please create your own category in order to add items.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		newItem = Item(name=request.form['name'], description=request.form['description'], category_id=category.id, user_id=category.user_id)
		session.add(newItem)
		flash('Your new item: %s, was successfully created' % (newItem.name))
		session.commit()
		return redirect(url_for('showItems', category_id=category_id))
	else:
		return render_template('newItem.html', category_id=category_id)

# allow user to edit an Item
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this category alert the user that he/she is not authorized to edit
# otherwise, navigate to editItem
# if item is edited, redirect to items page
@app.route('/catalog/<int:category_id>/item/<int:item_id>/edit/', methods=['GET', 'POST'])
def editItem(category_id, item_id):
	if 'username' not in login_session:
		return redirect('/login')
	editedItem = session.query(Item).filter_by(id=item_id).one()
	category = session.query(Category).filter_by(id=category_id).one()
	if login_session['user_id'] != category.user_id:
		return "<script>function myFunction() {alert('You are not authorized to edit tems for this category. Please create your own category in order to edit items.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		if request.form['name']:
			editedItem.name = request.form['name']
		if request.form['description']:
			editedItem.description = request.form['description']
		session.add(editedItem)
		flash('Item successfully edited')
		session.commit()
		return redirect(url_for('showItems', category_id=category_id))
	else:
		return render_template('editItem.html', category=category, item=editedItem)

# allow user to delete an Item
# if user not logged in, navigate to login page
# if user's id does not match the login_session id (the user did not create this category alert the user that he/she is not authorized to delete
# otherwise, navigate to deleteItem
# if item is deleted, redirect to items page
@app.route('/catalog/<int:category_id>/item/<int:item_id>/delete/', methods=['GET', 'POST'])
def deleteItem(category_id, item_id):
	if 'username' not in login_session:
		return redirect('/login')
	deletedItem = session.query(Item).filter_by(id=item_id).one()
	category = session.query(Category).filter_by(id=category_id).one()
	if login_session['user_id'] != category.user_id:
		return "<script>function myFunction() {alert('You are not authorized to delete items for this category. Please create your own category in order to delete items.');}</script><body onload='myFunction()''>"
	if request.method == 'POST':
		session.delete(deletedItem)
		flash('Item successfully deleted')
		session.commit()
		return redirect(url_for('showItems', category_id=category_id))
	else:
		return render_template('deleteItem.html', item=deletedItem, category=category)

# disconnect user and delete the user's login_session data
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['credentials']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        return redirect(url_for('showCatalog'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showCatalog'))
        
# create a secret key and run local server
# server only runs if script is executed directly from the python interpreter
if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)