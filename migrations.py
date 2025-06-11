from app import app, db

def init_db():
    with app.app_context():
        db.create_all()
        print("データベースの初期化が完了しました。")

if __name__ == '__main__':
    init_db() 