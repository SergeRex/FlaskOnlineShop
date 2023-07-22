from appfunctions import load_items_from_cloud, save_items_to_cloud
from appfunctions import load_users_data, save_coupons_to_cloud, load_coupons_from_cloud
from appfunctions import set_img_links,create_list_by_category,get_requested_item, complete_purchase

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import requests
import os
import random
import yagmail
import json
from google.cloud import storage
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from requests.auth import HTTPBasicAuth

# -----------------------------------------------------------------------------------------

MY_EMAIL = os.environ.get('MY_EMAIL_ADDRESS')
MY_PASSWORD = os.environ.get('MY_EMAIL_PASSWORD')
THE_SECRET_KEY = os.environ.get('APP_SECRET_KEY')

# PAYPAL SANDBOX
#PAYPAL_BUSINESS_CLIENT_ID = os.environ.get("PAYPAL_SANDBOX_BUSINESS_CLIENT_ID")
#PAYPAL_BUSINESS_SECRET_KEY = os.environ.get("PAYPAL_SANDBOX_BUSINESS_SECRET_KEY")
#PAYPAL_API_URL = "https://api-m.sandbox.paypal.com"

# PAYPAL LIVE Details
PAYPAL_BUSINESS_CLIENT_ID = os.environ.get("PAYPAL_LIVE_BUSINESS_CLIENT_ID")
PAYPAL_BUSINESS_SECRET_KEY = os.environ.get("PAYPAL_LIVE_BUSINESS_SECRET_KEY")
PAYPAL_API_URL = "https://api-m.paypal.com"


app = Flask(__name__)


# AUTHENTICATION --------------------------------------------------------------------------
app.config['SECRET_KEY'] = THE_SECRET_KEY
login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin):
    pass


@login_manager.user_loader
def user_loader(id):
    users = load_users_data()
    for usr in users:
        if id == usr['id']:
            user = User()
            user.id = id
            return user


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    ### POST
    users = load_users_data()
    email = request.form['email']
    for usr in users:
        if email == usr['email'] and check_password_hash(usr['password'], request.form['password']):
            # use no encrypted password usr['password'] == request.form['password']:
            print(f"{email} {usr['password']} {usr['name']}")
            user = User()
            user.id = usr['id']
            login_user(user)
            return redirect(url_for('manage',category='shop'))
    return render_template("login.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return 'Unauthorized', 401


# MANAGING  --------------------------------------------------------------------------
@app.route("/manage/<category>")
@login_required
def manage(category):
    category_items = create_list_by_category(category)
    return render_template("manage.html", manage_items=category_items)


@app.route("/new_item")
@login_required
def new_item():
    items = load_items_from_cloud()
    next_id = 0
    new_item = {}
    for item in items:
        if item["id"] > next_id:
            next_id = item["id"]
    next_id += 1
    new_item["id"] = next_id
    new_item["pics_qty"] = 0
    new_item["SKU"] = ""
    new_item["title"] = ""
    new_item["price"] = 0
    new_item["category"] = "archive"
    new_item["show_order"] = 1
    new_item["description"] = ""
    items.append(new_item)
    save_items_to_cloud(items)
    return render_template("edit_item.html", item=new_item)


@app.route("/edit_item/<int:id>", methods=["GET", "POST"])
@login_required
def edit_item(id):
    if request.method == "POST":
        if request.form["discountnprice"]:
            discount_price=int(request.form["discountnprice"])
            return redirect(url_for('create_coupon',item_id=id, discount_price=discount_price))
        items = load_items_from_cloud()
        for itm in items:
            if itm["id"] == id:
                # data
                itm["SKU"] = request.form["SKU"]
                itm["title"] = request.form["title"]
                itm["price"] = int(request.form["price"])
                itm["category"] = request.form["category"]
                itm["show_order"] = int(request.form["show_order"])
                itm["description"] = request.form["description"]
                # images
                storage_client = storage.Client('newoldwatches')
                bucket = storage_client.get_bucket('watch_items')
                for pic_num in range(10):
                    name = "img" + str(pic_num)
                    img_file = request.files[name]
                    if img_file:
                        # img_path = f"https://storage.googleapis.com/watch_items/{itm['id']}/{pic_num}.jpg"
                        img_path = f"{itm['id']}/{pic_num}.jpg"
                        blob_img = bucket.blob(img_path)
                        blob_img.upload_from_file(img_file)
                        print(blob_img)
                set_img_links(itm)
                save_items_to_cloud(items)
        return redirect(url_for('manage',category=request.form["category"]))
    # GET
    requested_item = get_requested_item(id)
    set_img_links(requested_item)
    return render_template("edit_item.html", item=requested_item)


@app.route("/delete_img/<int:itm>/<int:pic_num>")
@login_required
def delete_img(itm, pic_num):
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('watch_items')
    blob = bucket.blob(f"{itm}/{pic_num}.jpg")
    generation_match_precondition = None
    generation_match_precondition = blob.generation
    blob.delete(if_generation_match=generation_match_precondition)
    print(f"Blob {itm}/{pic_num}.jpg deleted.")
    requested_item = get_requested_item(itm)
    return render_template("edit_item.html", item=requested_item)


@app.route("/delete_item/<int:id>")
@login_required
def delete_item(id):
    pass


# COUPONS ----------------------------------------------------------------
@app.route("/create_coupon/<int:item_id>/<int:discount_price>")
@login_required
def create_coupon(item_id, discount_price):
    coupons =load_coupons_from_cloud()
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789'
    code = ''
    for i in range(8):
        code += random.choice(alphabet)

    new_coupon = {}
    new_coupon['item_id'] = item_id
    new_coupon['discount_price'] = discount_price
    new_coupon['code'] = code

    item = get_requested_item(item_id)

    new_coupon['SKU'] = item['SKU']
    new_coupon['title'] = item['title']
    new_coupon['price'] = item['price']

    coupons.append(new_coupon)
    save_coupons_to_cloud(coupons)
    return redirect(url_for('view_coupons'))

@app.route("/view_coupons")
@login_required
def view_coupons():
    coupons = load_coupons_from_cloud()
    return render_template("view_coupons.html", coupons=coupons)



@app.route("/delete_coupon/<code>")
def delete_coupon(code):
    coupons = load_coupons_from_cloud()
    for coupon in coupons:
        if coupon['code'] == code:
            coupons.remove(coupon)
    save_coupons_to_cloud(coupons)
    return redirect(url_for('view_coupons'))


# SHOPPING CART --------------------------------------------------------------------------------
@app.route("/shopping_cart", methods=["GET", "POST"])
def shopping_cart():
    if request.method == "POST":
        coupons = load_coupons_from_cloud()
        code = request.form["coupon_number"]
        for item in session['shopping_cart_items']:
            if item['coupon_code'] == code:
                for coupon in coupons:
                    if coupon['code'] == code and coupon['item_id'] == item['id']:
                        item['discount_price'] = coupon['discount_price']
                        session.modified = True
    # GET
    items_cost = 0
    payment_amount = 0
    shop_card_items_loc=session['shopping_cart_items']
    for item in shop_card_items_loc:
        payment_amount += item['discount_price']
        items_cost += item['price']
    return render_template("shopping_cart.html",
                           amount_to_pay=payment_amount,
                           items_cost=items_cost,
                           cart_items=session['shopping_cart_items'],
                           paypal_business_client_id=PAYPAL_BUSINESS_CLIENT_ID)


@app.route("/add_item_to_cart/<int:id>")
def add_item_to_cart(id):
    coupons = load_coupons_from_cloud()
    for cart_item in session['shopping_cart_items']:
        if cart_item['id'] == id:
            return redirect(url_for('shopping_cart'))
    requested_item = get_requested_item(id)
    requested_item["discount_price"]=requested_item["price"]
    requested_item['coupon_code'] = ""
    for coupon in coupons:
        if int(requested_item['id']) == int(coupon['item_id']):
            requested_item['coupon_code'] = coupon['code']
    session['shopping_cart_items'].append(requested_item)
    session.modified = True
    session['num_cart_items'] = len(session['shopping_cart_items'])
    return redirect(url_for('shopping_cart'))


@app.route("/delete_item_from_cart/<int:id>")
def delete_item_from_cart(id):
    for item in session['shopping_cart_items']:
        if item['id'] == id:
            session['shopping_cart_items'].remove(item)
            session.modified = True
    session['num_cart_items'] = len(session['shopping_cart_items'])
    return redirect(url_for('shopping_cart'))


# PAYPAL -----------------------------------------------------------------------------------------
@app.route("/payments/<order_id>/capture", methods=["POST"])
def capture_payment(order_id):  # Checks and confirms payment
    captured_payment = approve_payment(order_id)
    print(captured_payment)
    complete_purchase(captured_payment)
    return jsonify(captured_payment)


def approve_payment(order_id):
    api_link = f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}/capture"
    client_id = PAYPAL_BUSINESS_CLIENT_ID
    secret = PAYPAL_BUSINESS_SECRET_KEY
    basic_auth = HTTPBasicAuth(client_id, secret)
    headers = {
        "Content-Type": "application/json",
    }
    response = requests.post(url=api_link, headers=headers, auth=basic_auth)
    response.raise_for_status()
    json_data = response.json()
    return json_data


# SITE PUBLIC ROUTES -------------------------------------------------------------------------------

@app.route("/")
def index():
    if not 'shopping_cart_items' in session:
        session['shopping_cart_items'] = []
    if not 'num_cart_items' in session:
        session['num_cart_items'] = 0
    return render_template("index.html")


@app.route("/shop")
def shop():
    shop_items = create_list_by_category("shop")
    return render_template("shop.html", watches_shop=shop_items)


@app.route("/collection")
def collection():
    collection_items = create_list_by_category("collection")
    return render_template("collection.html", watches_collection=collection_items)


@app.route("/parts")
def parts():
    parts_items = create_list_by_category("parts")
    return render_template("parts.html", watches_collection=parts_items)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        email_subject = "Message from visitor of newoldwathes.com"
        email_message = f"\nEmail: {data['email']}\n\nMessage:\n{data['message']}"
        with yagmail.SMTP(MY_EMAIL, MY_PASSWORD) as msg:
            msg.send(MY_EMAIL, email_subject, email_message)
        return render_template("contact.html", msg_sent=True)
    # GET
    return render_template("contact.html", msg_sent=False)


@app.route("/view_shop_item/<int:id>")
def view_shop_item(id):
    requested_item = get_requested_item(id)
    images_list = set_img_links(requested_item)
    return render_template("view_shop_item.html", item=requested_item, img_list=images_list)


@app.route("/view_collection_item/<int:id>")
def view_collection_item(id):
    requested_item = get_requested_item(id)
    images_list = set_img_links(requested_item)
    return render_template("view_collection_item.html", item=requested_item, img_list=images_list)


# -----------------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
    # app.run(host="0.0.0.0", debug=True)
