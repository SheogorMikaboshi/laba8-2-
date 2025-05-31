from flask import Flask, render_template, request, redirect, session, url_for, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Подключение к MongoDB
client = MongoClient(
    "mongodb+srv://admin:228565@repairworks.exoy7l9.mongodb.net/?retryWrites=true&w=majority&appName=repairworks")
db = client.repairworks


@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    # Получаем данные
    data = {
        'user': session['user'],
        'clients': list(db.clients.find()),
        'contractors': list(db.contractors.find()),
        'materials': list(db.materials.find()),
        'objects': list(db.objects.find()),
        'users': list(db.users.find({"root": False}))
    }

    # Фильтр заказов
    if session['user']['is_admin']:
        data['orders'] = list(db.orders.find())
    else:
        data['orders'] = list(db.orders.find({
            "$or": [
                {"user_id": session['user']['_id']},
                {"assigned_user_id": session['user']['_id']}
            ]
        }))

    return render_template('index.html', **data)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = db.users.find_one({
            "login": request.form['login'],
            "password": request.form['password']
        })

        if user:
            session['user'] = {
                "_id": str(user['_id']),
                "login": user['login'],
                "is_admin": user.get('root', False)
            }
            return redirect(url_for('home'))

        flash("Неверный логин или пароль", "error")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/create_order', methods=['POST'])
def create_order():
    if 'user' not in session:
        return redirect(url_for('login'))

    try:
        # Проверка обязательных полей
        required_fields = {
            'client_id': 'Клиент',
            'contractor_id': 'Подрядчик',
            'object_id': 'Объект',
            'user_id': 'Пользователь'
        }

        for field, name in required_fields.items():
            if not request.form.get(field):
                flash(f"Поле '{name}' обязательно для заполнения", "error")
                return redirect(url_for('home'))

        # Получаем данные
        client = db.clients.find_one({"_id": ObjectId(request.form['client_id'])})
        contractor = db.contractors.find_one({"_id": ObjectId(request.form['contractor_id'])})
        obj = db.objects.find_one({"_id": ObjectId(request.form['object_id'])})

        # Расчет стоимости
        cost = obj['area'] * 1000
        materials_list = []
        for material_id in request.form.getlist('materials'):
            material = db.materials.find_one({"_id": ObjectId(material_id)})
            cost += material['cost']
            materials_list.append(material['name'])

        # Сохраняем заказ
        db.orders.insert_one({
            "client": client,
            "contractor": contractor,
            "object": obj,
            "materials": materials_list,
            "cost": cost,
            "user_id": session['user']['_id'],
            "assigned_user_id": request.form['user_id'],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "new"
        })

        flash("Заказ успешно создан!", "success")
        return redirect(url_for('home'))

    except Exception as e:
        flash(f"Ошибка при создании заказа: {str(e)}", "error")
        return redirect(url_for('home'))


@app.route('/delete_order/<order_id>')
def delete_order(order_id):
    if 'user' not in session or not session['user']['is_admin']:
        flash("Требуются права администратора", "error")
        return redirect(url_for('login'))

    db.orders.delete_one({"_id": ObjectId(order_id)})
    flash("Заказ успешно удалён", "success")
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)