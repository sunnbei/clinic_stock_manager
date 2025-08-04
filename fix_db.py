import sqlite3
import os

def fix_database():
    db_path = 'instance/inventory.db'
    
    if not os.path.exists(db_path):
        print("データベースファイルが見つかりません。")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # itemテーブルのカラムを確認
        cursor.execute("PRAGMA table_info(item)")
        item_columns = [row[1] for row in cursor.fetchall()]
        print(f"itemテーブルのカラム: {item_columns}")
        
        # setテーブルのカラムを確認
        cursor.execute("PRAGMA table_info([set])")
        set_columns = [row[1] for row in cursor.fetchall()]
        print(f"setテーブルのカラム: {set_columns}")
        
        # itemテーブルにdeleted_atカラムを追加
        if 'deleted_at' not in item_columns:
            cursor.execute("ALTER TABLE item ADD COLUMN deleted_at DATETIME")
            print("itemテーブルにdeleted_atカラムを追加しました。")
        else:
            print("itemテーブルのdeleted_atカラムは既に存在します。")
        
        # setテーブルにdeleted_atカラムを追加
        if 'deleted_at' not in set_columns:
            cursor.execute("ALTER TABLE [set] ADD COLUMN deleted_at DATETIME")
            print("setテーブルにdeleted_atカラムを追加しました。")
        else:
            print("setテーブルのdeleted_atカラムは既に存在します。")
        
        conn.commit()
        print("データベースの修正が完了しました。")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    fix_database() 