import os
import psycopg2
from sqlalchemy import text
from app import app, db

def migrate_postgres():
    with app.app_context():
        try:
            # PostgreSQLに接続
            database_url = os.environ.get('DATABASE_URL')
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            # SQLAlchemyエンジンを使用してマイグレーション実行
            with db.engine.connect() as connection:
                # itemテーブルにdeleted_atカラムを追加
                try:
                    connection.execute(text("ALTER TABLE item ADD COLUMN deleted_at TIMESTAMP"))
                    connection.commit()
                    print("itemテーブルにdeleted_atカラムを追加しました。")
                except Exception as e:
                    if "already exists" in str(e) or "duplicate column name" in str(e):
                        print("itemテーブルのdeleted_atカラムは既に存在します。")
                    else:
                        print(f"itemテーブルのdeleted_atカラム追加エラー: {e}")
                
                # setテーブルにdeleted_atカラムを追加
                try:
                    connection.execute(text("ALTER TABLE \"set\" ADD COLUMN deleted_at TIMESTAMP"))
                    connection.commit()
                    print("setテーブルにdeleted_atカラムを追加しました。")
                except Exception as e:
                    if "already exists" in str(e) or "duplicate column name" in str(e):
                        print("setテーブルのdeleted_atカラムは既に存在します。")
                    else:
                        print(f"setテーブルのdeleted_atカラム追加エラー: {e}")
            
            print("PostgreSQLマイグレーションが完了しました。")
            
        except Exception as e:
            print(f"マイグレーションエラー: {e}")

if __name__ == '__main__':
    migrate_postgres() 