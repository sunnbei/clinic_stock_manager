from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv
import io
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
db = SQLAlchemy(app)

# 在庫アイテムモデル
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# セットモデル
class Set(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('SetItem', backref='set', lazy=True)

# セットアイテムモデル（セットとアイテムの中間テーブル）
class SetItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    set_id = db.Column(db.Integer, db.ForeignKey('set.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    item = db.relationship('Item')

# 在庫履歴モデル
class InventoryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'in' or 'out'
    patient_name = db.Column(db.String(100))  # 患者名（出庫時のみ）
    note = db.Column(db.Text)  # 備考（出庫時のみ）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item')

@app.route('/')
def index():
    items = Item.query.all()
    sets = Set.query.all()
    return render_template('index.html', items=items, sets=sets)

@app.route('/history')
def history():
    histories = InventoryHistory.query.order_by(InventoryHistory.created_at.desc()).all()
    return render_template('history.html', histories=histories)

@app.route('/item/new', methods=['GET', 'POST'])
def new_item():
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        unit = request.form['unit']
        
        item = Item(name=name, quantity=quantity, unit=unit)
        db.session.add(item)
        db.session.commit()
        
        flash('新しい在庫アイテムが追加されました。')
        return redirect(url_for('index'))
    
    return render_template('new_item.html')

@app.route('/item/<int:id>/update', methods=['POST'])
def update_item(id):
    item = Item.query.get_or_404(id)
    quantity_change = int(request.form['quantity_change'])
    type = request.form['type']
    
    if type == 'in':
        item.quantity += quantity_change
        history = InventoryHistory(
            item_id=item.id,
            quantity_change=quantity_change,
            type=type
        )
    else:
        if item.quantity >= quantity_change:
            item.quantity -= quantity_change
            history = InventoryHistory(
                item_id=item.id,
                quantity_change=quantity_change,
                type=type,
                patient_name=request.form.get('patient_name'),
                note=request.form.get('note')
            )
        else:
            flash('在庫が不足しています。')
            return redirect(url_for('index'))
    
    db.session.add(history)
    db.session.commit()
    
    flash('在庫が更新されました。')
    return redirect(url_for('index'))

@app.route('/set/new', methods=['GET', 'POST'])
def new_set():
    if request.method == 'POST':
        name = request.form['name']
        set = Set(name=name)
        db.session.add(set)
        db.session.commit()
        
        # セットアイテムの追加
        item_ids = request.form.getlist('item_ids[]')
        quantities = request.form.getlist('quantities[]')
        
        for item_id, quantity in zip(item_ids, quantities):
            if item_id and quantity:
                set_item = SetItem(
                    set_id=set.id,
                    item_id=int(item_id),
                    quantity=int(quantity)
                )
                db.session.add(set_item)
        
        db.session.commit()
        flash('新しいセットが作成されました。')
        return redirect(url_for('index'))
    
    items = Item.query.all()
    return render_template('new_set.html', items=items)

@app.route('/set/<int:id>/update', methods=['POST'])
def update_set(id):
    set = Set.query.get_or_404(id)
    type = request.form['type']
    
    for set_item in set.items:
        item = set_item.item
        quantity_change = set_item.quantity
        
        if type == 'in':
            item.quantity += quantity_change
            history = InventoryHistory(
                item_id=item.id,
                quantity_change=quantity_change,
                type=type
            )
        else:
            if item.quantity >= quantity_change:
                item.quantity -= quantity_change
                history = InventoryHistory(
                    item_id=item.id,
                    quantity_change=quantity_change,
                    type=type,
                    patient_name=request.form.get('patient_name'),
                    note=request.form.get('note')
                )
            else:
                flash(f'{item.name}の在庫が不足しています。')
                return redirect(url_for('index'))
        
        db.session.add(history)
    
    db.session.commit()
    flash('セットの在庫が更新されました。')
    return redirect(url_for('index'))

@app.route('/history/export')
def export_history():
    # CSVデータを作成
    output = io.StringIO()
    writer = csv.writer(output)
    
    # ヘッダー行を追加
    writer.writerow(['日時', 'アイテム', '種類', '数量', '患者名', '備考'])
    
    # 履歴データを取得してCSVに書き込み
    histories = InventoryHistory.query.order_by(InventoryHistory.created_at.desc()).all()
    for history in histories:
        writer.writerow([
            history.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            history.item.name,
            '入庫' if history.type == 'in' else '出庫',
            history.quantity_change,
            history.patient_name or '',
            history.note or ''
        ])
    
    # メモリバッファの先頭に移動
    output.seek(0)
    
    # CSVファイルとしてダウンロード
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'inventory_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/item/<int:id>/edit', methods=['GET', 'POST'])
def edit_item(id):
    item = Item.query.get_or_404(id)
    
    if request.method == 'POST':
        item.name = request.form['name']
        item.unit = request.form['unit']
        db.session.commit()
        flash('在庫アイテムが更新されました。')
        return redirect(url_for('index'))
    
    return render_template('edit_item.html', item=item)

@app.route('/set/<int:id>/edit', methods=['GET', 'POST'])
def edit_set(id):
    set = Set.query.get_or_404(id)
    
    if request.method == 'POST':
        set.name = request.form['name']
        
        # 既存のセットアイテムを削除
        SetItem.query.filter_by(set_id=set.id).delete()
        
        # 新しいセットアイテムを追加
        item_ids = request.form.getlist('item_ids[]')
        quantities = request.form.getlist('quantities[]')
        
        for item_id, quantity in zip(item_ids, quantities):
            if item_id and quantity:
                set_item = SetItem(
                    set_id=set.id,
                    item_id=int(item_id),
                    quantity=int(quantity)
                )
                db.session.add(set_item)
        
        db.session.commit()
        flash('セットが更新されました。')
        return redirect(url_for('index'))
    
    items = Item.query.all()
    return render_template('edit_set.html', set=set, items=items)

# データベースの初期化
def init_db():
    with app.app_context():
        db.create_all()

# アプリケーション起動時にデータベースを初期化
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 