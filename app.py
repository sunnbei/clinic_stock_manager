from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv
import io
import os
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# JSTタイムゾーンの設定
JST = pytz.timezone('Asia/Tokyo')

# 在庫アイテムモデル
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

# セットモデル
class Set(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
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
    items = Item.query.filter(Item.deleted_at.is_(None)).all()
    sets = Set.query.filter(Set.deleted_at.is_(None)).all()
    return render_template('index.html', items=items, sets=sets)

@app.route('/history')
def history():
    histories = InventoryHistory.query.order_by(InventoryHistory.created_at.desc()).all()
    
    # 各履歴の時刻をJSTに変換
    for history in histories:
        history.jst_time = history.created_at.replace(tzinfo=pytz.UTC).astimezone(JST)
    
    return render_template('history.html', histories=histories)

@app.route('/item/new', methods=['GET', 'POST'])
def new_item():
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        unit = request.form['unit']
        
        item = Item(name=name, quantity=quantity, unit=unit, deleted_at=None)
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
        set = Set(name=name, deleted_at=None)
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
    
    items = Item.query.filter(Item.deleted_at.is_(None)).all()
    return render_template('new_set.html', items=items)

@app.route('/set/<int:id>/update', methods=['POST'])
def update_set(id):
    set = Set.query.get_or_404(id)
    type = request.form['type']
    
    # セットアイテムの処理
    set_item_ids = request.form.getlist('set_item_ids[]')
    set_item_quantities = request.form.getlist('set_item_quantities[]')
    
    # 追加アイテムの処理
    additional_item_ids = request.form.getlist('additional_item_ids[]')
    additional_quantities = request.form.getlist('additional_quantities[]')
    
    # セットアイテムの処理
    for item_id, quantity in zip(set_item_ids, set_item_quantities):
        if item_id and quantity:
            item = Item.query.get(int(item_id))
            quantity_change = int(quantity)
            
            if quantity_change > 0:  # 数量が0より大きい場合のみ処理
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
    
    # 追加アイテムの処理
    for item_id, quantity in zip(additional_item_ids, additional_quantities):
        if item_id and quantity:
            item = Item.query.get(int(item_id))
            quantity_change = int(quantity)
            
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
        # UTC時刻をJSTに変換
        jst_time = history.created_at.replace(tzinfo=pytz.UTC).astimezone(JST)
        writer.writerow([
            jst_time.strftime('%Y-%m-%d %H:%M:%S'),
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

@app.route('/history/<int:id>/cancel', methods=['POST'])
def cancel_history(id):
    history = InventoryHistory.query.get_or_404(id)
    item = history.item
    
    # 履歴を取り消す（在庫を元に戻す）
    if history.type == 'in':
        # 入庫の取り消し = 出庫
        if item.quantity >= history.quantity_change:
            item.quantity -= history.quantity_change
        else:
            flash(f'{item.name}の在庫が不足しているため取り消しできません。')
            return redirect(url_for('history'))
    else:
        # 出庫の取り消し = 入庫
        item.quantity += history.quantity_change
    
    # 履歴を削除
    db.session.delete(history)
    db.session.commit()
    
    flash('履歴が取り消されました。')
    return redirect(url_for('history'))

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

@app.route('/item/<int:id>/delete', methods=['POST'])
def delete_item(id):
    item = Item.query.get_or_404(id)
    
    # 削除前の制約チェック
    errors = []
    
    # 在庫数が0でない場合は削除不可
    if item.quantity > 0:
        errors.append(f'{item.name}の在庫が{item.quantity}{item.unit}残っているため削除できません。')
    
    # 削除されていないセットに含まれている場合は削除不可
    set_items = SetItem.query.filter_by(item_id=item.id).join(Set).filter(Set.deleted_at.is_(None)).first()
    if set_items:
        errors.append(f'{item.name}は削除されていないセットに含まれているため削除できません。')
    
    if errors:
        for error in errors:
            flash(error)
        return redirect(url_for('index'))
    
    # 論理削除実行
    item.deleted_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'{item.name}が削除されました。')
    return redirect(url_for('index'))

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
    
    items = Item.query.filter(Item.deleted_at.is_(None)).all()
    return render_template('edit_set.html', set=set, items=items)

@app.route('/set/<int:id>/delete', methods=['POST'])
def delete_set(id):
    set = Set.query.get_or_404(id)
    
    # 削除前の制約チェック
    errors = []
    
    # セットに含まれるアイテムの在庫チェック
    for set_item in set.items:
        if set_item.item.quantity > 0:
            errors.append(f'セットに含まれる「{set_item.item.name}」の在庫が{set_item.item.quantity}{set_item.item.unit}残っているため削除できません。')
            break
    
    # セットに含まれるアイテムが他のセットでも使用されているかチェック
    for set_item in set.items:
        # 削除されていない他のセットで同じアイテムが使用されているかチェック
        other_set_items = SetItem.query.filter(
            SetItem.item_id == set_item.item_id,
            SetItem.set_id != set.id
        ).join(Set).filter(Set.deleted_at.is_(None)).first()
        
        if other_set_items:
            errors.append(f'セットに含まれる「{set_item.item.name}」は削除されていない他のセットでも使用されているため削除できません。')
            break
    
    if errors:
        for error in errors:
            flash(error)
        return redirect(url_for('index'))
    
    # セット名を保存（削除後のメッセージ用）
    set_name = set.name
    
    # 論理削除実行
    set.deleted_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'セット「{set_name}」が削除されました。')
    return redirect(url_for('index'))

# データベースの初期化
def init_db():
    with app.app_context():
        db.create_all()
        print("データベースの初期化が完了しました。")

# アプリケーション起動時にデータベースを初期化
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 