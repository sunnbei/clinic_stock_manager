from app import app, db
from sqlalchemy import text

def migrate_database():
    with app.app_context():
        # Itemテーブルにdeleted_atカラムを追加（存在しない場合のみ）
        try:
            # カラムの存在をチェック
            result = db.session.execute(text("PRAGMA table_info(item)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'deleted_at' not in columns:
                db.session.execute(text("ALTER TABLE item ADD COLUMN deleted_at DATETIME"))
                print("Itemテーブルにdeleted_atカラムを追加しました。")
            else:
                print("Itemテーブルのdeleted_atカラムは既に存在します。")
        except Exception as e:
            print(f"Itemテーブルのdeleted_atカラム追加エラー: {e}")
        
        # Setテーブルにdeleted_atカラムを追加（存在しない場合のみ）
        try:
            # カラムの存在をチェック
            result = db.session.execute(text("PRAGMA table_info([set])"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'deleted_at' not in columns:
                db.session.execute(text("ALTER TABLE [set] ADD COLUMN deleted_at DATETIME"))
                print("Setテーブルにdeleted_atカラムを追加しました。")
            else:
                print("Setテーブルのdeleted_atカラムは既に存在します。")
        except Exception as e:
            print(f"Setテーブルのdeleted_atカラム追加エラー: {e}")
        
        db.session.commit()
        print("データベースマイグレーションが完了しました。")

if __name__ == '__main__':
    migrate_database() 