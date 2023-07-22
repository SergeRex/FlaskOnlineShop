from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import yagmail
import json
from google.cloud import storage


def load_items_from_cloud():
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('newoldwatches_data')
    blob = bucket.blob('items.json')
    with blob.open("r") as json_file:
        items_json = json.load(json_file)
    sorted_items = sorted(items_json, key=lambda k: k['show_order'], reverse=False)
    return sorted_items


def save_items_to_cloud(items):
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('newoldwatches_data')
    blob = bucket.blob('items.json')
    with blob.open("w") as json_file:
        json.dump(items, json_file)


def load_users_data():
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('newoldwatches_data')
    blob = bucket.blob('users.json')
    with blob.open("r") as json_file:
        users = json.load(json_file)
    return users


def save_coupons_to_cloud(coupons):
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('newoldwatches_data')
    blob = bucket.blob('coupons.json')
    with blob.open("w") as json_file:
        json.dump(coupons, json_file)


def load_coupons_from_cloud():
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('newoldwatches_data')
    blob = bucket.blob('coupons.json')
    with blob.open("r") as json_file:
        coupons = json.load(json_file)
    return coupons


def set_img_links(item):
    storage_client = storage.Client('newoldwatches')
    blobs = storage_client.list_blobs('watch_items', prefix=f"{item['id']}/")
    imglinks = []
    for blob in blobs:
        imglinks.append(blob.name)
    item['pics_qty'] = len(imglinks)
    return imglinks


def create_list_by_category(category_name):
    items = load_items_from_cloud()
    items_list = []
    for item in items:
        if item['category'] == category_name:
            items_list.append(item)
    items_list = sorted(items_list, key=lambda k: k['show_order'], reverse=False)
    return items_list


def get_requested_item(id):
    items=load_items_from_cloud()
    for item in items:
        if item['id'] == id:
            return item


def complete_purchase(captured_payment):
    storage_client = storage.Client('newoldwatches')
    bucket = storage_client.get_bucket('newoldwatches_data')
    blob = bucket.blob('purchases.json')
    with blob.open("r") as json_file:
        purchases = json.load(json_file)
    purchases.append(captured_payment)
    with blob.open("w") as json_file:
        json.dump(purchases, json_file)

    # send email
    email_subject = f"Payment on site newoldwatches.com"
    email_message = f"Paid for {len(session['shopping_cart_items'])} item(s)\n {captured_payment}"
    with yagmail.SMTP(MY_EMAIL, MY_PASSWORD) as msg:
        msg.send(MY_EMAIL, email_subject, email_message)

    items = load_items_from_cloud()
    for cart_item in session['shopping_cart_items']:
        for item in items:
            if cart_item["id"] == item["id"]:
                item["category"] = "sold"
                item["discount_price"] = cart_item["price"]
    save_items_to_cloud(items)
    session['shopping_cart_items'].clear()
    session['num_cart_items'] = 0
    session.modified = True